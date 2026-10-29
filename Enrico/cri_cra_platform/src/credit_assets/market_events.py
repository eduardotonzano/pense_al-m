"""Eventos de crédito no mercado inteiro, série a série, entre duas competências do Informe (dados da CVM).

Compara a versão vigente de cada série (chave: securitizadora + ISIN) num mês com o mês anterior em que ela
foi informada. Os eventos são sinais para olhar o ativo, não conclusões: o dado é o do Informe.
"""
from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from credit_assets.cross_checks import tokenize

EVENTS = {
    "entrou_em_atraso": "Situação passou de Adimplente para Em atraso",
    "saiu_do_atraso": "Situação passou de Em atraso para Adimplente",
    "rating_mudou": "Classificação de risco atual mudou",
    "vencimento_mudou": "Data de vencimento mudou (prorrogação ou antecipação)",
    "taxa_mudou": "Taxa de juros informada mudou",
    "saldo_caiu_sem_amortizacao": "Saldo caiu mais que o limite sem amortização informada no mês",
    "saldo_zerou": "Saldo foi a zero",
}
DROP_THRESHOLD = Decimal("0.10")


def _fold(text: str | None) -> str:
    decomposed = unicodedata.normalize("NFKD", text or "")
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", plain).strip().lower()


def _money(value: str | None) -> Decimal | None:
    text = (value or "").strip().replace(",", ".")
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _rate_key(text: str | None) -> frozenset[str]:
    """Taxa comparável por fichas (indexador, multiplicador, taxa), com números arredondados em 2 casas:
    "Pré-fixada 14,4287%" e "14,43% PRE" são a mesma taxa; "CDI + 6,73%" e "CDI + 8,33%" não são."""

    tokens = set()
    for token in tokenize(text or "", "remuneracao"):
        slot, _, value = token.partition("=")
        if slot in ("mult", "taxa"):
            value = str(round(Decimal(value), 2).normalize())
        tokens.add(f"{slot}={value}")
    return frozenset(tokens)


def _numbers(tokens: frozenset[str]) -> frozenset[str]:
    """Multiplicador e taxa; o indexador escrito de formas diferentes ("PRÉ", "Pré-fixada", sem indexador)
    gera ruído demais entre meses, então só o número decide se a taxa mudou."""

    return frozenset(t for t in tokens if t.startswith(("taxa=", "mult=")))


def _has_number(tokens: frozenset[str]) -> bool:
    return any(t.startswith(("taxa=", "mult=")) for t in tokens)


RATING_PLACEHOLDERS = {"0", "-", "--", "n/a", "na", "nao ha", "nao possui", "sem rating", "sem classificacao", "nao se aplica",
                       "nao aplicavel", "nao avaliado", "nd", "n.d."}


def _rating(value: str | None) -> str:
    """Rating comparável; marcadores de vazio ("0", "-", "Não há") contam como sem rating, não como mudança."""

    folded = _fold(value).rstrip(".")
    return "" if folded in RATING_PLACEHOLDERS else folded


def series_key(row: dict[str, Any]) -> tuple[str, str] | None:
    isin = (row.get("Codigo_ISIN") or "").strip().upper()
    return (row.get("CNPJ_Emissora") or "", isin) if isin else None


def compare(previous: dict[str, Any], current: dict[str, Any], threshold: Decimal = DROP_THRESHOLD) -> list[str]:
    events = []
    before, after = _fold(previous.get("Situacao")), _fold(current.get("Situacao"))
    if before == "adimplente" and after == "em atraso":
        events.append("entrou_em_atraso")
    if before == "em atraso" and after == "adimplente":
        events.append("saiu_do_atraso")
    rating_before, rating_after = _rating(previous.get("Classificacao_Risco_Atual")), _rating(current.get("Classificacao_Risco_Atual"))
    if rating_before and rating_after and rating_before != rating_after:
        events.append("rating_mudou")
    due_before, due_after = (previous.get("Data_Vencimento") or "")[:10], (current.get("Data_Vencimento") or "")[:10]
    if due_before and due_after and due_before != due_after:
        events.append("vencimento_mudou")
    rate_before, rate_after = _rate_key(previous.get("Taxa_Juros")), _rate_key(current.get("Taxa_Juros"))
    # só compara quando os dois lados trazem número de taxa; texto sem número não vira evento
    if _has_number(rate_before) and _has_number(rate_after) and _numbers(rate_before) != _numbers(rate_after):
        events.append("taxa_mudou")
    balance_before, balance_after = _money(previous.get("Valor_Certificados")), _money(current.get("Valor_Certificados"))
    amortized = _money(current.get("Amortizacoes")) or Decimal(0)
    if balance_before and balance_before > 0 and balance_after is not None:
        if balance_after == 0:
            events.append("saldo_zerou")
        else:
            unexplained = balance_before - balance_after - amortized
            if unexplained / balance_before > threshold:
                events.append("saldo_caiu_sem_amortizacao")
    return events


def detect(rows: Iterable[dict[str, Any]], month: str) -> list[dict[str, Any]]:
    """``rows``: linhas vigentes (uma por série e competência). Eventos de ``month`` contra a competência anterior
    informada de cada série."""

    history: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    for row in rows:
        key = series_key(row)
        if key is None:
            continue
        history.setdefault(key, {})[(row.get("Data_Referencia") or "")[:7]] = row
    found = []
    for key, months in history.items():
        if month not in months:
            continue
        earlier = sorted(m for m in months if m < month)
        if not earlier:
            continue
        previous, current = months[earlier[-1]], months[month]
        for event in compare(previous, current):
            found.append({
                "evento": event, "isin": key[1], "emissora": key[0],
                "certificado": current.get("Codigo_Identificacao_Certificado"),
                "mes_anterior": earlier[-1], "mes": month,
                "antes": _describe(event, previous), "depois": _describe(event, current),
                "saldo": str(_money(current.get("Valor_Certificados")) or ""),
            })
    return found


def _describe(event: str, row: dict[str, Any]) -> str:
    field = {
        "entrou_em_atraso": "Situacao", "saiu_do_atraso": "Situacao", "rating_mudou": "Classificacao_Risco_Atual",
        "vencimento_mudou": "Data_Vencimento", "taxa_mudou": "Taxa_Juros",
        "saldo_caiu_sem_amortizacao": "Valor_Certificados", "saldo_zerou": "Valor_Certificados",
    }[event]
    value = row.get(field) or ""
    if event == "saldo_caiu_sem_amortizacao":
        value = f"{value} (amortização {row.get('Amortizacoes') or '0'})"
    return str(value)
