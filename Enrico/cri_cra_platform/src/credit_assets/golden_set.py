"""Golden set de validação manual (Fase E, etapa 8.4).

Cada item aponta para um caminho XML de um arquivo congelado por SHA-256 e
registra o que está literalmente no XML bruto. Os itens só valem como
referência depois de revisão humana (``human_review_status = approved``).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from xml.parsers import expat

from credit_assets.xml_diagnostics import UnsafeXmlError, _FORBIDDEN

GOLDEN_SET_SCHEMA_VERSION = "1"
XSI_NIL = "http://www.w3.org/2001/XMLSchema-instance nil"
REVIEW_STATES = ("pending", "approved", "rejected", "corrected")
FIELD_STATES = (
    "present_value", "present_empty", "absent", "zero", "not_applicable", "invalid",
)
REQUIRED_CASE_TYPES = (
    "present_value", "present_empty", "absent", "zero", "monetary", "percentage",
    "repeated_block", "resubmission", "text", "invalid",
)
MAX_EXCERPT = 200


def locate(data: bytes, xml_path: str, instance_index: int = 0) -> dict[str, Any]:
    """Localiza ``xml_path`` (ou ``.../@atributo``) no XML bruto sem normalizar o texto."""
    if _FORBIDDEN.search(data):
        raise UnsafeXmlError("XML com DOCTYPE/ENTITY recusado")
    element_path, _, attribute = xml_path.partition("/@")
    parser = expat.ParserCreate(namespace_separator=" ")
    stack: list[str] = []
    seen = 0
    found: dict[str, Any] | None = None
    capturing = False
    chunks: list[str] = []

    def start(name, attributes):
        nonlocal seen, found, capturing
        stack.append(name.split(" ")[-1])
        if "/" + "/".join(stack) == element_path:
            if found is None and seen == instance_index:
                found = {
                    "element_present": True,
                    "line": parser.CurrentLineNumber,
                    "attributes": dict(attributes),
                }
                capturing = True
            seen += 1

    def end(name):
        nonlocal capturing
        if capturing and "/" + "/".join(stack) == element_path:
            found["raw_text"] = "".join(chunks)
            capturing = False
        stack.pop()

    def text(value):
        if capturing and "/" + "/".join(stack) == element_path:
            chunks.append(value)

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CharacterDataHandler = text
    parser.Parse(data, True)

    if found is None:
        return {"element_present": False, "occurrences": seen}
    lines = data.decode("utf-8").splitlines()
    excerpt = lines[found["line"] - 1].strip()
    result = {
        "element_present": True,
        "occurrences": seen,
        "line": found["line"],
        "xsi_nil": found["attributes"].get(XSI_NIL) == "true",
        "evidence_excerpt": excerpt[:MAX_EXCERPT],
        "evidence_excerpt_truncated": len(excerpt) > MAX_EXCERPT,
    }
    if attribute:
        key = next(
            (name for name in found["attributes"] if name.split(" ")[-1] == attribute),
            None,
        )
        result["attribute_present"] = key is not None
        result["raw_text"] = found["attributes"].get(key) if key else None
    else:
        result["raw_text"] = found.get("raw_text", "")
    return result


def load_golden_set(path: Path) -> dict[str, Any]:
    golden = json.loads(path.read_text(encoding="utf-8"))
    ids = [item["item_id"] for item in golden["items"]]
    if len(ids) != len(set(ids)):
        raise ValueError("item_id duplicado no golden set")
    for item in golden["items"]:
        if item["human_review_status"] not in REVIEW_STATES:
            raise ValueError(f"{item['item_id']}: human_review_status inválido")
        if item["proposed_field_state"] not in FIELD_STATES:
            raise ValueError(f"{item['item_id']}: proposed_field_state inválido")
        if item["human_review_status"] == "approved" and not item.get("reviewed_by"):
            raise ValueError(f"{item['item_id']}: aprovação sem revisor")
    return golden


def verify_item(item: dict[str, Any], data: bytes) -> list[str]:
    """Compara o item congelado com o XML bruto; devolve divergências."""
    problems = []
    if hashlib.sha256(data).hexdigest() != item["raw_file_hash"]:
        return ["raw_file_hash diverge do arquivo"]
    observed = locate(data, item["xml_path"], item.get("instance_index", 0))
    expected = item["observed"]
    for key in ("element_present", "raw_text", "xsi_nil", "line", "attribute_present"):
        if key in expected and observed.get(key) != expected[key]:
            problems.append(f"{key}: esperado {expected[key]!r}, observado {observed.get(key)!r}")
    return problems


def coverage(golden: dict[str, Any]) -> dict[str, Any]:
    covered = {case for item in golden["items"] for case in item["case_types"]}
    approved = sum(item["human_review_status"] == "approved" for item in golden["items"])
    return {
        "items": len(golden["items"]),
        "approved": approved,
        "pending": sum(item["human_review_status"] == "pending" for item in golden["items"]),
        "required_case_types_covered": [c for c in REQUIRED_CASE_TYPES if c in covered],
        "required_case_types_missing": [c for c in REQUIRED_CASE_TYPES if c not in covered],
        "publishable": (
            approved == len(golden["items"])
            and all(c in covered for c in REQUIRED_CASE_TYPES)
        ),
    }
