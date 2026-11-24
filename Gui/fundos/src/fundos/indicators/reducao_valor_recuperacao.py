"""Provisao para Reducao no Valor de Recuperacao e cobertura dos vencidos (FU11.3).

A provisao da carteira de direitos creditorios vem da tab_I, por bloco:
TAB_I2A11_VL_REDUCAO_RECUP (bloco a) e TAB_I2B11_VL_REDUCAO_RECUP (bloco b),
com o nome oficial "Provisao para Reducao no Valor de Recuperacao" (itens
a.10 e b.10 do Suplemento G; a.11 e b.11 no dicionario). O valor vem
positivo e e subtraido do total do bloco (docs/fundos-sonda-pdd-cedente.md,
secao 2). Nenhuma fonte oficial usa "PDD": a equivalencia nao esta
confirmada.

Por assunto (classe ou fundo), competencia e bloco (a, b e a+b; o a+b so
existe com os dois blocos presentes):
- provisao: o valor em R$ como informado;
- vencidos: o total "Inadimplentes (Valor das Parcelas Inadimplentes, em
  R$)" da tab_V.b (bloco a) e da tab_VI.b (bloco b), o mesmo da FU11.1;
- cobertura: provisao / vencidos x 100, so com vencidos > 0. A provisao e do
  bloco todo e o vencido e so uma parte dele: a cobertura nao diz quanto do
  vencido esta provisionado, e passar de 100% nao e erro (nao e cortado).

Estados da cobertura, nesta ordem: falta um dos lados (campo_ausente ou
tipo_inesperado); provisao negativa (provisao_negativa) ou vencidos
negativos (vencidos_negativos), sem calcular; vencidos = 0
(denominador_zero, com a provisao em R$ presente); fora disso, presente
(provisao 0 com vencidos > 0 da 0%). No a+b, um bloco com valor negativo
impede a soma, com o mesmo motivo. Marca provisao_sem_vencidos: provisao
maior que 0 e vencidos iguais a 0.

Nunca sao lidas as provisoes sobre cotas de FIDC, sobre debentures e CRI e
sobre outros ativos (TAB_I2_COTA_FIDC, TAB_I2_DEBENTURE_CRI e
TAB_I2_VL_OUTRO_ATIVO), que nao sao da carteira de direitos creditorios.
Nada e somado nem comparado com a.2.1, a.3 ou o total do bloco. Nada e
gravado.
"""

from dataclasses import dataclass

from fundos.indicators.overdue import OVERDUE_TOTAL
from fundos.indicators.reading import read_competence
from fundos.indicators.values import BLOCK_A
from fundos.indicators.values import BLOCK_B
from fundos.indicators.values import BLOCK_TOTAL
from fundos.indicators.values import NO_DATA
from fundos.indicators.values import PRESENT
from fundos.indicators.values import Amount
from fundos.indicators.values import Ratio
from fundos.indicators.values import Subject
from fundos.indicators.values import percentage
from fundos.indicators.values import reported
from fundos.indicators.values import summed


OFFICIAL_NAME = "Provisao para Reducao no Valor de Recuperacao"

PROVISION = {
    BLOCK_A: "tab_I.TAB_I2A11_VL_REDUCAO_RECUP",
    BLOCK_B: "tab_I.TAB_I2B11_VL_REDUCAO_RECUP",
}

REASON_NEGATIVE_PROVISION = "provisao_negativa"
REASON_NEGATIVE_OVERDUE = "vencidos_negativos"

PROVISION_WITHOUT_OVERDUE = "provisao_sem_vencidos"


@dataclass(frozen=True)
class ProvisaoBlock:
    """Provisao, vencidos e cobertura de um bloco (a, b ou a+b)."""

    block: str
    provisao: Amount
    vencidos: Amount
    cobertura: Ratio
    flags: tuple[str, ...]


@dataclass(frozen=True)
class ProvisaoResult:
    """A provisao e a cobertura de um assunto numa competencia."""

    subject: Subject
    reference_date: str
    blocks: tuple[ProvisaoBlock, ...]
    name: str = OFFICIAL_NAME

    def block(self, name):
        """O bloco a, b ou a+b."""

        return next(block for block in self.blocks if block.block == name)


def fields():
    """Os 4 campos lidos: a provisao e os vencidos de cada bloco."""

    return (
        PROVISION[BLOCK_A],
        PROVISION[BLOCK_B],
        OVERDUE_TOTAL[BLOCK_A],
        OVERDUE_TOTAL[BLOCK_B],
    )


def _non_negative_sum(first, second, reason):
    """Soma a+b da mesma medida; sem dado se faltar parte ou houver negativo."""

    total = summed(first, second)

    if total.state == PRESENT and any(part.value < 0 for part in total.parts):
        return Amount(NO_DATA, None, total.parts, reason)

    return total


def coverage(provisao, vencidos):
    """provisao / vencidos x 100, com os motivos de sem_dado desta etapa."""

    for amount in (provisao, vencidos):
        if amount.state != PRESENT:
            return Ratio(NO_DATA, None, provisao, vencidos, amount.reason)

    if provisao.value < 0:
        return Ratio(NO_DATA, None, provisao, vencidos, REASON_NEGATIVE_PROVISION)

    if vencidos.value < 0:
        return Ratio(NO_DATA, None, provisao, vencidos, REASON_NEGATIVE_OVERDUE)

    return percentage(provisao, vencidos)


def _block(block, provisao, vencidos):
    flags = ()

    if (
        provisao.state == PRESENT
        and vencidos.state == PRESENT
        and provisao.value > 0
        and vencidos.value == 0
    ):
        flags = (PROVISION_WITHOUT_OVERDUE,)

    return ProvisaoBlock(block, provisao, vencidos, coverage(provisao, vencidos), flags)


def provisao_reducao_valor_recuperacao(connection, reference_date, subjects=None):
    """Provisao e cobertura dos vencidos por assunto (blocos a, b e a+b)."""

    results = []

    for subject, values in read_competence(
        connection, reference_date, fields(), subjects
    ).items():
        blocks = [
            _block(
                block,
                reported(values[PROVISION[block]]),
                reported(values[OVERDUE_TOTAL[block]]),
            )
            for block in (BLOCK_A, BLOCK_B)
        ]
        blocks.append(
            _block(
                BLOCK_TOTAL,
                _non_negative_sum(
                    values[PROVISION[BLOCK_A]],
                    values[PROVISION[BLOCK_B]],
                    REASON_NEGATIVE_PROVISION,
                ),
                _non_negative_sum(
                    values[OVERDUE_TOTAL[BLOCK_A]],
                    values[OVERDUE_TOTAL[BLOCK_B]],
                    REASON_NEGATIVE_OVERDUE,
                ),
            )
        )
        results.append(
            ProvisaoResult(
                subject=subject,
                reference_date=values[PROVISION[BLOCK_A]].reference_date,
                blocks=tuple(blocks),
            )
        )

    return tuple(results)
