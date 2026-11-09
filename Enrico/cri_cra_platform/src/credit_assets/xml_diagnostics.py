"""Diagnóstico estrutural de XMLs documentais (Fase E, etapa 8.3).

Só descreve a estrutura real dos arquivos: não extrai valores para o banco,
não normaliza números e não decide mapeamentos. A classificação de cada
caminho vem de um arquivo de mapeamento versionado; caminhos sem decisão
explícita ficam como ``pending_decision``.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

DIAGNOSTIC_VERSION = "0.1.0"
CLASSIFICATION_STATES = ("mapped", "ignored", "pending_decision")
LONG_TEXT_THRESHOLD = 200
MAX_EXAMPLES = 3
MAX_EXAMPLE_LENGTH = 80
XSI_NIL = "{http://www.w3.org/2001/XMLSchema-instance}nil"

_DECLARATION = re.compile(rb"^\s*<\?xml[^>]*encoding=[\"']([A-Za-z0-9._-]+)[\"']")
_FORBIDDEN = re.compile(rb"<!DOCTYPE|<!ENTITY", re.IGNORECASE)
_BASE64 = re.compile(r"^[A-Za-z0-9+/\r\n]{120,}={0,2}$")
_CPF = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_PHONE = re.compile(r"\(?\b\d{2}\)?\s?9?\d{4}-\d{4}\b")
_PERSONAL_TAGS = re.compile(r"cpf|email|telefone|celular|endereco", re.IGNORECASE)


class UnsafeXmlError(ValueError):
    pass


def value_shape(value: str) -> str:
    """Descreve a forma textual do valor sem convertê-lo."""
    if value == "":
        return "empty"
    if re.fullmatch(r"-?0+(\.0+)?", value):
        return "zero"
    if re.fullmatch(r"-?\d+", value):
        return "integer"
    if re.fullmatch(r"-?\d+\.\d+", value):
        return "decimal_dot"
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})*,\d+|-?\d+,\d+", value):
        return "decimal_comma"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return "date_iso"
    if re.fullmatch(r"\d{2}/\d{2}/\d{4}", value):
        return "date_br"
    if re.fullmatch(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", value):
        return "cnpj_formatted"
    return "text"


def personal_data_suspected(tag: str, value: str) -> bool:
    return bool(
        _PERSONAL_TAGS.search(tag)
        or _CPF.search(value)
        or _EMAIL.search(value)
        or _PHONE.search(value)
    )


def _mask(value: str) -> str:
    return re.sub(r"[A-Za-z0-9]", "*", value)


def _example(value: str, personal: bool) -> str:
    shown = _mask(value) if personal else value
    return shown if len(shown) <= MAX_EXAMPLE_LENGTH else shown[:MAX_EXAMPLE_LENGTH] + "…"


def analyze_xml_bytes(data: bytes) -> dict[str, Any]:
    if _FORBIDDEN.search(data):
        raise UnsafeXmlError("XML com DOCTYPE/ENTITY recusado no diagnóstico")
    declared = _DECLARATION.match(data)
    encoding_declared = declared.group(1).decode("ascii") if declared else None
    try:
        data.decode(encoding_declared or "utf-8")
        decodes_as_declared = True
    except (LookupError, UnicodeDecodeError):
        decodes_as_declared = False

    namespaces: dict[str, str] = {}
    stack: list[str] = []
    sibling_counts: list[dict[str, int]] = [defaultdict(int)]
    root_tag = None
    root_attributes: dict[str, str] = {}
    max_depth = 0
    paths: dict[str, dict[str, Any]] = {}

    def entry(path: str, kind: str) -> dict[str, Any]:
        return paths.setdefault(path, {
            "node_kind": kind,
            "occurrences": 0,
            "filled": 0,
            "max_repeated_within_parent": 0,
            "values": [],
        })

    for event, item in ET.iterparse(io.BytesIO(data), events=("start-ns", "start", "end")):
        if event == "start-ns":
            prefix, uri = item
            namespaces[prefix or ""] = uri
            continue
        element = item
        if event == "start":
            sibling_counts[-1][element.tag] += 1
            repeat = sibling_counts[-1][element.tag]
            stack.append(element.tag)
            sibling_counts.append(defaultdict(int))
            max_depth = max(max_depth, len(stack))
            if root_tag is None:
                root_tag = element.tag
                root_attributes = dict(element.attrib)
            path = "/" + "/".join(stack)
            node = entry(path, "leaf")
            node["occurrences"] += 1
            node["max_repeated_within_parent"] = max(
                node["max_repeated_within_parent"], repeat
            )
            for name, value in element.attrib.items():
                attribute = entry(f"{path}/@{name}", "attribute")
                attribute["occurrences"] += 1
                attribute["values"].append(value)
                attribute["filled"] += bool(value.strip())
            continue
        path = "/" + "/".join(stack)
        node = paths[path]
        if len(element):
            node["node_kind"] = "container"
        else:
            text = (element.text or "").strip()
            if element.attrib.get(XSI_NIL) == "true" and not text:
                node.setdefault("nil_count", 0)
                node["nil_count"] += 1
            else:
                node["values"].append(text)
            node["filled"] += bool(text)
        stack.pop()
        sibling_counts.pop()
        element.clear()

    return {
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "raw_file_hash": hashlib.sha256(data).hexdigest(),
        "size_bytes": len(data),
        "encoding": encoding_declared,
        "decodes_as_declared": decodes_as_declared,
        "namespaces": namespaces,
        "root_tag": root_tag,
        "root_attributes": root_attributes,
        "layout_version_declared": (
            root_attributes.get("versao")
            or root_attributes.get("version")
            or root_attributes.get("{http://www.w3.org/2001/XMLSchema-instance}schemaLocation")
            or root_attributes.get(
                "{http://www.w3.org/2001/XMLSchema-instance}noNamespaceSchemaLocation"
            )
        ),
        "maximum_depth": max_depth,
        "paths": paths,
    }


def summarize_file(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for path, node in sorted(analysis["paths"].items()):
        values = node["values"]
        tag = path.rsplit("/", 1)[-1]
        personal = any(personal_data_suspected(tag, value) for value in values)
        rows.append({
            "xml_path": path,
            "node_kind": node["node_kind"],
            "occurrences": node["occurrences"],
            "filled": node["filled"] if node["node_kind"] != "container" else None,
            "max_repeated_within_parent": node["max_repeated_within_parent"],
            "value_shapes": sorted(
                {value_shape(value) for value in values}
                | ({"xsi_nil"} if node.get("nil_count") else set())
            ),
            "long_text_flag": any(len(value) > LONG_TEXT_THRESHOLD for value in values),
            "base64_suspected": any(_BASE64.match(value) for value in values),
            "personal_data_suspected": personal,
            "example_values": [
                _example(value, personal)
                for value in list(dict.fromkeys(v for v in values if v))[:MAX_EXAMPLES]
            ],
        })
    return rows


def load_mapping(path: Path) -> dict[str, Any]:
    mapping = json.loads(path.read_text(encoding="utf-8"))
    for xml_path, decision in mapping.get("paths", {}).items():
        if decision.get("status") not in CLASSIFICATION_STATES:
            raise ValueError(f"status inválido no mapeamento para {xml_path}")
        if decision["status"] != "pending_decision" and not decision.get("justification"):
            raise ValueError(f"decisão sem justificativa no mapeamento para {xml_path}")
    return mapping


def build_union(
    files: Iterable[dict[str, Any]], mapping: dict[str, Any]
) -> dict[str, Any]:
    files = list(files)
    decisions = mapping.get("paths", {})
    union: dict[str, dict[str, Any]] = {}
    for file_info in files:
        for row in file_info["summary"]:
            item = union.setdefault(row["xml_path"], {
                "xml_path": row["xml_path"],
                "node_kind": set(),
                "files_present": 0,
                "files_filled": 0,
                "occurrences_by_file": {},
                "max_repeated_within_parent": 0,
                "value_shapes": set(),
                "long_text_flag": False,
                "base64_suspected": False,
                "personal_data_suspected": False,
                "example_values": [],
            })
            item["node_kind"].add(row["node_kind"])
            item["files_present"] += 1
            item["files_filled"] += bool(row["filled"])
            item["occurrences_by_file"][file_info["source_document_id"]] = row["occurrences"]
            item["max_repeated_within_parent"] = max(
                item["max_repeated_within_parent"], row["max_repeated_within_parent"]
            )
            item["value_shapes"].update(row["value_shapes"])
            for flag in ("long_text_flag", "base64_suspected", "personal_data_suspected"):
                item[flag] = item[flag] or row[flag]
            for example in row["example_values"]:
                if example not in item["example_values"] and len(item["example_values"]) < MAX_EXAMPLES:
                    item["example_values"].append(example)

    total_files = len(files)
    rows = []
    for path in sorted(union):
        item = union[path]
        occurrences = [
            item["occurrences_by_file"].get(file_info["source_document_id"], 0)
            for file_info in files
        ]
        decision = decisions.get(path, {})
        rows.append({
            "xml_path": path,
            "node_kind": "/".join(sorted(item["node_kind"])),
            "files_present": item["files_present"],
            "files_absent": total_files - item["files_present"],
            "files_filled": item["files_filled"] if "container" not in item["node_kind"] else None,
            "min_occurrences": min(occurrences),
            "max_occurrences": max(occurrences),
            "max_repeated_within_parent": item["max_repeated_within_parent"],
            "value_shapes": sorted(item["value_shapes"]),
            "long_text_flag": item["long_text_flag"],
            "base64_suspected": item["base64_suspected"],
            "personal_data_suspected": item["personal_data_suspected"],
            "example_values": item["example_values"],
            "classification_status": decision.get("status", "pending_decision"),
            "classification_source": "mapping" if path in decisions else "default",
        })
    status_counts = {
        state: sum(row["classification_status"] == state for row in rows)
        for state in CLASSIFICATION_STATES
    }
    return {
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "mapping_version": mapping.get("mapping_version"),
        "layout_version": mapping.get("layout_version"),
        "layout_validation_status": "structural_only",
        "files_analyzed": total_files,
        "source_document_ids": [file_info["source_document_id"] for file_info in files],
        "root_tags": sorted({file_info["root_tag"] for file_info in files}),
        "encodings": sorted({str(file_info["encoding"]) for file_info in files}),
        "namespaces": sorted({
            f"{prefix}={uri}"
            for file_info in files
            for prefix, uri in file_info["namespaces"].items()
        }),
        "layout_versions_declared": sorted({
            str(file_info["layout_version_declared"]) for file_info in files
        }),
        "maximum_depth": max((file_info["maximum_depth"] for file_info in files), default=0),
        "paths_total": len(rows),
        "classification_counts": status_counts,
        "classification_coverage": (
            sum(status_counts.values()) / len(rows) if rows else 1.0
        ),
        "paths_only_in_some_files": [
            row["xml_path"] for row in rows if row["files_absent"]
        ],
        "paths": rows,
    }
