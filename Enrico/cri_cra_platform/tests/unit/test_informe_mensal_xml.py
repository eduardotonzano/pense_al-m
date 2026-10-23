"""O leitor nao conhece nenhuma tag do informe. Todo XML destes testes e inventado e fica
dentro do codigo: nenhum documento baixado, nenhum arquivo .xml."""

from __future__ import annotations

import random

import pytest

from credit_assets.parsers.informe_mensal_xml import (
    DEFAULT_MAX_BYTES,
    MAX_DEPTH,
    PARSER_VERSION,
    InformeXmlError,
    classify_value,
    parse_informe_xml,
)


def rows(xml: str | bytes):
    data = xml.encode("utf-8") if isinstance(xml, str) else xml
    return [
        (item.field, item.occurrence, item.value, item.value_kind)
        for item in parse_informe_xml(data).values
    ]


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        (None, "empty"), ("", "empty"), ("   ", "empty"), ("\n\t", "empty"),
        ("12", "number"), ("-3", "number"), ("12.50", "number"), ("-0.5", "number"),
        ("007", "number"), (" 12 ", "number"),
        ("1,5", "text"), ("1.234,56", "text"), ("+5", "text"), ("1e5", "text"),
        (".5", "text"), ("5.", "text"), ("1 000", "text"), ("٣", "text"),
        ("2026-08-01", "date"), ("2026-02-30", "text"), ("2026-13-01", "text"),
        ("01/08/2026", "text"), ("2026-08-01T10:00:00", "text"),
        ("abc", "text"), ("N/A", "text"),
    ],
)
def test_the_kind_comes_from_the_shape_of_the_text_only(text, kind):
    assert classify_value(text) == kind


def test_leaves_come_out_in_document_order_with_their_full_path():
    xml = "<Raiz><Grupo><A>1</A><B>texto</B></Grupo><C>2026-08-01</C></Raiz>"

    assert rows(xml) == [
        ("/Raiz/Grupo/A", "", "1", "number"),
        ("/Raiz/Grupo/B", "", "texto", "text"),
        ("/Raiz/C", "", "2026-08-01", "date"),
    ]
    parsed = parse_informe_xml(xml.encode())
    assert (parsed.root, parsed.namespaces) == ("Raiz", ())


def test_attributes_become_fields_with_an_at_sign_and_come_before_the_text():
    xml = '<R><V escala="2" vazio="" tipo="X">10</V></R>'

    assert rows(xml) == [
        ("/R/V@escala", "", "2", "number"),
        ("/R/V@vazio", "", None, "empty"),
        ("/R/V@tipo", "", "X", "text"),
        ("/R/V", "", "10", "number"),
    ]


def test_repeated_siblings_record_depth_and_position_and_the_first_stays_blank():
    xml = (
        "<R><Classes>"
        "<Classe><V>1</V></Classe><Classe><V>2</V></Classe><Classe><V>3</V></Classe>"
        "</Classes></R>"
    )

    assert rows(xml) == [
        ("/R/Classes/Classe/V", "", "1", "number"),
        ("/R/Classes/Classe/V", "3:2", "2", "number"),
        ("/R/Classes/Classe/V", "3:3", "3", "number"),
    ]


def test_nested_repetition_lists_every_level_whose_position_is_above_one():
    xml = (
        "<R>"
        "<G><I><V>a</V><V>b</V></I><I><V>c</V></I></G>"
        "<G><I><V>d</V></I></G>"
        "</R>"
    )

    assert rows(xml) == [
        ("/R/G/I/V", "", "a", "text"),
        ("/R/G/I/V", "4:2", "b", "text"),
        ("/R/G/I/V", "3:2", "c", "text"),
        ("/R/G/I/V", "2:2", "d", "text"),
    ]


def test_the_first_occurrence_has_the_same_key_whether_or_not_the_group_repeats():
    one = rows("<R><Classe><V>1</V></Classe></R>")
    two = rows("<R><Classe><V>1</V></Classe><Classe><V>2</V></Classe></R>")

    assert one[0] == two[0] == ("/R/Classe/V", "", "1", "number")
    assert two[1] == ("/R/Classe/V", "2:2", "2", "number")


def test_empty_and_blank_elements_are_rows_with_no_value_but_containers_are_not():
    assert rows("<R><A/><B>   </B><C></C><D><E>1</E></D></R>") == [
        ("/R/A", "", None, "empty"),
        ("/R/B", "", None, "empty"),
        ("/R/C", "", None, "empty"),
        ("/R/D/E", "", "1", "number"),
    ]
    assert rows("<R/>") == [("/R", "", None, "empty")]


def test_text_before_the_first_child_is_kept_under_the_container_field():
    assert rows("<R>nota<A>1</A></R>") == [
        ("/R", "", "nota", "text"),
        ("/R/A", "", "1", "number"),
    ]


def test_text_after_a_child_is_refused_because_it_would_be_lost():
    with pytest.raises(InformeXmlError, match="misto"):
        parse_informe_xml(b"<R><A>1</A>sobra</R>")

    assert rows("<R>\n  <A>1</A>\n  <B>2</B>\n</R>") == [
        ("/R/A", "", "1", "number"),
        ("/R/B", "", "2", "number"),
    ]


def test_values_lose_the_spaces_at_the_ends_and_nothing_else():
    assert rows("<R><A>\n   a   b  \n</A></R>") == [("/R/A", "", "a   b", "text")]


