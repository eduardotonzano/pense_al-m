"""Relatorio de FIC-FIDC, da conferencia do CDA e da fila: so contagens.

Nunca traz CNPJ, nome nem valor de linha: so a regra, os campos, as
competencias, a tolerancia e contagens por faixa, estado, motivo e marca.
A contagem descreve o que esta no banco: um tipo com 0 detentores nao
quer dizer que o tipo nao exista no CDA da CVM.
"""

from collections import Counter

from fundos.fic_fidc import cda_check
from fundos.fic_fidc import classification as rule
from fundos.fic_fidc.review_queue import ACTION
from fundos.fic_fidc.review_queue import DECISION_SOURCE
from fundos.fic_fidc.review_queue import ENTITY_TYPES
from fundos.fic_fidc.review_queue import STALE
from fundos.indicators.values import NO_DATA


NO_TYPE = "sem tipo no cadastro"
NO_CLASSIFICATION = "sem classificacao (assunto so no CDA)"
HOLDER_TYPES = ("FIDC", "FIAGRO")


def _joined(values):
    return ", ".join(values) if values else "nenhuma"


def _reasons(counter, indent):
    return [indent + reason + ": " + str(counter[reason]) for reason in sorted(counter)]


def format_classification_report(classifications, reference_date, informe_competences):
    """Linhas da classificacao: regra, campos, competencias e contagens."""

    lines = [
        "Classificacao de FIC-FIDC (calculada na leitura; nada e gravado):",
        "  Regra: " + rule.RULE_TEXT,
        "  Campos: " + rule.NUMERATOR + " (numerador) e " + rule.DENOMINATOR + " (denominador)",
        "  Competencia pedida: " + reference_date,
        "  Competencias do informe de FIDC no banco: " + _joined(informe_competences),
    ]

    if not classifications:
        lines.append(
            "  Informe de FIDC: sem dado nesta competencia (nenhum assunto com a tab_I); "
            "nada classificado."
        )
        return lines

    sources = Counter(
        part.source_code
        for item in classifications
        for amount in (item.numerator, item.denominator)
        for part in amount.parts
        if part.source_code is not None
    )
    bands = Counter(item.band for item in classifications)
    reasons = Counter(item.reason for item in classifications if item.reason is not None)
    flags = Counter(flag for item in classifications for flag in item.flags)
    types = Counter(item.cadastro_type or NO_TYPE for item in classifications)

    lines.append(
        "  Fontes dos numeros: "
        + _joined([code + " " + str(sources[code]) for code in sorted(sources)])
    )
    lines.append("  Assuntos: " + str(len(classifications)))

    for band in rule.BANDS:
        lines.append("    " + rule.LABELS[band] + ": " + str(bands[band]))

    lines.extend(_reasons(reasons, "      sem dado, "))
    lines.append("  Marcas:")

    for flag in rule.FLAGS:
        lines.append("    " + flag + ": " + str(flags[flag]))

    lines.append(
        "  Tipo do assunto no cadastro: "
        + "; ".join(label + " " + str(types[label]) for label in sorted(types))
    )

    return lines


def format_check_report(checks, reference_date, competences, tolerance=cda_check.TOLERANCE):
    """Linhas da conferencia do CDA com a tab_I: competencias, estados e detentores."""

    lines = [
        "Conferencia do CDA com a tab_I (calculada na leitura; a divergencia e nota "
        "de qualidade e nada e gravado):",
        "  Soma de " + cda_check.CDA_FIELD + " dos investidos FIDC no cadastro contra "
        + cda_check.INFORME_FIELD + ", sempre na mesma competencia",
        "  Tolerancia: " + tolerance.text,
        "  Competencia conferida: " + reference_date,
    ]

    if competences is None:
        lines.append("  Competencias do CDA no banco: holdings nao existe neste banco (migration 004)")
    else:
        lines.append("  Competencias do CDA no banco: " + _joined(competences))

    states = Counter(item.state for item in checks)
    reasons = Counter(item.reason for item in checks if item.reason is not None)
    flags = Counter(flag for item in checks for flag in item.flags)
    lines.append("  Assuntos: " + str(len(checks)))

    for state in cda_check.STATES:
        lines.append("    " + state + ": " + str(states[state]))

    lines.extend(_reasons(reasons, "      " + NO_DATA + "/"))
    lines.append("  Marcas:")

    for flag in cda_check.FLAGS:
        lines.append("    " + flag + ": " + str(flags[flag]))

    holders = Counter()
    holder_lines = Counter()

    for item in checks:
        if item.cda_lines:
            label = item.holder_type or NO_TYPE
            holders[label] += 1
            holder_lines[label] += item.cda_lines

    lines.append(
        "  Detentores com posicao no CDA desta competencia, por tipo no cadastro "
        "(contagem do que esta neste banco, sem concluir a causa de um 0):"
    )

    for label in HOLDER_TYPES + tuple(sorted(set(holders) - set(HOLDER_TYPES))):
        lines.append(
            "    " + label + ": " + str(holders[label]) + " detentor(es), "
            + str(holder_lines[label]) + " linha(s)"
        )

    return lines


def _check_key(item):
    if item.reason is not None:
        return item.state + "/" + item.reason

    return item.state


def format_cross_report(classifications, checks):
    """Cruzamento, em assuntos: faixa da classificacao x estado da conferencia."""

    bands = {(item.subject.kind, item.subject.id): item.band for item in classifications}
    table = {}

    for item in checks:
        band = bands.get((item.subject.kind, item.subject.id))
        label = NO_CLASSIFICATION if band is None else rule.LABELS[band]
        table.setdefault(label, Counter())[_check_key(item)] += 1

    lines = ["Cruzamento faixa da classificacao x estado da conferencia (assuntos):"]

    for label in [rule.LABELS[band] for band in rule.BANDS] + [NO_CLASSIFICATION]:
        counter = table.get(label, Counter())
        within = counter[cda_check.WITHIN]
        outside = counter[cda_check.OUTSIDE_TOLERANCE]
        no_data = sorted(key for key in counter if key.startswith(NO_DATA + "/"))
        parts = [
            cda_check.WITHIN + " " + str(within),
            cda_check.OUTSIDE_TOLERANCE + " " + str(outside),
        ] + [key + " " + str(counter[key]) for key in no_data]
        lines.append("  " + label + ": " + "; ".join(parts))

    return lines


def format_queue_report(new, already, queued_reviews, committed=None):
    """Linhas da fila: o que ja esta nela, o que entraria e, no commit, o gravado."""

    stale = sum(1 for item in queued_reviews if STALE in item.flags)
    by_type = Counter(item.entity_type for item in queued_reviews)
    lines = [
        "Fila de revisao manual (audit_log, acao " + ACTION + "; fonte da decisao "
        + DECISION_SOURCE + "):",
        "  Ja na fila nesta competencia: "
        + str(len(queued_reviews))
        + " assunto(s) ("
        + "; ".join(t + " " + str(by_type[t]) for t in sorted(set(ENTITY_TYPES.values())))
        + "), "
        + str(sum(item.entries for item in queued_reviews))
        + " linha(s), "
        + str(stale)
        + " com "
        + STALE,
        "  Em revisao manual e ja na fila (mesma evidencia): " + str(len(already)),
    ]

    if committed is None:
        lines.append("  Entrariam agora: " + str(len(new)))
    else:
        lines.append("  Gravadas agora: " + str(len(committed.created)))

    return lines
