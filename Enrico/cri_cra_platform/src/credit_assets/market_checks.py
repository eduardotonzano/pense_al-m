"""Verificações de triagem sobre o Informe Mensal de todo o mercado (dados abertos da CVM).

Cada regra devolve um *candidato* a revisão, nunca uma conclusão: o dado da CVM é o do próprio
Informe, então erro de preenchimento vem junto. As regras só leem e não alteram nada.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from typing import Any

MESES = ["janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto", "setembro",
         "outubro", "novembro", "dezembro"]
PERIODIC = re.compile(r"semestral|anual|trimestral|bimestral|quadrimestral")
WEIGHTS = {"em_atraso": 5, "vencido_com_saldo_adimplente": 4, "informe_defasado": 3,
           "vencimento_fora_mes_base": 2, "isin_repetido": 3, "serie_sem_isin": 1,
           "identificador_duplicado": 1}


def fold(text: str | None) -> str:
    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower().strip()


def money(value: str | None) -> Decimal:
    try:
        return Decimal((value or "0").replace(",", "."))
    except InvalidOperation:
        return Decimal(0)


def month_index(date: str) -> int:
    return int(date[:4]) * 12 + int(date[5:7]) - 1


def reference_competence(counts: dict[str, int]) -> str:
    """Última competência já 'cheia': com pelo menos 90% das emissões do mês anterior."""

    months = sorted(counts)
    reference = months[0]
    for previous, current in zip(months, months[1:]):
        if counts[current] >= 0.9 * counts[previous]:
            reference = current
    return reference


def base_months(text: str | None) -> list[int]:
    """Meses (0 a 11) citados no mês-base de pagamento; vazio se o campo não lista meses por extenso."""

    folded = fold(text)
    return [i for i, name in enumerate(MESES) if re.search(rf"\b{name}\b", folded)]


def series_flags(row: dict[str, Any], reference: str) -> list[str]:
    flags = []
    situation = fold(row.get("Situacao"))
    balance = money(row.get("Valor_Certificados"))
    maturity = (row.get("Data_Vencimento") or "")[:10]
    if situation == "em atraso":
        flags.append("em_atraso")
    if maturity and maturity < reference and balance > 0 and situation == "adimplente":
        flags.append("vencido_com_saldo_adimplente")
    months = base_months(row.get("Pagamento_Mes_Base"))
    if months and PERIODIC.search(fold(row.get("Pagamento_Periodicidade"))) and len(maturity) == 10:
        if int(maturity[5:7]) - 1 not in months:
            flags.append("vencimento_fora_mes_base")
    if not (row.get("Codigo_ISIN") or "").strip():
        flags.append("serie_sem_isin")
    return flags


def rank_emissions(
    rows: list[dict[str, Any]], reference: str, last_filing: dict[str, str],
) -> list[dict[str, Any]]:
    """``rows``: última linha de cada série. ``last_filing``: última competência entregue por emissão."""

    isin_owners: dict[str, set[str]] = defaultdict(set)
    isin_issuers: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        if row.get("Codigo_ISIN"):
            isin_owners[row["Codigo_ISIN"]].add(row["Codigo_Identificacao_Certificado"])
            isin_issuers[row["Codigo_ISIN"]].add(row.get("CNPJ_Emissora") or "")
    emissions: dict[str, dict[str, Any]] = {}
    for row in rows:
        cert = row["Codigo_Identificacao_Certificado"]
        item = emissions.setdefault(cert, {
            "certificado": cert, "emissora": row.get("CNPJ_Emissora"), "series": 0,
            "saldo": Decimal(0), "flags": Counter(), "ultima_competencia": last_filing.get(cert, ""),
        })
        balance = money(row.get("Valor_Certificados"))
        item["series"] += 1
        current = last_filing.get(cert, "") >= reference
        item["saldo"] += balance if current else Decimal(0)
        flags = series_flags(row, reference) if current else []
        isin = row.get("Codigo_ISIN")
        if isin and len(isin_owners[isin]) > 1:
            # mesmo ISIN em securitizadoras diferentes é conflito; na mesma securitizadora o certificado
            # aparece com dois códigos (ISIN e CETIP) e isso só duplica a contagem de emissões
            flags.append("isin_repetido" if len(isin_issuers[isin]) > 1 else "identificador_duplicado")
        maturity = (row.get("Data_Vencimento") or "")[:10]
        if (not current and balance > 0 and maturity >= reference
                and month_index(reference) - month_index(last_filing.get(cert, reference)) >= 2):
            flags.append("informe_defasado")
        for flag in flags:
            item["flags"][flag] += 1
    ranking = []
    for item in emissions.values():
        item["score"] = sum(WEIGHTS[flag] for flag in item["flags"])
        ranking.append(item)
    ranking.sort(key=lambda i: (-i["score"], -i["saldo"], i["certificado"]))
    return ranking
