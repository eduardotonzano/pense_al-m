"""Rentabilidade apurada no mes, por serie (tab_X_3), como informada (FU11.5).

E o item X.3 do modelo do Suplemento G da Resolucao CVM 175, "Rentabilidade
Apurada no Mes", informado por serie (classe ou subclasse e serie) no campo
tab_X_3.TAB_X_VL_RENTAB_MES. E do mes: nao e acumulada nem anualizada.

Cada serie sai com o valor como informado, com fonte, competencia,
observacao e coleta, e estado presente ou sem_dado (com o motivo): valor
ausente e sem_dado, nunca zero; zero informado e zero. A serie e
identificada pelo id e pelo rotulo normalizado (quota_series).

Nada e calculado: o valor nao e anualizado, nao e comparado com benchmark
e nao e agregado por classe. Nao confirmado: a unidade (o dicionario nao a
traz) e se o valor e liquido ou bruto de taxas.

Marca: conflito_aberto, quando o campo da serie tem conflito aberto no
banco. Calculado na leitura; nada e gravado.
"""

from dataclasses import dataclass

from fundos.database import normalize_iso_date
from fundos.indicators.reading import previous_month_end
from fundos.indicators.reading import read_series_competence
from fundos.indicators.values import FieldValue
from fundos.indicators.values import Subject


TABLE = "tab_X_3"
FIELD = "tab_X_3.TAB_X_VL_RENTAB_MES"
OFFICIAL_NAME = "Rentabilidade Apurada no Mes"
UNIT = "unidade nao confirmada"

OPEN_CONFLICT = "conflito_aberto"
FLAGS = (OPEN_CONFLICT,)


@dataclass(frozen=True)
class SeriesReturn:
    """A rentabilidade informada de uma serie."""

    series_id: int
    label_key: str | None
    value: FieldValue
    flags: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReturnResult:
    """A rentabilidade das series de um assunto (classe ou fundo) numa competencia."""

    subject: Subject
    reference_date: str
    series: tuple[SeriesReturn, ...]
    flags: tuple[str, ...] = ()
    name: str = OFFICIAL_NAME
    unit: str = UNIT

    def line(self, series_id):
        """A serie pelo id, ou None."""

        return next((line for line in self.series if line.series_id == series_id), None)


def fields():
    """Campo lido: a rentabilidade apurada no mes da tab_X_3."""

    return (FIELD,)


def _month_end(reference_date):
    reference = normalize_iso_date(reference_date, "Competencia")
    previous_month_end(reference)
    return reference


def rentabilidade(connection, reference_date, subjects=None):
    """A rentabilidade por serie, agrupada pelo assunto (classe ou fundo) (so le).

    So as series com o campo na competencia; subjects (opcional) limita aos
    pais informados. Devolve uma tupla em ordem de assunto, com as series
    em ordem de id.
    """

    reference = _month_end(reference_date)
    results = []

    for parent, by_series in read_series_competence(connection, reference, fields(), subjects).items():
        lines = tuple(
            SeriesReturn(
                series_id=series_id,
                label_key=series_values.label_key,
                value=series_values.values[FIELD],
                flags=(OPEN_CONFLICT,) if series_values.values[FIELD].open_conflict else (),
            )
            for series_id, series_values in by_series.items()
        )
        results.append(
            ReturnResult(
                subject=parent,
                reference_date=reference,
                series=lines,
                flags=(OPEN_CONFLICT,) if any(line.flags for line in lines) else (),
            )
        )

    return tuple(results)
