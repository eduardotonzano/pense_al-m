"""Liquidez do informe de FIDC (tab_X_5), como informada (FU11.5).

E o item X.5 do modelo do Suplemento G da Resolucao CVM 175, "Liquidez",
em R$, com as 7 faixas do dicionario de dados da CVM, de "Ativos com
liquidez imediata" a "Ativos que podem ser liquidados em mais de 360 dias".
Cada faixa sai como informada, com fonte, competencia, observacao e coleta,
e estado presente ou sem_dado (com o motivo): valor ausente e sem_dado,
nunca zero; zero informado e zero.

Nada e somado nem dividido. O texto diz "em ate", o que sugere faixas
acumuladas, mas na maioria dos assuntos de 09 e 10/2026 (medido em copias)
as faixas nao crescem de uma para a proxima; nao ha base confirmada para a
soma, para o % de cada faixa nem para uma razao contra resgates ou
despesas (a tab_X_4 nao e carregada).

Nota do Suplemento G, item X.5: "Preenchimento compulsorio apenas para os
fundos abertos". Nenhum resultado usa a tab_I.CONDOM para classificar o
assunto.

Marcas:
- todas_as_faixas_zero: as 7 faixas informadas iguais a 0;
- faixa_negativa: alguma faixa informada negativa;
- conflito_aberto: algum campo tem conflito aberto no banco.

Calculado na leitura; nada e gravado.
"""

from dataclasses import dataclass

from fundos.database import normalize_iso_date
from fundos.indicators.reading import previous_month_end
from fundos.indicators.reading import read_competence
from fundos.indicators.values import PRESENT
from fundos.indicators.values import FieldValue
from fundos.indicators.values import Subject


TABLE = "tab_X_5"
OFFICIAL_NAME = "Liquidez"
NOTE = "Suplemento G, item X.5: preenchimento compulsorio apenas para os fundos abertos"

# (rotulo oficial, campo): as descricoes do dicionario, sem acento, na ordem do modelo.
BUCKETS = (
    ("Ativos com liquidez imediata", "tab_X_5.TAB_X_VL_LIQUIDEZ_0"),
    ("Ativos que podem ser liquidados em ate 30 dias", "tab_X_5.TAB_X_VL_LIQUIDEZ_30"),
    ("Ativos que podem ser liquidados em ate 60 dias", "tab_X_5.TAB_X_VL_LIQUIDEZ_60"),
    ("Ativos que podem ser liquidados em ate 90 dias", "tab_X_5.TAB_X_VL_LIQUIDEZ_90"),
    ("Ativos que podem ser liquidados em ate 180 dias", "tab_X_5.TAB_X_VL_LIQUIDEZ_180"),
    ("Ativos que podem ser liquidados em ate 360 dias", "tab_X_5.TAB_X_VL_LIQUIDEZ_360"),
    ("Ativos que podem ser liquidados em mais de 360 dias", "tab_X_5.TAB_X_VL_LIQUIDEZ_MAIOR_360"),
)

ALL_ZERO = "todas_as_faixas_zero"
NEGATIVE_BUCKET = "faixa_negativa"
OPEN_CONFLICT = "conflito_aberto"
FLAGS = (ALL_ZERO, NEGATIVE_BUCKET, OPEN_CONFLICT)


@dataclass(frozen=True)
class LiquidityResult:
    """A liquidez de um assunto (classe ou fundo) numa competencia, como informada."""

    subject: Subject
    reference_date: str
    buckets: tuple[tuple[str, FieldValue], ...]
    flags: tuple[str, ...] = ()
    name: str = OFFICIAL_NAME
    note: str = NOTE

    def bucket(self, label):
        """O FieldValue da faixa pelo rotulo oficial."""

        return next(value for name, value in self.buckets if name == label)


def fields():
    """Campos lidos: as 7 faixas da tab_X_5, na ordem do modelo."""

    return tuple(field_name for _, field_name in BUCKETS)


def _month_end(reference_date):
    reference = normalize_iso_date(reference_date, "Competencia")
    previous_month_end(reference)
    return reference


def _flags(values):
    present = [value for value in values if value.state == PRESENT]
    flags = []

    if len(present) == len(values) and all(value.value == 0 for value in present):
        flags.append(ALL_ZERO)

    if any(value.value < 0 for value in present):
        flags.append(NEGATIVE_BUCKET)

    if any(value.open_conflict for value in values):
        flags.append(OPEN_CONFLICT)

    return tuple(flags)


def liquidez(connection, reference_date, subjects=None):
    """A liquidez por assunto (classe ou fundo) numa competencia (so le).

    So os assuntos com alguma faixa na competencia; subjects (opcional)
    limita a leitura. Devolve uma tupla em ordem de assunto.
    """

    reference = _month_end(reference_date)
    results = []

    for subject, values in read_competence(connection, reference, fields(), subjects).items():
        ordered = [values[field_name] for _, field_name in BUCKETS]
        results.append(
            LiquidityResult(
                subject=subject,
                reference_date=reference,
                buckets=tuple((label, values[field_name]) for label, field_name in BUCKETS),
                flags=_flags(ordered),
            )
        )

    return tuple(results)