def test_namespaces_are_stripped_from_names_and_listed():
    xml = '<r:Raiz xmlns:r="urn:teste" xmlns:o="urn:outro"><r:A o:id="7">1</r:A></r:Raiz>'
    parsed = parse_informe_xml(xml.encode())

    assert [(item.field, item.value) for item in parsed.values] == [
        ("/Raiz/A@id", "7"),
        ("/Raiz/A", "1"),
    ]
    assert parsed.namespaces == ("urn:outro", "urn:teste")
    assert rows('<Raiz xmlns="urn:x"><A>1</A></Raiz>') == [("/Raiz/A", "", "1", "number")]


def test_two_attributes_that_collapse_to_the_same_name_are_refused():
    xml = '<R xmlns:a="urn:a" xmlns:b="urn:b"><V a:id="1" b:id="2">x</V></R>'

    with pytest.raises(InformeXmlError, match="repetido"):
        parse_informe_xml(xml.encode())


def test_cdata_and_predefined_entities_are_read_as_text():
    xml = "<R><A><![CDATA[a < b & c]]></A><B>x &amp; y &lt; z &#233;</B></R>"

    assert rows(xml) == [
        ("/R/A", "", "a < b & c", "text"),
        ("/R/B", "", "x & y < z é", "text"),
    ]


def test_declared_encoding_and_utf8_bom_are_honoured():
    declared = '<?xml version="1.0" encoding="ISO-8859-1"?><R><A>Securitização</A></R>'
    utf8 = '<?xml version="1.0" encoding="UTF-8"?><R><A>Securitização</A></R>'

    assert rows(declared.encode("latin-1")) == [("/R/A", "", "Securitização", "text")]
    assert rows(b"\xef\xbb\xbf" + utf8.encode("utf-8")) == [("/R/A", "", "Securitização", "text")]


@pytest.mark.parametrize("codec", ["utf-16", "utf-16-le", "utf-32"])
def test_utf16_and_utf32_are_refused(codec):
    with pytest.raises(InformeXmlError, match="Codificacao"):
        parse_informe_xml("<R><A>1</A></R>".encode(codec))


@pytest.mark.parametrize(
    "xml",
    [
        "<!DOCTYPE R><R/>",
        "<!doctype R><R/>",
        "<! DOCTYPE R><R/>",
        '<?xml version="1.0"?><!DOCTYPE R [<!ENTITY e "x">]><R>&e;</R>',
        (
            '<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">'
            '<!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">]><lolz>&lol2;</lolz>'
        ),
        '<R><!ENTITY e "x"></R>',
    ],
)
def test_doctype_and_entity_declarations_are_refused_before_parsing(xml):
    with pytest.raises(InformeXmlError, match="DOCTYPE"):
        parse_informe_xml(xml.encode())


@pytest.mark.parametrize(
    "xml",
    [b"", b"   ", b"texto solto", b"<R><A>1</R>", b"<R></S>", b"<R/><S/>", b"<R a=1/>", b'<?xml version="1.0" encoding="nao-existe"?><R/>'],
)
def test_malformed_xml_is_refused_with_a_clear_error(xml):
    with pytest.raises(InformeXmlError, match="mal formado"):
        parse_informe_xml(xml)


def test_oversized_and_too_deep_documents_are_refused():
    with pytest.raises(InformeXmlError, match="limite"):
        parse_informe_xml(b"<R>" + b"x" * 100 + b"</R>", max_bytes=50)

    assert DEFAULT_MAX_BYTES == 2 * 1024 * 1024
    ok = "<a>" * MAX_DEPTH + "</a>" * MAX_DEPTH
    too_deep = "<a>" * (MAX_DEPTH + 1) + "</a>" * (MAX_DEPTH + 1)
    assert len(rows(ok)) == 1

    with pytest.raises(InformeXmlError, match="profundidade"):
        parse_informe_xml(too_deep.encode())


def test_only_bytes_are_accepted():
    with pytest.raises(TypeError):
        parse_informe_xml("<R/>")  # type: ignore[arg-type]


def test_the_parser_version_is_declared():
    assert PARSER_VERSION == "informe_mensal_xml/1"


# ---- propriedade: (field, occurrence) nunca se repete e nada se perde ------------

TAGS = ("A", "B", "C")
ATTRIBUTES = ("p", "q")
TEXTS = ("", "x", "1", "2026-01-31", "a b")


def random_element(rng: random.Random, depth: int):
    children = []

    if depth < 5:
        children = [random_element(rng, depth + 1) for _ in range(rng.randint(0, 4))]

    attributes = {name: rng.choice(TEXTS) for name in ATTRIBUTES if rng.random() < 0.3}
    text = rng.choice(TEXTS) if rng.random() < 0.8 else ""
    return (rng.choice(TAGS), attributes, text, children)


def serialize(element) -> str:
    tag, attributes, text, children = element
    attrs = "".join(f' {name}="{value}"' for name, value in attributes.items())
    inner = text + "\n".join(serialize(child) for child in children)
    return f"<{tag}{attrs}>{inner}</{tag}>" if (inner or text) else f"<{tag}{attrs}/>"


def expected_rows(element) -> int:
    _, attributes, text, children = element
    own = len(attributes) + (1 if (text.strip() or not children) else 0)
    return own + sum(expected_rows(child) for child in children)


def test_no_field_and_occurrence_pair_repeats_and_no_leaf_is_lost():
    rng = random.Random(2026)

    for _ in range(300):
        tree = random_element(rng, 1)
        found = parse_informe_xml(serialize(tree).encode()).values
        keys = [(item.field, item.occurrence) for item in found]

        assert len(keys) == len(set(keys))
        assert len(found) == expected_rows(tree)
