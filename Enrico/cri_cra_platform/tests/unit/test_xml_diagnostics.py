import json

import pytest

from credit_assets.xml_diagnostics import (
    UnsafeXmlError,
    analyze_xml_bytes,
    build_union,
    load_mapping,
    summarize_file,
    value_shape,
)

XML_A = """<?xml version="1.0" encoding="UTF-8"?>
<Informe xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <Geral><Competencia>2026-08-31</Competencia><Vazio></Vazio><Nome>Café</Nome></Geral>
  <Series>
    <Serie><Numero>1</Numero><Valor>45048086.96</Valor></Serie>
    <Serie><Numero>2</Numero><Valor>0</Valor></Serie>
  </Series>
  <Devedor><CPF>123.456.789-09</CPF></Devedor>
</Informe>""".encode("utf-8")

XML_B = b"""<?xml version="1.0" encoding="UTF-8"?>
<Informe><Geral><Competencia>2026-07-31</Competencia><Novo>x</Novo></Geral></Informe>"""


def _file(source_id, data):
    analysis = analyze_xml_bytes(data)
    return {
        "source_document_id": source_id,
        **{k: v for k, v in analysis.items() if k != "paths"},
        "summary": summarize_file(analysis),
    }


def _row(rows, path):
    return next(row for row in rows if row["xml_path"] == path)


def test_file_analysis_distinguishes_empty_repeated_and_metadata():
    analysis = analyze_xml_bytes(XML_A)
    assert analysis["root_tag"] == "Informe"
    assert analysis["encoding"] == "UTF-8" and analysis["decodes_as_declared"]
    assert analysis["namespaces"] == {"xsi": "http://www.w3.org/2001/XMLSchema-instance"}
    assert analysis["maximum_depth"] == 4
    rows = summarize_file(analysis)
    empty = _row(rows, "/Informe/Geral/Vazio")
    assert empty["occurrences"] == 1 and empty["filled"] == 0
    assert empty["value_shapes"] == ["empty"]
    serie = _row(rows, "/Informe/Series/Serie")
    assert serie["node_kind"] == "container" and serie["max_repeated_within_parent"] == 2
    valor = _row(rows, "/Informe/Series/Serie/Valor")
    assert valor["occurrences"] == 2 and valor["value_shapes"] == ["decimal_dot", "zero"]


def test_xsi_nil_is_a_shape_distinct_from_empty_and_zero():
    data = b"""<?xml version="1.0" encoding="UTF-8"?>
<R xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<A xsi:nil="true"/><B></B><C>0</C></R>"""
    rows = summarize_file(analyze_xml_bytes(data))
    assert _row(rows, "/R/A")["value_shapes"] == ["xsi_nil"]
    assert _row(rows, "/R/B")["value_shapes"] == ["empty"]
    assert _row(rows, "/R/C")["value_shapes"] == ["zero"]


def test_personal_data_is_flagged_and_masked():
    cpf = _row(summarize_file(analyze_xml_bytes(XML_A)), "/Informe/Devedor/CPF")
    assert cpf["personal_data_suspected"]
    assert cpf["example_values"] == ["***.***.***-**"]


def test_doctype_is_rejected():
    with pytest.raises(UnsafeXmlError):
        analyze_xml_bytes(b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><x>&a;</x>')


def test_union_counts_absence_and_defaults_to_pending_decision():
    union = build_union(
        [_file("1", XML_A), _file("2", XML_B)],
        {"mapping_version": "t", "paths": {
            "/Informe/Geral/Competencia": {"status": "mapped", "justification": "teste"},
        }},
    )
    competencia = _row(union["paths"], "/Informe/Geral/Competencia")
    assert competencia["files_present"] == 2 and competencia["classification_status"] == "mapped"
    novo = _row(union["paths"], "/Informe/Geral/Novo")
    assert novo["files_absent"] == 1 and novo["min_occurrences"] == 0
    assert novo["classification_status"] == "pending_decision"
    assert "/Informe/Geral/Novo" in union["paths_only_in_some_files"]
    assert union["classification_coverage"] == 1.0
    assert union["layout_validation_status"] == "structural_only"


@pytest.mark.parametrize("value, shape", [
    ("", "empty"), ("0", "zero"), ("-0.01", "decimal_dot"), ("100000", "integer"),
    ("4,5", "decimal_comma"), ("2022-10-30", "date_iso"),
    ("31.943.818/0001-71", "cnpj_formatted"), ("CDI + 4,5000 a.a.", "text"),
])
def test_value_shape_describes_without_converting(value, shape):
    assert value_shape(value) == shape


def test_mapping_requires_valid_status_and_justification(tmp_path):
    path = tmp_path / "m.json"
    path.write_text(json.dumps({"paths": {"/a": {"status": "mapped"}}}), encoding="utf-8")
    with pytest.raises(ValueError, match="justificativa"):
        load_mapping(path)
    path.write_text(json.dumps({"paths": {"/a": {"status": "talvez"}}}), encoding="utf-8")
    with pytest.raises(ValueError, match="status"):
        load_mapping(path)
