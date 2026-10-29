"""Comparação do mesmo campo entre documentos (Termo, oferta, relatório do AF, DFs).

Só lê ``contract_parameters`` e ``reported_facts``. Compara valores numéricos,
datas e códigos depois de normalizar; texto livre não é comparado: fica listado
para leitura. Nunca decide qual fonte está certa: divergência vira item de revisão.
"""
from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

KINDS = ("number", "date", "code", "text")
TOKENIZERS = ("remuneracao", "nome")
REVIEW_RANK = {"approved": 0, "pending": 1}


def load_checks(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    ids = [check["id"] for check in config["checks"]]
    if len(ids) != len(set(ids)):
        raise ValueError("id duplicado nas verificações")
    for check in config["checks"]:
        if check["kind"] not in KINDS:
            raise ValueError(f"{check['id']}: kind inválido")
        if check["kind"] == "text" and check.get("tokenizer") not in TOKENIZERS:
            raise ValueError(f"{check['id']}: texto exige tokenizer em {TOKENIZERS}")
        check["_param"] = [re.compile(p) for p in check.get("parameters", [])]
        check["_fact"] = [re.compile(p) for p in check.get("facts", [])]
    return config


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


INDEXERS = (
    (re.compile(r"\b(?:taxa\s+)?c?di\b"), "DI"),
    (re.compile(r"\bipca\b"), "IPCA"),
    (re.compile(r"\bselic\b"), "SELIC"),
    (re.compile(r"\bigp-?m\b"), "IGPM"),
    (re.compile(r"\b(?:pre-?fixad[ao]s?|pre)\b"), "PREFIXADA"),
)
MULT_AFTER = re.compile(
    r"(?:d[aeo]s?\s+)?(?:variacao\s+(?:acumulada\s+)?(?:d[aeo]s?\s+)?)?(?:taxa\s+|indexador\s*\(\s*)?(?:c?di|ipca|selic)\b"
)
PERCENT = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")
NAME_STOPWORDS = {
    "s.a.", "sa", "s/a", "ltda", "e", "de", "do", "da", "dos", "das", "cnpj", "nire",
    "sede", "cidade", "estado", "sociedade", "por", "acoes", "em", "no", "na",
}


def tokenize(text: str, tokenizer: str) -> frozenset[str]:
    """Fichas comparáveis de um texto curto. É triagem, não leitura do contrato:
    o relatório sempre mostra o texto original ao lado das fichas."""

    folded = _fold(text or "")
    tokens: set[str] = set()
    if tokenizer == "remuneracao":
        for match in PERCENT.finditer(folded):
            number = format(Decimal(match.group(1).replace(",", ".")).normalize(), "f")
            # percentual colado ao indexador ("100% da Taxa DI") é multiplicador; os demais são taxa/spread
            multiplier = bool(MULT_AFTER.match(folded[match.end():match.end() + 40].lstrip()))
            tokens.add(("mult=" if multiplier else "taxa=") + number)
        for pattern, label in INDEXERS:
            if pattern.search(folded):
                tokens.add("idx=" + label)
    elif tokenizer == "nome":
        for cnpj in re.findall(r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}", folded):
            tokens.add("cnpj=" + re.sub(r"\D", "", cnpj))
        head = re.split(r"[(,;]|\bsociedade\b|\bcnpj\b", folded)[0]
        for word in re.findall(r"[a-z0-9]{3,}", head):
            if word not in NAME_STOPWORDS:
                tokens.add("w=" + word.upper())
    return frozenset(tokens)


def normalize(value: str | None, kind: str) -> str | None:
    """Forma comparável do valor ou None se não for do tipo esperado."""

    text = (value or "").strip()
    if not text:
        return None
    if kind == "number":
        try:
            return format(Decimal(text).normalize(), "f")
        except InvalidOperation:
            return None
    if kind == "date":
        return text if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text) else None
    if kind == "code":
        return re.sub(r"\s+", "", text).upper()
    return None  # texto usa tokenize()


def _group(match: re.Match) -> str:
    return match.groupdict().get("n") or "-"


def _informe_entries(connection: sqlite3.Connection, asset_id: int, check: dict[str, Any]):
    """Valores do Informe Mensal vigente mais recente do ativo (campo ``informe`` do check:
    ``path`` = regex do xml_path, ``group`` = "n" (usa a série) ou "-", ``instance`` opcional)."""

    spec = check.get("informe")
    if not spec:
        return []
    report = connection.execute(
        """SELECT r.report_id, r.reference_date, r.human_review_status, d.source_document_id
           FROM extracted_reports r JOIN documents d ON d.document_pk = r.document_id
           WHERE r.asset_id = ? AND r.is_current = 1
           ORDER BY r.reference_date DESC, r.report_id DESC LIMIT 1""", (asset_id,),
    ).fetchone()
    if report is None:
        return []
    pattern = re.compile(spec["path"])
    entries = []
    for row in connection.execute(
        """SELECT extracted_value_id, xml_path, instance_key, original_value
           FROM extracted_values WHERE report_id = ? AND original_value IS NOT NULL
             AND TRIM(original_value) <> ''""", (report["report_id"],),
    ):
        if not pattern.search(row["xml_path"]):
            continue
        if spec.get("instance") and str(row["instance_key"]) != str(spec["instance"]):
            continue
        group = str(row["instance_key"]) if spec.get("group") == "n" else "-"
        entries.append({
            "group": group, "origin": "informe", "name": row["xml_path"].split("/", 2)[-1],
            "raw": row["original_value"], "unit": None,
            "status": "approved" if report["human_review_status"] == "approved" else "pending",
            "source": f"Informe {report['reference_date']} (doc {report['source_document_id']})",
            "id": row["extracted_value_id"],
        })
    return entries


