"""Exposição por devedor no mercado inteiro de CRA/CRI e sinal de contágio (dados abertos da CVM).

A tabela ``*_cedente_devedor`` do Informe traz, por certificado, o CNPJ dos devedores (e cedentes) que
representam mais de 20% dos créditos e o percentual. Aqui:
  - o CNPJ, numérico ou alfanumérico (IN RFB 2.229/2024, regra em credit_assets.cnpj), é normalizado e validado
    pelos dígitos verificadores; o que não é CNPJ fica de fora e é contado por motivo: não informado (vazio, "0",
    "NA"), CPF de pessoa física (contado, nunca exibido) ou inválido; CNPJ numérico com 12 ou 13 dígitos que perdeu
    os zeros à esquerda só é aceito se os dígitos verificadores baterem e se o valor não tiver letra;
  - a exposição estimada é percentual × saldo dos certificados da emissão no mês;
  - "contágio" = devedor com alguma emissão em atraso e outra emissão ainda adimplente.
CNPJ é o identificador forte (regra 6 do projeto): nada é unido por nome.
"""
from __future__ import annotations

import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from credit_assets import cnpj as cnpj_rule


def _has_letter(text: str) -> bool:
    return any(character.isalpha() for character in text)


def _rule(value: str) -> str | None:
    try:
        return cnpj_rule.normalize_cnpj(value)
    except ValueError:
        return None


def normalize_cnpj(value: str | None) -> str | None:
    """CNPJ canônico de 14 caracteres (numérico ou alfanumérico, em maiúsculas) ou None.

    Valor sem letra: como antes, só os dígitos, e eles passam pela regra de credit_assets.cnpj.
    Valor com letra: primeiro a regra inteira (tira só ponto, barra e hífen; maiúsculas; DV); senão, se sobram
    exatamente 14 dígitos ASCII (ex.: "CNPJ 01.486.546/0001-67"), esses 14 pela mesma regra. Um CNPJ alfanumérico
    tem no máximo 13 dígitos, então esses 14 nunca vêm só dele. Nunca completa zeros."""

    text = value if isinstance(value, str) else ""
    if not _has_letter(text):
        return _rule(re.sub(r"\D", "", text))
    canonical = _rule(text)
    if canonical:
        return canonical
    digits = re.sub(r"[^0-9]", "", text)
    return _rule(digits) if len(digits) == 14 else None


def _is_cpf(digits: str) -> bool:
    if len(digits) != 11 or len(set(digits)) == 1:
        return False
    for size in (9, 10):
        total = sum(int(d) * (size + 1 - i) for i, d in enumerate(digits[:size]))
        if total * 10 % 11 % 10 != int(digits[size]):
            return False
    return True


def classify_identifier(value: str | None) -> tuple[str, str | None]:
    """Identificador de devedor do Informe: ("cnpj" | "cnpj_sem_zeros", CNPJ canônico), ("cpf", None),
    ("nao_informado", None) ou ("invalido", None). CPF não é devolvido: não sai em relatório.

    Valor com letra só pode ser "cnpj" (ver normalize_cnpj), "nao_informado" ou "invalido": nunca completa zeros
    nem vira CPF, porque tirar as letras de um CNPJ alfanumérico deixa 12 ou 13 dígitos que podem formar, por
    acaso, o CNPJ numérico de outra empresa. Valor sem letra: como antes."""

    text = value if isinstance(value, str) else ""
    cnpj = normalize_cnpj(text)
    if cnpj:
        return "cnpj", cnpj
    digits = re.sub(r"\D", "", text)
    if not digits or (len(digits) <= 2 and set(digits) <= {"0", "1"}) or len(set(digits)) == 1:
        return "nao_informado", None  # vazio, "0", "NA", "00000000000000", "99.999.999/9999-99"
    if _has_letter(text):
        return "invalido", None
    if len(digits) in (12, 13) and (padded := normalize_cnpj(digits.zfill(14))):
        return "cnpj_sem_zeros", padded
    if _is_cpf(digits):
        return "cpf", None
    return "invalido", None


def informed_cnpj(value: str | None) -> str | None:
    """CNPJ de um campo do Informe da CVM (aceita o que perdeu os zeros à esquerda, com dígitos verificadores)."""

    kind, digits = classify_identifier(value)
    return digits if kind in ("cnpj", "cnpj_sem_zeros") else None


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
    ``delinquent``: certificados com alguma série em atraso. Devolve devedores ordenados por exposição e contadores.

    Unidade dos contadores: ``vinculos``, ``nao_informado``, ``cpf``, ``cnpj_invalido``, ``cnpj_sem_zeros`` e
    ``cnpj_alfanumerico`` contam vínculos de devedor (linhas), antes de deduplicar por certificado;
    ``cnpj_alfanumerico`` conta o vínculo cujo CNPJ devolvido (canônico) tem letra, e esse CNPJ também entra no
    ranking. ``percentual_invalido`` conta pares (CNPJ, certificado) já deduplicados."""

    stats = {"vinculos": 0, "nao_informado": 0, "cpf": 0, "cnpj_invalido": 0, "cnpj_sem_zeros": 0,
             "cnpj_alfanumerico": 0, "percentual_invalido": 0}
    seen: set[tuple[str, str]] = set()
    debtors: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "cnpj": "", "certificados": set(), "em_atraso": set(), "exposicao": Decimal(0), "tipos": set(),
    })
    for link in links:
        if link.get("tipo") != "Devedor":
            continue
        stats["vinculos"] += 1
        kind, cnpj = classify_identifier(link.get("cnpj"))
        if cnpj is None:
            stats["cnpj_invalido" if kind == "invalido" else kind] += 1
            continue
        if kind == "cnpj_sem_zeros":
            stats["cnpj_sem_zeros"] += 1
        if re.search(r"[A-Z]", cnpj):
            stats["cnpj_alfanumerico"] += 1
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
