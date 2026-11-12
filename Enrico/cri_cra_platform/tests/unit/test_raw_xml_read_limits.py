"""Limites de leitura do walk_values: cada recusa tem código estável da lista XmlRefusal.

Parte dos casos vem do leitor do ramo feat/cri-cra-informe-rating (0b81efb), adaptada ao
formato do walk_values (caminho/@nome e índice por caminho).
"""
from __future__ import annotations

import ast
import hashlib
import inspect
import json
import random
import textwrap
from pathlib import Path

import pytest

from credit_assets.services import raw_xml_extraction_service as service_module
from credit_assets.services.raw_xml_extraction_service import (
    DEFAULT_MAX_BYTES,
    DEFAULT_MAX_DEPTH,
    REFUSAL_DETAILS,
    REFUSAL_PREFIX,
    XmlReadLimits,
    XmlRefusal,
    XmlRefusedError,
    walk_values,
)
from credit_assets.xml_diagnostics import UnsafeXmlError

ROOT = Path(__file__).resolve().parents[2]


def refusal_of(data: bytes, **limits) -> XmlRefusedError:
    with pytest.raises(XmlRefusedError) as caught:
        walk_values(data, limits=XmlReadLimits(**limits))
    return caught.value


def assert_refused(data: bytes, code: XmlRefusal, **limits) -> XmlRefusedError:
    error = refusal_of(data, **limits)
    assert error.code is code
    assert str(error).startswith(f"{REFUSAL_PREFIX}:{code.value}: ")
    return error


def pairs(data: bytes) -> list[tuple[str, str]]:
    return [(value["xml_path"], value["raw_text"]) for value in walk_values(data)]


def nested(depth: int) -> bytes:
    return b"<a>" * depth + b"</a>" * depth


# ------------------------------------------------------- um caso por código de recusa

CASES = {
    XmlRefusal.TAMANHO: (b"<R>" + b"x" * 100 + b"</R>", {"max_bytes": 50}),
    XmlRefusal.CODIFICACAO: ("<R><A>1</A></R>".encode("utf-16"), {}),
    XmlRefusal.DOCTYPE_ENTITY: (b'<!DOCTYPE R [<!ENTITY e "x">]><R>&e;</R>', {}),
    XmlRefusal.MAL_FORMADO: (b"<R><A>1</R>", {}),
    XmlRefusal.PROFUNDIDADE: (nested(4), {"max_depth": 3}),
    XmlRefusal.CONTEUDO_MISTO: (b"<R><A>1</A>resto</R>", {}),
    XmlRefusal.PAR_REPETIDO: (b'<R xmlns:a="urn:a" xmlns:b="urn:b"><A a:x="1" b:x="2"/></R>', {}),
}


def test_the_case_table_and_the_messages_cover_every_refusal_code():
    assert set(CASES) == set(XmlRefusal)
    assert set(REFUSAL_DETAILS) == set(XmlRefusal)


@pytest.mark.parametrize("code", list(XmlRefusal), ids=lambda code: code.value)
def test_each_refusal_starts_the_message_with_its_code(code):
    data, limits = CASES[code]
    error = assert_refused(data, code, **limits)
    assert isinstance(error, UnsafeXmlError)


SECRET = "segredo-12345"


@pytest.mark.parametrize(
    "data",
    [
        f"<R><A>1</A>{SECRET}</R>".encode(),
        f"<R>{SECRET}<A>1</A></R>".encode(),
        f'<?xml version="1.0" encoding="{SECRET}"?><R/>'.encode(),
        f"<R><A>{SECRET}</B></R>".encode(),
        f'<R xmlns:a="urn:a" xmlns:b="urn:b"><A a:x="{SECRET}" b:x="{SECRET}"/></R>'.encode(),
    ],
    ids=["texto-depois", "texto-antes", "codificacao-declarada", "mal-formado", "par-repetido"],
)
def test_refusal_messages_never_repeat_the_xml_content(data):
    assert SECRET not in str(refusal_of(data))


# ------------------------------------------------------------- tetos e fronteiras

def test_the_byte_ceiling_itself_passes_and_one_byte_more_is_refused():
    data = b"<R><A>1</A></R>"
    assert pairs(data) == [("/R/A", "1")]
    assert walk_values(data, limits=XmlReadLimits(max_bytes=len(data)))
    error = assert_refused(data, XmlRefusal.TAMANHO, max_bytes=len(data) - 1)
    assert f"arquivo com {len(data)} bytes, acima do teto de {len(data) - 1} bytes" in str(error)


