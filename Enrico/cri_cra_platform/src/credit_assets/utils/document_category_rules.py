"""Classificador estrito de categoria de documento (CRI/CRA).

So troca a categoria com correspondencia inequivoca: exatamente uma categoria
candidata. Nenhuma regra, ou regras de categorias diferentes, resultam em
"Outro". Frases ancoradas, nunca substring solta.

As regras ficam em dois grupos:

- ``verified``: tem evidencia real (linhas da grade do Fundos.NET) e vale por
  padrao;
- ``unverified``: linguisticamente ancorada, mas sem nenhum exemplo real nos
  dados disponiveis. Fica desligada e so vale com ``include_unverified=True``
  (``--enable-unverified-rules`` em scripts/reclassify_documents.py).

Este modulo nao importa Playwright e nao substitui ``classify_document``, que
segue servindo a escolha de amostras do download.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Mapping

CLASSIFIER_VERSION = "1.0.0"
VERIFIED = "verified"
UNVERIFIED = "unverified"
OTHER = "Outro"

# Papel de cada campo -> chaves aceitas (grade oficial, apelidos antigos e
# colunas do banco). A primeira chave preenchida de cada papel vale.
FIELD_ALIASES = {
    "category": (
        "categoriaDocumento", "categoria_documento", "categoria",
        "source_category",
    ),
    "type": (
        "tipoDocumento", "tipo_documento", "live_type", "tipo", "source_type",
    ),
    "species": (
        "especieDocumento", "especie_documento", "live_species",
        "source_species",
    ),
    "name": ("document_name", "nome_documento", "titulo", "nome", "descricao"),
}


def fold(value: object) -> str:
    """Minusculas e sem acentos, para comparar frases."""

    folded = unicodedata.normalize("NFKD", str(value).casefold())
    return "".join(
        character for character in folded if not unicodedata.combining(character)
    )


@dataclass(frozen=True)
class Rule:
    rule_id: str
    category: str
    group: str
    roles: tuple[str, ...]
    pattern: re.Pattern
    unless: re.Pattern | None = None


def _rule(rule_id, category, group, roles, pattern, unless=None) -> Rule:
    return Rule(
        rule_id,
        category,
        group,
        tuple(roles),
        re.compile(pattern),
        re.compile(unless) if unless else None,
    )


# Veto: evidencia explicita de que o documento NAO e de uma categoria
# especifica. Resulta em "Outro" e tambem acusa classificacoes antigas erradas.
VETOES = (
    _rule(
        "DF-VETO-01", OTHER, VERIFIED, ("type", "name", "species"),
        r"\bdemonstracoes?\s+financeiras?\b",
    ),
)

RULES = (
    # --- grupo verificado -------------------------------------------------
    _rule(
        "IM-01", "Informe Mensal", VERIFIED, ("type", "name"),
        r"\binforme\s+mensal\b",
    ),
    _rule("ATA-ESP-01", "Ata/Edital", VERIFIED, ("species",), r"\bata\b"),
    _rule("EDT-ESP-01", "Ata/Edital", VERIFIED, ("species",), r"\bedital\b"),
    # --- grupo nao verificado (sem exemplo real) --------------------------
    _rule(
        "ADT-01", "Aditamento", UNVERIFIED, ("type", "name", "species"),
        r"\baditamento\b",
    ),
    _rule(
        "TS-01", "Termo de Securitização", UNVERIFIED,
        ("type", "name", "species"),
        r"\btermo\s+de\s+securitizacao\b",
        unless=r"\baditamento\b",
    ),
    _rule(
        "FR-01", "Fato Relevante", UNVERIFIED, ("type", "name", "species"),
        r"\bfato\s+relevante\b",
    ),
    _rule(
        "AF-01", "Relatório Agente Fiduciário", UNVERIFIED,
        ("type", "name", "species"),
        r"\brelatorio\s+(?:anual\s+)?(?:do\s+|de\s+)?agente\s+fiduciario\b",
    ),
    _rule(
        "RT-01", "Relatório de Rating", UNVERIFIED, ("type", "name", "species"),
        r"\brelatorio\s+de\s+(?:rating|classificacao\s+de\s+risco)\b",
    ),
    _rule(
        "AE-01", "Anúncio de Encerramento", UNVERIFIED,
        ("type", "name", "species"),
        r"\banuncio\s+de\s+encerramento\b",
    ),
)


@dataclass(frozen=True)
class Classification:
    category: str
    rule_id: str | None = None
    group: str | None = None
    matched_field: str | None = None
    matched_value: str | None = None
    candidates: tuple[str, ...] = ()
    ambiguous: bool = False
    vetoed: bool = False


def field_values(fields: Mapping[str, object]) -> dict[str, str]:
    """Texto original de cada papel (categoria, tipo, especie, nome)."""

    values = {}

    for role, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            value = fields.get(alias)

            if value is not None and str(value).strip():
                values[role] = str(value).strip()
                break

    return values


def _match(rule: Rule, values: Mapping[str, str]) -> tuple[str, str] | None:
    for role in rule.roles:
        text = values.get(role)

        if not text:
            continue

        folded = fold(text)

        if rule.pattern.search(folded) and not (
            rule.unless and rule.unless.search(folded)
        ):
            return role, text

    return None


def classify_strict(
    fields: Mapping[str, object],
    include_unverified: bool = False,
) -> Classification:
    """Categoria so se exatamente uma candidata casar; senao "Outro"."""

    values = field_values(fields)

    for veto in VETOES:
        hit = _match(veto, values)

        if hit is not None:
            return Classification(
                OTHER, veto.rule_id, veto.group, hit[0], hit[1], vetoed=True
            )

    hits = []

    for rule in RULES:
        if rule.group == UNVERIFIED and not include_unverified:
            continue

        hit = _match(rule, values)

        if hit is not None:
            hits.append((rule, hit))

    if not hits:
        return Classification(OTHER)

    candidates = tuple(dict.fromkeys(rule.category for rule, _ in hits))

    if len(candidates) > 1:
        return Classification(OTHER, candidates=candidates, ambiguous=True)

    rule, (role, value) = hits[0]

    return Classification(
        rule.category, rule.rule_id, rule.group, role, value, candidates
    )
