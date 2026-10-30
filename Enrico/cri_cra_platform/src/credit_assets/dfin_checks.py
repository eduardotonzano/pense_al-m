"""Sinais das demonstrações financeiras dos patrimônios separados (índice DFIN da CVM).

Por certificado, olha a DF mais recente e a anterior: opinião do auditor (ressalva, abstenção, adversa),
piora entre as duas e prazo de entrega. Também aponta emissões com Informe recente e sem DF entregue no período.
Triagem: o texto da opinião é o informado à CVM; o relatório do auditor precisa ser lido.
"""
from __future__ import annotations

import unicodedata
from datetime import date
from typing import Any, Iterable

SEVERITY = {"sem ressalva e sem enfase": 0, "sem ressalva e com enfase": 0, "sem ressalva": 0,
            "com ressalva": 2, "adversa": 3, "opiniao adversa": 3, "abstencao de opiniao": 3, "abstencao": 3}


def _fold(text: str | None) -> str:
    decomposed = unicodedata.normalize("NFKD", text or "")
    return " ".join("".join(c for c in decomposed if not unicodedata.combining(c)).lower().split())


def opinion_severity(text: str | None) -> int | None:
    """0 = sem ressalva; 2 = com ressalva; 3 = adversa ou abstenção; None = não informado ou desconhecido."""

    folded = _fold(text)
    if not folded:
        return None
    if folded in SEVERITY:
        return SEVERITY[folded]
    if "abstenc" in folded or "advers" in folded:
        return 3
    if "com ressalva" in folded:
        return 2
    if "sem ressalva" in folded:
        return 0
    return None


def delivery_days(reference: str, delivered: str) -> int | None:
    try:
        return (date.fromisoformat(delivered[:10]) - date.fromisoformat(reference[:10])).days
    except (TypeError, ValueError):
        return None


def latest_by_certificate(rows: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Por certificado, DFs ordenadas da mais recente para a mais antiga (uma por data-base, maior versão)."""

    best: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (row["Codigo_Identificacao_Certificado"], (row.get("Data_Referencia") or "")[:10])
        version = int((row.get("Versao") or "1").strip() or 1)
        if key not in best or version > int((best[key].get("Versao") or "1").strip() or 1):
            best[key] = row
    grouped: dict[str, list[dict[str, Any]]] = {}
    for (cert, _), row in best.items():
        grouped.setdefault(cert, []).append(row)
    for items in grouped.values():
        items.sort(key=lambda r: r.get("Data_Referencia") or "", reverse=True)
    return grouped


def signals(history: list[dict[str, Any]], deadline_days: int = 90) -> list[str]:
    if not history:
        return []
    last = history[0]
    found = []
    severity = opinion_severity(last.get("Parecer_Auditor"))
    if severity == 2:
        found.append("df_com_ressalva")
    if severity == 3:
        found.append("df_abstencao_ou_adversa")
    if len(history) > 1:
        before = opinion_severity(history[1].get("Parecer_Auditor"))
        if severity is not None and before is not None and severity > before:
            found.append("opiniao_piorou")
    days = delivery_days(last.get("Data_Referencia") or "", last.get("Data_Entrega") or "")
    if days is not None and days > deadline_days:
        found.append("df_entregue_apos_prazo")
    return found
