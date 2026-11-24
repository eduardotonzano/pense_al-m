"""Indicador 10: "Por Prazo de Vencimento (R$)" do informe de FIDC (FU11.1).

E a distribuicao informada pela CVM, como o informe a traz: o item V.a
(bloco a, tab_V) e o item VI.a (bloco b, tab_VI) do modelo do Suplemento G
da Resolucao CVM 175, cada um com o total e as 10 faixas, de "Ate 30 dias"
a "Acima de 1080 dias". Cada faixa sai com o % no total da mesma tabela; o
total a+b soma os dois blocos e so existe com os dois presentes. O total
nunca e recalculado pelas faixas.

Nao confirmado: o que o total V.a (e o VI.a) cobre; a descricao oficial
nao diz. O informe de FIDC nao tem campo de prazo medio, e nada aqui o
calcula nem o estima. Calculado na leitura; nada e gravado.
"""

from dataclasses import dataclass

from fundos.indicators.reading import read_competence
from fundos.indicators.values import BLOCK_A
from fundos.indicators.values import BLOCK_B
from fundos.indicators.values import BucketBlock
from fundos.indicators.values import Subject
from fundos.indicators.values import bucket_blocks


OFFICIAL_NAME = "Por Prazo de Vencimento (R$)"

TOTAL = {
    BLOCK_A: "tab_V.TAB_V_A_VL_DIRCRED_PRAZO",
    BLOCK_B: "tab_VI.TAB_VI_A_VL_DIRCRED_PRAZO",
}

# Rotulos = descricoes oficiais das faixas no dicionario (sem acento).
LABELS = (
    "Ate 30 dias",
    "De 31 a 60 dias",
    "De 61 a 90 dias",
    "De 91 a 120 dias",
    "De 121 a 150 dias",
    "De 151 a 180 dias",
    "De 181 a 360 dias",
    "De 361 a 720 dias",
    "De 721 a 1080 dias",
    "Acima de 1080 dias",
)

_DAYS = ("30", "60", "90", "120", "150", "180", "360", "720", "1080")


def _fields(table):
    prefix = table + "." + table.upper() + "_A"

    return tuple(
        prefix + str(index) + "_VL_PRAZO_VENC_" + days
        for index, days in enumerate(_DAYS, start=1)
    ) + (prefix + "10_VL_PRAZO_VENC_MAIOR_1080",)


BUCKET_FIELDS = {BLOCK_A: _fields("tab_V"), BLOCK_B: _fields("tab_VI")}

SPECS = {
    block: (TOTAL[block], tuple(zip(LABELS, BUCKET_FIELDS[block])))
    for block in (BLOCK_A, BLOCK_B)
}


@dataclass(frozen=True)
class PorPrazoDeVencimento:
    """A distribuicao "Por Prazo de Vencimento (R$)" de um assunto numa competencia."""

    subject: Subject
    reference_date: str
    blocks: tuple[BucketBlock, ...]
    name: str = OFFICIAL_NAME

    def block(self, name):
        """O bloco a, b ou a+b."""

        return next(block for block in self.blocks if block.block == name)


def fields():
    """Campos lidos: os totais V.a e VI.a e as 10 faixas de cada um."""

    return tuple(TOTAL.values()) + BUCKET_FIELDS[BLOCK_A] + BUCKET_FIELDS[BLOCK_B]


def por_prazo_de_vencimento(connection, reference_date, subjects=None):
    """A distribuicao informada, por assunto (blocos a, b e a+b), com o % no total."""

    return tuple(
        PorPrazoDeVencimento(
            subject=subject,
            reference_date=values[TOTAL[BLOCK_A]].reference_date,
            blocks=bucket_blocks(values, SPECS),
        )
        for subject, values in read_competence(
            connection, reference_date, fields(), subjects
        ).items()
    )
