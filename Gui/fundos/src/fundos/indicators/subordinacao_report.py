"""Linhas do relatorio da subordinacao: so contagens (FU6.3).

Nunca traz CNPJ, nome nem valor de linha: a formula, a competencia, o mapa
e contagens por estado, motivo e marca, a conferencia com o PL, as faixas
da subordinacao e a divisao do valor das series (em %, com 1 casa so na
exibicao). As faixas e a divisao seguem a secao 10.6 de
docs/fundos-descoberta.md: assuntos calculados cuja soma das series fecha
com o PL a ate 1%; as faixas, so os com 2 ou mais series.
"""

from collections import Counter
from decimal import ROUND_HALF_EVEN
from decimal import Decimal

from fundos.indicators import subordinacao as rule
from fundos.indicators.values import NO_DATA
from fundos.quota_classes.mapping import ABSENT


BANDS = (
    ("0", None, Decimal(0)),
    ("abaixo de 5%", Decimal(0), Decimal(5)),
    ("de 5% a 10%", Decimal(5), Decimal(10)),
    ("de 10% a 20%", Decimal(10), Decimal(20)),
    ("de 20% a 30%", Decimal(20), Decimal(30)),
    ("de 30% a 50%", Decimal(30), Decimal(50)),
    ("50% ou mais", Decimal(50), None),
)

_ONE_PLACE = Decimal("0.1")


def _band(value):
    if value == 0:
        return BANDS[0][0]

    for label, low, high in BANDS[1:]:
        above = value > low if low == 0 else value >= low

        if above and (high is None or value < high):
            return label

    return BANDS[-1][0]


def _percent(part, total):
    if total == 0:
        return "-"

    return str((part / total * 100).quantize(_ONE_PLACE, rounding=ROUND_HALF_EVEN)) + "%"


def format_subordinacao_report(results, reference_date):
    """O relatorio inteiro, em linhas (so contagens)."""

    states = Counter(item.state for item in results)
    reasons = Counter(item.reason for item in results if item.reason is not None)
    flags = Counter(flag for item in results for flag in item.flags)
    checks = Counter(item.pl_check for item in results if item.pl_check is not None)
    reviews = Counter(item.map_review for item in results if item.map_review is not None)
    calculated = [item for item in results if item.state == rule.CALCULATED]

    lines = [
        "Subordinacao das classes de FIDC (calculada na leitura; nada e gravado):",
        "  Formula: " + rule.FORMULA,
        "  Competencia: " + reference_date,
        "  Mapa das series (quota_class_map), situacao das regras usadas: "
        + "; ".join(name + " " + str(reviews[name]) for name in ("revisado", "proposto")),
        "  Assuntos: " + str(len(results)),
    ]

    for state in rule.STATES:
        lines.append("    " + state + ": " + str(states[state]))

    for reason in sorted(reasons):
        lines.append("      " + NO_DATA + "/" + reason + ": " + str(reasons[reason]))

    lines.append("  Marcas:")

    for flag in rule.FLAGS:
        lines.append("    " + flag + ": " + str(flags[flag]))

    lines.append(
        "  Conferencia com o PL (" + rule.PL + ", 1% puro): "
        + "; ".join(check + " " + str(checks[check]) for check in rule.PL_CHECKS)
    )

    single_senior = sum(
        1 for item in calculated if len(item.series) == 1 and rule.NO_SUBORDINATE in item.flags
    )
    absent_series = sum(
        1 for item in results for line in item.series if line.subtype == ABSENT
    )
    lines.append("  Assuntos calculados com uma so serie, senior: " + str(single_senior))
    lines.append("  Series com subtipo ausente: " + str(absent_series))

    closing = [item for item in calculated if item.pl_check == rule.WITHIN_1PCT]
    banded = Counter(
        _band(item.subordinacao_total.value) for item in closing if len(item.series) >= 2
    )
    lines.append(
        "  Faixas da subordinacao (calculados que fecham com o PL a ate 1%, com 2 ou mais series; "
        + str(sum(banded.values())) + " assunto(s)): "
        + "; ".join(label + " " + str(banded[label]) for label, _, _ in BANDS)
    )

    totals = Counter()

    for item in closing:
        for part in item.parts:
            totals[part.name] += part.value

    grand_total = sum(totals.values(), Decimal(0))
    lines.append(
        "  Divisao do valor das series (calculados que fecham com o PL a ate 1%; "
        + str(len(closing)) + " assunto(s)): "
        + "; ".join(name + " " + _percent(totals[name], grand_total) for name in rule.PARTS)
        + "; subordinada e subtipo ausente juntos "
        + _percent(totals[rule.PART_SUBORDINATE] + totals[rule.PART_ABSENT], grand_total)
    )

    return lines
