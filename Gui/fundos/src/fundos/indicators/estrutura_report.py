"""Linhas do relatorio de estrutura: carteira por segmento e garantias (FU11.4).

So contagens: nunca CNPJ, nome nem valor de linha. Os intervalos do maior
segmento, do HHI e do percentual das garantias sao intervalos de contagem,
sem limiar: nao classificam a concentracao nem a garantia. A subordinacao
(tambem do grupo D4) tem o seu proprio relatorio.
"""

from collections import Counter
from decimal import Decimal

from fundos.indicators import garantias as guarantee
from fundos.indicators import segmentos as segment
from fundos.indicators.values import NO_DATA
from fundos.indicators.values import PRESENT


NONZERO = ("0", "1", "2", "3", "4", "5 ou mais")

# (rotulo, de, ate): de <= valor < ate; None = sem limite.
LARGEST_INTERVALS = (
    ("100% ou mais", Decimal(100), None),
    ("de 90% a menos de 100%", Decimal(90), Decimal(100)),
    ("de 50% a menos de 90%", Decimal(50), Decimal(90)),
    ("menos de 50%", None, Decimal(50)),
)
HHI_INTERVALS = (
    ("10.000 ou mais", Decimal(10000), None),
    ("de 5.000 a menos de 10.000", Decimal(5000), Decimal(10000)),
    ("de 2.500 a menos de 5.000", Decimal(2500), Decimal(5000)),
    ("menos de 2.500", None, Decimal(2500)),
)

VALUE_GROUPS = ("maior que 0", "igual a 0", "negativo", NO_DATA)
PERCENT_GROUPS = ("igual a 0", "maior que 0 e ate 100", "acima de 100", "negativo", NO_DATA)

PERCENT_NOTE = "O percentual e informado; nao e calculado a partir do valor."
SUBORDINATION_NOTE = "Subordinacao (D4): veja scripts/report_subordinacao.py."


def interval(value, intervals):
    """O rotulo do intervalo de contagem do valor."""

    for label, low, high in intervals:
        if (low is None or value >= low) and (high is None or value < high):
            return label

    raise ValueError("Valor fora dos intervalos.")


def _nonzero(count):
    return NONZERO[-1] if count >= 5 else str(count)


def _value_group(field_value):
    if field_value.state != PRESENT:
        return NO_DATA

    if field_value.value > 0:
        return "maior que 0"

    return "igual a 0" if field_value.value == 0 else "negativo"


def _percent_group(field_value):
    if field_value.state != PRESENT:
        return NO_DATA

    if field_value.value < 0:
        return "negativo"

    if field_value.value == 0:
        return "igual a 0"

    return "maior que 0 e ate 100" if field_value.value <= 100 else "acima de 100"


def _counts(labels, counter):
    return "; ".join(label + " " + str(counter[label]) for label in labels)


def format_segment_report(results, reference_date):
    """A parte da carteira por segmento, em linhas (so contagens)."""

    states = Counter(item.state for item in results)
    reasons = Counter(item.reason for item in results if item.reason is not None)
    flags = Counter(flag for item in results for flag in item.flags)
    calculated = [item for item in results if item.state == segment.CALCULATED]
    concentrated = [item for item in calculated if item.hhi is not None]

    lines = [
        "Carteira por segmento (tab_II; calculada na leitura; nada e gravado):",
        "  Competencia: " + reference_date,
        "  Base do %: " + segment.BASE,
        "  Assuntos: " + str(len(results)),
    ]

    for state in segment.STATES:
        lines.append("    " + state + ": " + str(states[state]))

    for reason in sorted(reasons):
        lines.append("      " + NO_DATA + "/" + reason + ": " + str(reasons[reason]))

    lines.append("  Marcas:")

    for flag in segment.FLAGS:
        lines.append("    " + flag + ": " + str(flags[flag]))

    nonzero = Counter(_nonzero(item.nonzero_count) for item in calculated)
    lines.append(
        "  Segmentos de topo diferentes de 0 (calculados; " + str(len(calculated))
        + " assunto(s)): " + _counts(NONZERO, nonzero)
    )

    largest = Counter(
        interval(item.largest.share.value, LARGEST_INTERVALS)
        for item in concentrated
        if item.largest is not None
    )
    lines.append(
        "  Maior segmento, % do total, intervalos de contagem, sem limiar (calculados sem "
        "segmento negativo; " + str(sum(largest.values())) + " assunto(s)): "
        + _counts([label for label, _, _ in LARGEST_INTERVALS], largest)
    )

    hhi = Counter(interval(item.hhi, HHI_INTERVALS) for item in concentrated)
    lines.append(
        "  HHI nos 11 segmentos de topo, intervalos de contagem, sem limiar (calculados sem "
        "segmento negativo; " + str(len(concentrated)) + " assunto(s)): "
        + _counts([label for label, _, _ in HHI_INTERVALS], hhi)
    )

    lines.append("  Por segmento de topo, assuntos com valor maior que 0 (todos os assuntos):")

    for item_name, name, _, _ in segment.SEGMENTS:
        count = sum(
            1
            for item in results
            if item.segment(item_name).amount.state == PRESENT
            and item.segment(item_name).amount.value > 0
        )
        lines.append("    " + item_name + " " + name + ": " + str(count))

    return lines


def format_guarantee_report(results, reference_date):
    """A parte das garantias, em linhas (so contagens)."""

    flags = Counter(flag for item in results for flag in item.flags)
    values = Counter(_value_group(item.value) for item in results)
    percents = Counter(_percent_group(item.percent) for item in results)

    lines = [
        "Garantias (tab_X_7; como informadas; nada e calculado entre os dois campos):",
        "  Competencia: " + reference_date,
        "  " + guarantee.VALUE_ITEM + " " + guarantee.VALUE + ": " + guarantee.VALUE_NAME
        + " (" + guarantee.CORRESPONDENCE + ")",
        "  " + guarantee.PERCENT_ITEM + " " + guarantee.PERCENT + ": " + guarantee.PERCENT_NAME
        + " (" + guarantee.CORRESPONDENCE + ")",
        "  Assuntos com a linha: " + str(len(results)),
        "  Valor (" + guarantee.VALUE_ITEM + "): " + _counts(VALUE_GROUPS, values),
        "  Percentual (" + guarantee.PERCENT_ITEM + "): " + _counts(PERCENT_GROUPS, percents),
        "  Marcas:",
    ]

    for flag in guarantee.FLAGS:
        lines.append("    " + flag + ": " + str(flags[flag]))

    lines.append("  " + PERCENT_NOTE)

    return lines


def format_estrutura_report(segment_results, guarantee_results, reference_date):
    """O relatorio inteiro, em linhas (so contagens)."""

    return (
        format_segment_report(segment_results, reference_date)
        + format_guarantee_report(guarantee_results, reference_date)
        + [SUBORDINATION_NOTE]
    )