def _collect(connection: sqlite3.Connection, asset_id: int, check: dict[str, Any]):
    entries = []
    for row in connection.execute(
        """SELECT parameter_id, parameter_name, parameter_value, unit, review_status,
                  source_reference
           FROM contract_parameters
           WHERE asset_id = ? AND review_status <> 'rejected'
             AND (valid_to IS NULL OR valid_to >= date('now'))""", (asset_id,),
    ):
        for pattern in check["_param"]:
            match = pattern.search(row["parameter_name"])
            if match:
                entries.append({
                    "group": _group(match), "origin": "parâmetro",
                    "name": row["parameter_name"], "raw": row["parameter_value"],
                    "unit": row["unit"], "status": row["review_status"],
                    "source": row["source_reference"], "id": row["parameter_id"],
                })
                break
    for row in connection.execute(
        """SELECT f.fact_id, f.fact_name, f.value, f.unit, f.review_status, f.page_number,
                  d.source_document_id, d.category, d.document_name
           FROM reported_facts f
           JOIN document_versions v ON v.version_id = f.document_version_id
           JOIN documents d ON d.document_pk = v.document_id
           WHERE f.asset_id = ? AND f.review_status <> 'rejected'""", (asset_id,),
    ):
        for pattern in check["_fact"]:
            match = pattern.search(row["fact_name"])
            if match:
                entries.append({
                    "group": _group(match), "origin": "fato",
                    "name": row["fact_name"], "raw": row["value"], "unit": row["unit"],
                    "status": row["review_status"],
                    "source": f"{row['document_name']} {row['source_document_id']}, p.{row['page_number']}",
                    "id": row["fact_id"],
                })
                break
    entries.extend(_informe_entries(connection, asset_id, check))
    allowed = check.get("units")
    for entry in entries:
        entry["comparable"] = (
            allowed is None or entry["origin"] == "informe" or (entry["unit"] or "") in allowed
        )
        entry["tokens"] = None
        if check["kind"] == "text":
            tokens = tokenize(entry["raw"], check["tokenizer"]) if entry["comparable"] else frozenset()
            entry["tokens"] = tokens
            entry["normalized"] = ";".join(sorted(tokens)) or None
        else:
            entry["normalized"] = (
                normalize(entry["raw"], check["kind"]) if entry["comparable"] else None
            )
    return entries


def _slots(tokens: frozenset[str]) -> dict[str, frozenset[str]]:
    slots: dict[str, set[str]] = defaultdict(set)
    for token in tokens:
        slot, _, value = token.partition("=")
        slots[slot].add(value)
    return {slot: frozenset(values) for slot, values in slots.items()}


def _text_verdict(comparable: list[dict[str, Any]], tokenizer: str) -> str:
    sets = [e["tokens"] for e in comparable]
    if all(item == sets[0] for item in sets):
        return "concordam"
    if tokenizer == "remuneracao":
        # conflito = duas fontes definem o mesmo campo (indexador, multiplicador, taxa) com valores diferentes
        slotted = [_slots(item) for item in sets]
        for i, first in enumerate(slotted):
            for second in slotted[i + 1:]:
                if any(first[k] != second[k] for k in first.keys() & second.keys()):
                    return "divergem"
        return "compativeis"
    related = all(a <= b or b <= a for i, a in enumerate(sets) for b in sets[i + 1:])
    return "compativeis" if related else "divergem"


def run_checks(connection: sqlite3.Connection, config: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for asset in connection.execute(
        "SELECT asset_id, codigo_cetip, tipo_ativo FROM assets ORDER BY codigo_cetip"
    ).fetchall():
        for check in config["checks"]:
            if asset["tipo_ativo"] not in check.get("applies_to", ["CRI", "CRA"]):
                continue
            by_group = defaultdict(list)
            for entry in _collect(connection, asset["asset_id"], check):
                by_group[entry["group"]].append(entry)
            for group, entries in sorted(by_group.items()):
                comparable = [e for e in entries if e["normalized"] is not None]
                values = sorted({e["normalized"] for e in comparable})
                origins = {e["source"] for e in comparable}
                if len(comparable) < 2 or len(origins) < 2:
                    verdict = "uma_fonte"
                elif check["kind"] == "text":
                    verdict = _text_verdict(comparable, check["tokenizer"])
                elif len(values) == 1:
                    verdict = "concordam"
                else:
                    verdict = "divergem"
                all_approved = all(e["status"] == "approved" for e in comparable)
                results.append({
                    "codigo_cetip": asset["codigo_cetip"], "check_id": check["id"],
                    "label": check["label"], "group": group, "verdict": verdict,
                    "all_approved": all_approved, "values": values, "entries": entries,
                })
    return results
