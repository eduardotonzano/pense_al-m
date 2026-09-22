from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


SAMPLE_CATEGORIES = (
    "Termo de Securitização",
    "Aditamento",
    "Informe Mensal",
    "Ata/Edital",
    "Fato Relevante",
    "Relatório Agente Fiduciário",
    "Relatório de Rating",
    "Anúncio de Encerramento",
)


def safe_filename(name: str, fallback: str = "documento") -> str:
    value = re.sub(r"[^\w.-]+", "_", name, flags=re.UNICODE).strip("._")
    return (value[:120] or fallback) + ".bin"


def detect_content(data: bytes, content_type: str = "") -> dict[str, Any]:
    prefix = data[:16]
    lowered = content_type.lower()
    if prefix.startswith(b"%PDF-"):
        kind = "PDF"
    elif prefix.startswith(b"PK\x03\x04"):
        kind = "ZIP"
    elif prefix.lstrip().startswith(b"<?xml"):
        kind = "XML"
    elif b"<html" in data[:2048].lower() or "text/html" in lowered:
        kind = "HTML"
    else:
        kind = "outro"
    return {
        "format": kind,
        "signature": prefix.hex(" ")[:47],
        "is_pdf": kind == "PDF",
        "is_html": kind == "HTML",
        "size_bytes": len(data),
    }


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_download(data: bytes, content_type: str, max_bytes: int) -> dict[str, Any]:
    result = detect_content(data, content_type)
    result["content_type"] = content_type
    result["within_limit"] = len(data) <= max_bytes
    result["sha256"] = (
        sha256_bytes(data)
        if data and result["within_limit"] and not result["is_html"]
        else None
    )
    result["accepted"] = bool(data) and result["within_limit"] and not result["is_html"]
    return result


def _row_value(row: Any, *names: str) -> str:
    for name in names:
        value = row[name] if isinstance(row, dict) else row[name]
        if value not in (None, ""):
            return str(value)
    return ""


def build_inventory(rows: Iterable[Any], asset: dict[str, Any]) -> dict[str, Any]:
    rows = list(rows)
    category_counts = Counter(_row_value(row, "category") or "Outro" for row in rows)
    grouped: dict[str, int] = defaultdict(int)
    documents = []
    duplicate_keys: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        document_id = _row_value(row, "document_pk")
        category = _row_value(row, "category") or "Outro"
        document_name = _row_value(row, "document_name")
        key = "|".join((
            category,
            document_name,
            _row_value(row, "reference_date"),
            _row_value(row, "publication_date"),
            _row_value(row, "source_url"),
        ))
        duplicate_keys[key].append(document_id)
        grouped["|".join((
            category,
            _row_value(row, "document_name"),
            _row_value(row, "reference_date"),
            _row_value(row, "publication_date"),
        ))] += 1
        documents.append({
            "document_id": document_id,
            "source_document_id": _row_value(row, "source_document_id"),
            "category": category,
            "document_name": document_name,
            "reference_date": _row_value(row, "reference_date"),
            "publication_date": _row_value(row, "publication_date"),
            "source": _row_value(row, "source"),
            "url": _row_value(row, "source_url"),
            "file_hash": _row_value(row, "file_hash"),
        })
    duplicates = [
        {"key": key, "document_ids": ids}
        for key, ids in duplicate_keys.items() if len(ids) > 1
    ]
    dates = [
        value for row in documents
        for value in (row["reference_date"], row["publication_date"]) if value
    ]
    return {
        "asset": {
            "asset_id": asset["asset_id"],
            "codigo_cetip": asset["codigo_cetip"],
            "isin": asset["isin"],
            "tipo_ativo": asset["tipo_ativo"],
        },
        "total_documents": len(rows),
        "category_counts": dict(sorted(category_counts.items())),
        "missing_categories": [category for category in SAMPLE_CATEGORIES if not category_counts[category]],
        "period": {"min": min(dates) if dates else None, "max": max(dates) if dates else None},
        "documents": documents,
        "groups": [{"key": key, "count": count} for key, count in sorted(grouped.items())],
        "potential_duplicates": duplicates,
        "invalid_url_document_ids": [
            row["document_id"] for row in documents
            if not row["url"].lower().startswith(("http://", "https://"))
        ],
        "repeated_presentations": [],
    }


def select_samples(rows: Iterable[Any]) -> list[dict[str, Any]]:
    selected = []
    seen = set()
    for row in rows:
        category = _row_value(row, "category") or "Outro"
        if category == "Outro":
            name = _row_value(row, "document_name").lower()
            inferred = (
                ("Informe Mensal", "Informe Mensal") if "informe mensal" in name else
                ("Termo de Securitização", "Termo de Securitização") if "termo" in name else
                ("Aditamento", "Aditamento") if "aditamento" in name else
                ("Ata/Edital", "Ata/Edital") if "ata" in name or "edital" in name else
                ("Fato Relevante", "Fato Relevante") if "fato relevante" in name else
                ("Relatório de Rating", "Relatório de Rating") if "rating" in name else
                ("Relatório Agente Fiduciário", "Relatório Agente Fiduciário")
                if "agente fiduci" in name else
                ("Anúncio de Encerramento", "Anúncio de Encerramento")
                if "encerramento" in name else None
            )
            category = inferred[1] if inferred else category
        if category in SAMPLE_CATEGORIES and category not in seen:
            selected.append({
                "category": category,
                "document_id": _row_value(row, "document_pk"),
                "source_url": _row_value(row, "source_url"),
                "document_name": _row_value(row, "document_name"),
            })
            seen.add(category)
    return selected


def find_row_by_document_id(rows: Iterable[Any], source_document_id: str) -> Any | None:
    target = str(source_document_id)
    for row in rows:
        values = {
            str(row.get(name, "") if isinstance(row, dict) else row[name])
            for name in ("id", "idDocumento", "id_documento", "source_document_id")
            if (row.get(name) if isinstance(row, dict) else name in row.keys()) not in (None, "")
        }
        if target in values:
            return row
    return None


def identify_view_action(elements: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    for element in elements:
        haystack = " ".join(
            str(element.get(key, "")).lower()
            for key in ("href", "onclick", "title", "aria_label", "text")
        )
        if any(term in haystack for term in ("visualizar", "documento", "download", "baixar")):
            return element
    return None


def identify_download_action(elements: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    for element in elements:
        haystack = " ".join(
            str(element.get(key, "")).lower()
            for key in ("href", "onclick", "title", "aria_label", "text")
        )
        if "download" in haystack or "baixar" in haystack:
            return element
    return None