def test_depth_counts_the_root_as_level_one_and_the_ceiling_itself_passes():
    assert pairs(b"<R/>") == [("/R", "")]
    assert walk_values(b"<R/>", limits=XmlReadLimits(max_depth=1))
    assert_refused(b"<R><A/></R>", XmlRefusal.PROFUNDIDADE, max_depth=1)
    assert len(walk_values(nested(3), limits=XmlReadLimits(max_depth=3))) == 1
    assert_refused(nested(4), XmlRefusal.PROFUNDIDADE, max_depth=3)


def test_the_default_depth_ceiling_itself_passes_and_one_level_more_is_refused():
    assert len(walk_values(nested(DEFAULT_MAX_DEPTH))) == 1
    assert_refused(nested(DEFAULT_MAX_DEPTH + 1), XmlRefusal.PROFUNDIDADE)


def test_the_limits_have_defaults_from_the_module_constants():
    assert XmlReadLimits() == XmlReadLimits(max_bytes=DEFAULT_MAX_BYTES, max_depth=DEFAULT_MAX_DEPTH)
    assert DEFAULT_MAX_DEPTH == 100


@pytest.mark.parametrize("value", [0, -1, 1.5, "10", None, True, False])
@pytest.mark.parametrize("field", ["max_bytes", "max_depth"])
def test_the_limits_refuse_anything_but_positive_integers(field, value):
    with pytest.raises(ValueError, match=field):
        XmlReadLimits(**{field: value})


def test_the_default_byte_ceiling_is_the_document_download_ceiling():
    pytest.importorskip("playwright")
    from credit_assets.services.document_download_service import DEFAULT_MAX_BYTES as DOWNLOAD

    assert DEFAULT_MAX_BYTES == DOWNLOAD


# ------------------------------------------------------------------ conteúdo misto

@pytest.mark.parametrize(
    "data",
    [
        b"<R>antes<A>1</A></R>",
        b"<R><A>1</A>depois</R>",
        b"<R><A>1</A>entre<B>2</B></R>",
        b"<R><A>1</A><![CDATA[x]]></R>",
        "<R> <A>1</A></R>".encode(),
        b"<R>\n  <A>1</A>\n  resto\n</R>",
        b"<R>\n  <A>1</A>\n  meio\n  <B>2</B>\n</R>",
        b"<R>\n  solto\n  <A>1</A>\n</R>",
    ],
    ids=[
        "antes", "depois", "entre", "cdata", "espaco-nao-quebravel",
        "indentado-depois", "indentado-entre", "indentado-antes",
    ],
)
def test_text_next_to_child_elements_is_refused_because_it_would_be_lost(data):
    error = assert_refused(data, XmlRefusal.CONTEUDO_MISTO)
    assert "em /R (linha 1)" in str(error)


def test_indentation_between_children_is_not_mixed_content():
    data = b"<R>\r\n\t <A>1</A>\n  <B> 2 </B>\n</R>"
    assert pairs(data) == [("/R/A", "1"), ("/R/B", " 2 ")]


# --------------------------------------------------------------------- codificação

@pytest.mark.parametrize("codec", ["utf-16", "utf-16-le", "utf-16-be", "utf-32", "utf-32-le"])
def test_utf16_and_utf32_are_refused(codec):
    assert_refused("<R><A>1</A></R>".encode(codec), XmlRefusal.CODIFICACAO)


def test_bytes_that_are_not_utf8_are_refused_even_when_another_encoding_is_declared():
    data = '<?xml version="1.0" encoding="ISO-8859-1"?><R><A>ação</A></R>'.encode("latin-1")
    assert_refused(data, XmlRefusal.CODIFICACAO)


def test_an_unknown_declared_encoding_is_a_codificacao_refusal():
    assert_refused(b'<?xml version="1.0" encoding="nao-existe"?><R/>', XmlRefusal.CODIFICACAO)


def test_utf8_with_bom_and_a_declared_utf8_encoding_are_accepted():
    assert pairs(b"\xef\xbb\xbf<R><A>\xc3\xa7</A></R>") == [("/R/A", "ç")]
    assert pairs('<?xml version="1.0" encoding="UTF-8"?><R><A>ç</A></R>'.encode()) == [("/R/A", "ç")]


# ------------------------------------------------------ DOCTYPE/ENTITY e mal formado

@pytest.mark.parametrize(
    "data",
    [
        b"<!DOCTYPE R><R/>",
        b"<!doctype R><R/>",
        b'<?xml version="1.0"?>\n<!DOCTYPE R [<!ENTITY e "x">]><R>&e;</R>',
        b'<R><!ENTITY e "x"></R>',
    ],
)
def test_doctype_and_entity_declarations_are_refused_before_parsing(data):
    error = assert_refused(data, XmlRefusal.DOCTYPE_ENTITY)
    assert str(error) == f"{REFUSAL_PREFIX}:doctype_entity: XML com DOCTYPE/ENTITY recusado"


