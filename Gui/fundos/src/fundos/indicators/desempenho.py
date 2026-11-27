"""Desempenho esperado e realizado, por serie (tab_X_6), como informados (FU11.5).

Sao os dois campos da tab_X_6, ligados ao item "6) Desempenho Esperado
(Benchmark) e o Realizado" do modelo do Suplemento G da Resolucao CVM 175
(Suplemento G, correspondencia pelo nome do campo; o dicionario de dados da
CVM nao descreve os dois campos):
- TAB_X_PR_DESEMP_ESPERADO: "Desempenho Esperado (Benchmark)";
- TAB_X_PR_DESEMP_REAL: "Desempenho Realizado (Rentabilidade no Mes)".

Cada serie sai com os dois valores como informados, com fonte, competencia,
observacao e coleta, e estado presente ou sem_dado (com o motivo). A unidade
nao e confirmada: o prefixo PR do nome sugere percentual, sem confirmacao.
Nada e calculado entre os dois campos: nem diferenca nem razao. Tambem nao
se sabe se o esperado e a meta do regulamento ou o benchmark do mes.

Conferencia, sem conta: o Suplemento chama o realizado de "Rentabilidade
no Mes". Por isso cada serie traz tambem a tab_X_3.TAB_X_VL_RENTAB_MES da
mesma serie e competencia, e a marca diz quando os dois valores informados
sao diferentes.

Marcas, por serie:
- esperado_informado_zero: o esperado informado e 0 (pode ser "nao
  preenchido"; a marca nao afirma nada);
- esperado_negativo;
- realizado_difere_da_rentabilidade: realizado e tab_X_3 presentes e
  diferentes;
- conflito_aberto: algum dos tres campos tem conflito aberto no banco.

Calculado na leitura; nada e gravado.
"""

from dataclasses import dataclass

from fundos.database import normalize_iso_date
from fundos.indicators import rentabilidade as monthly_return
from fundos.indicators.reading import previous_month_end
from fundos.indicators.reading import read_series_competence
from fundos.indicators.reading import read_snapshot
from fundos.indicators.values import PRESENT
from fundos.indicators.values import FieldValue
from fundos.indicators.values import Subject


TABLE = "tab_X_6"
EXPECTED = "tab_X_6.TAB_X_PR_DESEMP_ESPERADO"
REALIZED = "tab_X_6.TAB_X_PR_DESEMP_REAL"
RETURN = monthly_return.FIELD

CORRESPONDENCE = "Suplemento G, correspondencia pelo nome do campo"
EXPECTED_NAME = "Desempenho Esperado (Benchmark)"
REALIZED_NAME = "Desempenho Realizado (Rentabilidade no Mes)"
UNIT = "unidade nao confirmada"

EXPECTED_ZERO = "esperado_informado_zero"
EXPECTED_NEGATIVE = "esperado_negativo"
DIFFERS_FROM_RETURN = "realizado_difere_da_rentabilidade"
OPEN_CONFLICT = "conflito_aberto"
FLAGS = (EXPECTED_ZERO, EXPECTED_NEGATIVE, DIFFERS_FROM_RETURN, OPEN_CONFLICT)


@dataclass(frozen=True)
class SeriesPerformance:
    """Os dois campos de uma serie, como informados, e a tab_X_3 da mesma serie."""

    series_id: int
    label_key: str | None
    expected: FieldValue
    realized: FieldValue
    monthly_return: FieldValue
    flags: tuple[str, ...] = ()


@dataclass(frozen=True)
class PerformanceResult:
    """O desempenho das series de um assunto (classe ou fundo) numa competencia."""

    subject: Subject
    reference_date: str
    series: tuple[SeriesPerformance, ...]
    flags: tuple[str, ...] = ()
    correspondence: str = CORRESPONDENCE
    unit: str = UNIT

    def line(self, series_id):
        """A serie pelo id, ou None."""

        return next((line for line in self.series if line.series_id == series_id), None)


def fields():
    """Campos da tab_X_6 lidos: o esperado e o realizado."""

    return (EXPECTED, REALIZED)


def _month_end(reference_date):
    reference = normalize_iso_date(reference_date, "Competencia")
    previous_month_end(reference)
    return reference


def _flags(expected, realized, monthly):
    flags = []

    if expected.state == PRESENT and expected.value == 0:
        flags.append(EXPECTED_ZERO)

    if expected.state == PRESENT and expected.value < 0:
        flags.append(EXPECTED_NEGATIVE)

    if realized.state == PRESENT and monthly.state == PRESENT and realized.value != monthly.value:
        flags.append(DIFFERS_FROM_RETURN)

    if expected.open_conflict or realized.open_conflict or monthly.open_conflict:
        flags.append(OPEN_CONFLICT)

    return tuple(flags)


def desempenho(connection, reference_date, subjects=None):
    """O desempenho esperado e realizado por serie, agrupado pelo assunto (so le).

    So as series com algum dos dois campos da tab_X_6 na competencia;
    subjects (opcional) limita aos pais informados. Devolve uma tupla em
    ordem de assunto, com as series em ordem de id.
    """

    reference = _month_end(reference_date)

    with read_snapshot(connection):
        performance = read_series_competence(connection, reference, fields(), subjects)
        returns = read_series_competence(connection, reference, (RETURN,), subjects)

    by_series = {
        series_id: series_values.values[RETURN]
        for parent_series in returns.values()
        for series_id, series_values in parent_series.items()
    }
    results = []

    for parent, parent_series in performance.items():
        lines = []

        for series_id, series_values in parent_series.items():
            expected = series_values.values[EXPECTED]
            realized = series_values.values[REALIZED]
            monthly = by_series.get(series_id) or FieldValue.missing(RETURN, reference)
            lines.append(
                SeriesPerformance(
                    series_id=series_id,
                    label_key=series_values.label_key,
                    expected=expected,
                    realized=realized,
                    monthly_return=monthly,
                    flags=_flags(expected, realized, monthly),
                )
            )

        results.append(
            PerformanceResult(
                subject=parent,
                reference_date=reference,
                series=tuple(lines),
                flags=tuple(flag for flag in FLAGS if any(flag in line.flags for line in lines)),
            )
        )

    return tuple(results)
