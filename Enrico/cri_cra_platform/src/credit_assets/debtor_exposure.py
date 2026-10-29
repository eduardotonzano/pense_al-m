"""Exposição por devedor no mercado inteiro de CRA/CRI e sinal de contágio (dados abertos da CVM).

A tabela ``*_cedente_devedor`` do Informe traz, por certificado, o CNPJ dos devedores (e cedentes) que
representam mais de 20% dos créditos e o percentual. Aqui:
  - o CNPJ é normalizado (só dígitos) e validado pelos dígitos verificadores; inválido fica de fora e é contado;
  - a exposição estimada é percentual × saldo dos certificados da emissão no mês;
  - "contágio" = devedor com alguma emissão em atraso e outra emissão ainda adimplente.
CNPJ é o identificador forte (regra 6 do projeto): nada é unido por nome.
"""
from __future__ import annotations

import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable


def normalize_cnpj(value: str | None) -> str | None:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) != 14 or len(set(digits)) == 1:
        return None
    def check(base: str) -> str:
        weights = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2][-len(base):]
        total = sum(int(d) * w for d, w in zip(base, weights))
        rest = total % 11
        return "0" if rest < 2 else str(11 - rest)
    first = check(digits[:12])
    second = check(digits[:12] + first)
    return digits if digits[12:] == first + second else None


def fraction(value: str | None) -> Decimal | None:
    """Percentual do Informe como fração entre 0 e 1; fora disso (ex.: -1) é inválido."""

    try:
        number = Decimal((value or "").strip().replace(",", "."))
    except InvalidOperation:
        return None
    if number > 1 and number <= 100:
        number = number / 100  # alguns informes trazem 0-100
    return number if 0 < number <= 1 else None


def aggregate(
    links: Iterable[dict[str, Any]],
    balances: dict[str, Decimal],
    delinquent: set[str],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """``links``: linhas {certificado, tipo, cnpj, percentual, kind}. ``balances``: saldo por certificado.
    ``delinquent``: certificados com alguma série em atraso. Devolve devedores ordenados por exposição e contadores."""

    stats = {"vinculos": 0, "cnpj_invalido": 0, "percentual_invalido": 0}
    seen: set[tuple[str, str]] = set()
    debtors: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "cnpj": "", "certificados": set(), "em_atraso": set(), "exposicao": Decimal(0), "tipos": set(),
    })
    for link in links:
        if link.get("tipo") != "Devedor":
            continue
        stats["vinculos"] += 1
        cnpj = normalize_cnpj(link.get("cnpj"))
        if cnpj is None:
            stats["cnpj_invalido"] += 1
            continue
        cert = link["certificado"]
        if (cnpj, cert) in seen:
            continue
        seen.add((cnpj, cert))
        share = fraction(link.get("percentual"))
        if share is None:
            stats["percentual_invalido"] += 1
        item = debtors[cnpj]
        item["cnpj"] = cnpj
        item["certificados"].add(cert)
        item["tipos"].add(link.get("kind", ""))
        if cert in delinquent:
            item["em_atraso"].add(cert)
        if share is not None:
            item["exposicao"] += share * balances.get(cert, Decimal(0))
    ranking = []
    for item in debtors.values():
        item["contagio"] = bool(item["em_atraso"]) and len(item["certificados"]) > len(item["em_atraso"])
        ranking.append(item)
    ranking.sort(key=lambda i: (-i["exposicao"], i["cnpj"]))
    return ranking, stats


def format_cnpj(digits: str) -> str:
    return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"