@pytest.mark.parametrize(
    "data",
    [b"", b"   ", b"texto solto", b"<R><A>1</R>", b"<R></S>", b"<R/><S/>", b"<R a=1/>"],
)
def test_malformed_xml_is_refused_with_line_and_column(data):
    error = assert_refused(data, XmlRefusal.MAL_FORMADO)
    assert "(linha " in str(error) and ", coluna " in str(error)


# ----------------------------------------------------------- par (caminho, índice)

def test_two_attributes_with_the_same_local_name_are_a_repeated_pair():
    error = assert_refused(CASES[XmlRefusal.PAR_REPETIDO][0], XmlRefusal.PAR_REPETIDO)
    assert "/R/A/@x aparece mais de uma vez na ocorrência 0" in str(error)


def test_xsi_nil_is_not_a_value_and_does_not_collide_with_a_plain_nil_attribute():
    data = b'<R xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><A xsi:nil="true" nil="x"/></R>'
    values = walk_values(data)
    assert [(v["xml_path"], v["raw_text"], v["xsi_nil"]) for v in values] == [
        ("/R/A/@nil", "x", False),
        ("/R/A", "", True),
    ]


# ---------------------------------- comportamento que não muda (adaptado do 0b81efb)

def test_leaves_come_out_in_document_order_with_their_full_path():
    data = b"<R><A>1</A><G><B>2</B><C>3</C></G><D>4</D></R>"
    assert pairs(data) == [("/R/A", "1"), ("/R/G/B", "2"), ("/R/G/C", "3"), ("/R/D", "4")]


def test_attributes_use_slash_at_and_come_before_the_element_text():
    data = b'<R><A u="m" v="2">10</A></R>'
    assert pairs(data) == [("/R/A/@u", "m"), ("/R/A/@v", "2"), ("/R/A", "10")]


def test_the_first_occurrence_has_index_zero_whether_or_not_the_group_repeats():
    once = [(v["xml_path"], v["instance_index"]) for v in walk_values(b"<R><S><N>1</N></S></R>")]
    twice = [
        (v["xml_path"], v["instance_index"])
        for v in walk_values(b"<R><S><N>1</N></S><S><N>2</N></S></R>")
    ]
    assert once == [("/R/S/N", 0)]
    assert twice == [("/R/S/N", 0), ("/R/S/N", 1)]


def test_empty_and_blank_leaves_keep_their_literal_text_and_containers_are_not_values():
    data = b"<R><E/><B>  </B><G><X>1</X></G></R>"
    assert pairs(data) == [("/R/E", ""), ("/R/B", "  "), ("/R/G/X", "1")]


def test_namespaces_are_stripped_from_element_and_attribute_names():
    data = b'<n:R xmlns:n="urn:n" xmlns:m="urn:m"><n:A m:u="x">1</n:A></n:R>'
    assert pairs(data) == [("/R/A/@u", "x"), ("/R/A", "1")]


def test_cdata_and_predefined_entities_are_read_as_text():
    data = b"<R><A><![CDATA[a<b]]></A><B>&lt;&amp;&gt;&quot;&apos;</B></R>"
    assert [value["raw_text"] for value in walk_values(data)] == ["a<b", "<&>\"'"]


# --------------------- propriedade: (caminho, índice) nunca se repete e nada se perde

TAGS = ("A", "B", "C")
ATTRIBUTES = ("p", "q")
TEXTS = ("", "x", "1", "2026-01-31", "a b")


def random_element(rng: random.Random, depth: int):
    children = []

    if depth < 5:
        children = [random_element(rng, depth + 1) for _ in range(rng.randint(0, 4))]

    attributes = {name: rng.choice(TEXTS) for name in ATTRIBUTES if rng.random() < 0.3}
    # Elemento com filhos não tem texto: no walk_values isso é recusa (conteúdo misto).
    text = "" if children else (rng.choice(TEXTS) if rng.random() < 0.8 else "")
    return (rng.choice(TAGS), attributes, text, children)


def serialize(element) -> str:
    tag, attributes, text, children = element
    attrs = "".join(f' {name}="{value}"' for name, value in attributes.items())
    inner = text + "\n".join(serialize(child) for child in children)
    return f"<{tag}{attrs}>{inner}</{tag}>" if inner else f"<{tag}{attrs}/>"


def expected_values(element) -> int:
    _, attributes, _, children = element
    own = len(attributes) + (0 if children else 1)
    return own + sum(expected_values(child) for child in children)


def test_no_path_and_index_pair_repeats_and_no_leaf_or_attribute_is_lost():
    rng = random.Random(2026)

    for _ in range(300):
        tree = random_element(rng, 1)
        values = walk_values(serialize(tree).encode())
        keys = [(value["xml_path"], value["instance_index"]) for value in values]

        assert len(keys) == len(set(keys))
        assert len(values) == expected_values(tree)


