"""Linhas do relatorio de desempenho: liquidez, rentabilidade e desempenho (FU11.5).

So contagens: nunca CNPJ, nome nem valor de linha. Os intervalos dos
valores da tab_X_3 e da tab_X_6 sao intervalos de contagem, sem limiar: nao
classificam a serie. A unidade desses valores nao e confirmada, e por isso
nenhuma linha traz o sinal de percentual junto deles.
"""

from collections import Counter

from fundos.indicators import desempenho as performance
from fundos.indicators import liquidez as liquidity
from fundos.indicators import rentabilidade as monthly_return
from fundos.indicators.values import NO_DATA
from fundos.indicators.values import PRESENT
from fundos.indicators.values import REASON_MISSING


GROUPS = ("maior que 0", "igual a 0", "menor que 0", NO_DATA)

INTERVALS = (
    "menos de -10",
    "de -10 a menos de 0",
    "igual a 0",
    "mais de 0 ate 1",
    "mais de 1 ate 2",
    "mais de 2 ate 10",
    "mais de 10",
)

UNIT_NOTE = "unidade nao confirmada; o valor e mostrado como informado"
NO_CALCULATION_NOTE = "Nada e calculado entre o esperado e o realizado."


def interval(value):
    """O intervalo de contagem do valor informado (sem limiar)."""

    if value < -10:
        return INTERVALS[0]

    if value < 0:
        return INTERVALS[1]

    if value == 0:
        return INTERVALS[2]

    if value <= 1:
        return INTERVALS[3]

    if value <= 2:
        return INTERVALS[4]

    if value <= 10:
        return INTERVALS[5]

    return INTERVALS[6]


def group(field_value):
    """maior que 0, igual a 0, menor que 0 ou sem_dado."""

    if field_value.state != PRESENT:
        return NO_DATA

    if field_value.value > 0:
        return GROUPS[0]

    return GROUPS[1] if field_value.value == 0 else GROUPS[2]


def _counts(labels, counter):
    return "; ".join(label + " " + str(counter[label]) for label in labels)


def _intervals(values):
    counter = Counter(interval(value.value) for value in values if value.state == PRESENT)
    return _counts(INTERVALS, counter)


def _flags(lines, names, results):
    counter = Counter(flag for item in results for flag in item.flags)
    lines.append("  Marcas:")

    for name in names:
        lines.append("    " + name + ": " + str(counter[name]))


def format_liquidity_report(results, reference_date):
    """A parte da liquidez (tab_X_5), em linhas (so contagens)."""

    lines = [
        "Liquidez (tab_X_5; como informada; nada e somado nem dividido):",
        "  Competencia: " + reference_date,
        "  Nota: " + liquidity.NOTE,
        "  Assuntos: " + str(len(results)),
        "  Por faixa (" + "; ".join(GROUPS) + "):",
    ]

    for label, _ in liquidity.BUCKETS:
        counter = Counter(group(item.bucket(label)) for item in results)
        lines.append("    " + label + ": " + _counts(GROUPS, counter))

    _flags(lines, liquidity.FLAGS, results)
    return lines


def format_return_report(results, reference_date):
    """A parte da rentabilidade (tab_X_3), em linhas (so contagens)."""

    values = [line.value for item in results for line in item.series]
    reasons = Counter(value.reason for value in values if value.state != PRESENT)
    lines = [
        "Rentabilidade (" + monthly_return.FIELD + ", \"" + monthly_return.OFFICIAL_NAME
        + "\"; por serie; como informada):",
        "  Competencia: " + reference_date,
        "  Unidade: " + UNIT_NOTE,
        "  Assuntos: " + str(len(results)) + "; series: " + str(len(values)),
        "  Valor: " + _counts(GROUPS, Counter(group(value) for value in values)),
    ]

    for reason in sorted(reasons):
        lines.append("    " + NO_DATA + "/" + reason + ": " + str(reasons[reason]))

    lines.append("  Intervalos de contagem do valor, sem limiar: " + _intervals(values))
    _flags(lines, monthly_return.FLAGS, [line for item in results for line in item.series])
    return lines


def format_performance_report(results, reference_date):
    """A parte do desempenho esperado e realizado (tab_X_6), em linhas (so contagens)."""

    series = [line for item in results for line in item.series]
    expected = [line.expected for line in series]
    realized = [line.realized for line in series]
    comparison = Counter()

    for line in series:
        if line.monthly_return.state != PRESENT and line.monthly_return.reason == REASON_MISSING:
            comparison["sem tab_X_3"] += 1
        elif line.realized.state != PRESENT or line.monthly_return.state != PRESENT:
            comparison["algum sem dado"] += 1
        elif line.realized.value == line.monthly_return.value:
            comparison["igual"] += 1
        else:
            comparison["diferente"] += 1

    lines = [
        "Desempenho esperado e realizado (tab_X_6; por serie; como informados):",
        "  Competencia: " + reference_date,
        "  " + performance.EXPECTED + ": " + performance.EXPECTED_NAME
        + " (" + performance.CORRESPONDENCE + ")",
        "  " + performance.REALIZED + ": " + performance.REALIZED_NAME
        + " (" + performance.CORRESPONDENCE + ")",
        "  Unidade: " + UNIT_NOTE,
        "  " + NO_CALCULATION_NOTE,
        "  Assuntos: " + str(len(results)) + "; series: " + str(len(series)),
        "  Esperado: " + _counts(GROUPS, Counter(group(value) for value in expected)),
        "  Realizado: " + _counts(GROUPS, Counter(group(value) for value in realized)),
        "  Intervalos de contagem do esperado, sem limiar: " + _intervals(expected),
        "  Intervalos de contagem do realizado, sem limiar: " + _intervals(realized),
        "  Realizado contra " + monthly_return.FIELD + " da mesma serie: "
        + _counts(("igual", "diferente", "sem tab_X_3", "algum sem dado"), comparison),
    ]

    _flags(lines, performance.FLAGS, series)
    return lines


def format_desempenho_report(liquidity_results, return_results, performance_results, reference_date):
    """O relatorio inteiro, em linhas (so contagens)."""

    return (
        format_liquidity_report(liquidity_results, reference_date)
        + format_return_report(return_results, reference_date)
        + format_performance_report(performance_results, reference_date)
    )