# ------------------------------- toda recusa do walk_values usa um código da lista

def offending_raises(function) -> list[str]:
    """Cada raise da função (e das funções internas) que não seja XmlRefusedError(XmlRefusal.<membro>, ...)."""
    source = inspect.getsource(function)
    first_line = inspect.getsourcelines(function)[1]
    members = {code.name for code in XmlRefusal}
    problems = []

    for node in ast.walk(ast.parse(textwrap.dedent(source))):
        if not isinstance(node, ast.Raise):
            continue

        exc = node.exc
        listed = (
            isinstance(exc, ast.Call)
            and isinstance(exc.func, ast.Name)
            and exc.func.id == "XmlRefusedError"
            and bool(exc.args)
            and isinstance(exc.args[0], ast.Attribute)
            and isinstance(exc.args[0].value, ast.Name)
            and exc.args[0].value.id == "XmlRefusal"
            and exc.args[0].attr in members
        )

        if not listed:
            problems.append(f"linha {first_line + node.lineno - 1}: {ast.unparse(node)}")

    return problems


def assert_only_listed_refusals(function) -> None:
    problems = offending_raises(function)
    assert not problems, (
        f"{function.__name__} tem raise fora da lista XmlRefusal: " + "; ".join(problems)
    )


def test_every_refusal_in_walk_values_uses_a_code_from_the_list():
    assert_only_listed_refusals(walk_values)


def test_the_verifier_rejects_a_raise_outside_the_list_and_names_the_offender():
    def synthetic(data):
        if data:
            raise XmlRefusedError(XmlRefusal.TAMANHO, size=1, limit=0)
        raise UnsafeXmlError("texto solto")

    assert offending_raises(synthetic) == [
        f"linha {inspect.getsourcelines(synthetic)[1] + 3}: raise UnsafeXmlError('texto solto')"
    ]

    with pytest.raises(AssertionError, match=r"synthetic tem raise fora da lista XmlRefusal: .*raise UnsafeXmlError\('texto solto'\)"):
        assert_only_listed_refusals(synthetic)


def test_the_service_module_builds_no_refusal_from_loose_text():
    tree = ast.parse(inspect.getsource(service_module))
    loose = [
        ast.unparse(node)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"UnsafeXmlError", "XmlRefusedError"}
        and not (
            node.args
            and isinstance(node.args[0], ast.Attribute)
            and isinstance(node.args[0].value, ast.Name)
            and node.args[0].value.id == "XmlRefusal"
        )
    ]
    assert loose == []


# ------------------------- dados reais (só onde os XMLs brutos estão, como a máquina do Enrico)

SKIP_REASON = "arquivos brutos locais ausentes (data/documents não versionado)"
GOLDEN_SETS = sorted((ROOT / "config" / "golden_sets").glob("*.json"))
DIAGNOSTICS = sorted((ROOT / "reports" / "xml_diagnostics").glob("*.json"))


def test_every_diagnosed_real_xml_passes_the_default_limits_when_available():
    paths = [
        ROOT / json.loads(path.read_text(encoding="utf-8"))["local_file_path"]
        for path in DIAGNOSTICS
    ]
    present = [path for path in paths if path.exists()]

    if not present:
        pytest.skip(SKIP_REASON)

    for path in present:
        walk_values(path.read_bytes())


@pytest.mark.parametrize("golden_path", GOLDEN_SETS, ids=lambda path: path.stem)
def test_golden_set_items_keep_their_text_through_walk_values_when_available(golden_path):
    golden = json.loads(golden_path.read_text(encoding="utf-8"))
    by_file: dict[Path, dict] = {}
    checked = 0

    for item in golden["items"]:
        path = ROOT / item["local_file_path"]

        if not path.exists():
            continue

        if path not in by_file:
            data = path.read_bytes()
            assert hashlib.sha256(data).hexdigest() == item["raw_file_hash"], item["item_id"]
            by_file[path] = {
                (value["xml_path"], value["instance_index"]): value for value in walk_values(data)
            }

        values = by_file[path]
        expected = item["observed"]
        key = (item["xml_path"], item.get("instance_index", 0))

        if not expected.get("element_present", True) or expected.get("attribute_present") is False:
            assert key not in values, item["item_id"]
        else:
            assert key in values, item["item_id"]
            assert values[key]["raw_text"] == expected["raw_text"], item["item_id"]

            if "/@" not in item["xml_path"]:
                assert values[key]["xsi_nil"] == expected["xsi_nil"], item["item_id"]
                assert values[key]["line"] == expected["line"], item["item_id"]

        checked += 1

    if not checked:
        pytest.skip(SKIP_REASON)
