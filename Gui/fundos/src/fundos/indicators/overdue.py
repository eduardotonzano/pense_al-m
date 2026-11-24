"""Vencidos na carteira e faixas de atraso do informe de FIDC (FU11.1).

Calculado na leitura, por assunto (classe ou fundo) e competencia, sobre as
observacoes ja carregadas; nada e gravado. So os campos abaixo sao lidos:
nenhuma provisao (I.2.a.11 e I.2.b.11 ficam para a FU11.3), nenhum cedente.

Vencidos (overdue_in_portfolio), por bloco:
- o valor em R$ e o total "Inadimplentes (Valor das Parcelas
  Inadimplentes, em R$)" como a CVM o informa: tab_V.b (bloco a) e tab_VI.b
  (bloco b), cujas faixas a descricao oficial chama de "Vencidos e nao
  Pagos". O total a+b soma os dois blocos e so existe com os dois presentes;
- ao lado, separados e nunca somados aqui, os itens da tab_I do mesmo bloco:
  a.2 (creditos a vencer com parcelas inadimplentes), a.2.1 (valor total
  das parcelas inadimplentes) e a.3 (creditos existentes inadimplentes), e
  os equivalentes do bloco b. Parcela inadimplente e credito inadimplente
  sao medidas diferentes;
- o % sobre o denominador escolhido por quem chama, sem padrao (decisao de
  24/11/2026: so D1 e D2). D1, carteira (tab_I.TAB_I2_VL_CARTEIRA), igual
  para os dois blocos e o total. D2, direitos creditorios: I.2.a para o
  bloco a, I.2.b para o b e a soma dos dois para o total. Os totais I.2.a e
  I.2.b vem liquidos da provisao. Percentual acima de 100 nao e cortado.

Faixas de atraso (delinquency_buckets): as 10 faixas de tab_V.b e tab_VI.b,
cada uma com o % no total da mesma tabela. O total nunca e recalculado
pelas faixas.

Evolucao (bucket_evolution): a competencia M contra M-1 (ultimo dia do mes
anterior), faixa a faixa: os dois valores, a diferenca em R$ e a diferenca
da participacao em pontos percentuais. Sem M-1 carregada para o assunto, o
resultado e sem_dado (competencia_anterior_nao_carregada); nenhum buraco e
pulado. A passagem de credito de uma faixa para outra nao e observavel no
informe, que e agregado, e nao e calculada.
"""

from dataclasses import dataclass
from enum import Enum

from fundos.indicators.reading import previous_month_end
from fundos.indicators.reading import read_competence
from fundos.indicators.reading import read_snapshot
from fundos.indicators.values import BLOCK_A
from fundos.indicators.values import BLOCK_B
from fundos.indicators.values import BLOCK_TOTAL
from fundos.indicators.values import REASON_PREVIOUS_NOT_LOADED
from fundos.indicators.values import Amount
from fundos.indicators.values import Bucket
from fundos.indicators.values import BucketBlock
from fundos.indicators.values import Change
from fundos.indicators.values import FieldValue
from fundos.indicators.values import Ratio
from fundos.indicators.values import Subject
from fundos.indicators.values import bucket_blocks
from fundos.indicators.values import difference
from fundos.indicators.values import percentage
from fundos.indicators.values import reported
from fundos.indicators.values import summed


PORTFOLIO = "tab_I.TAB_I2_VL_CARTEIRA"

CREDIT_RIGHTS = {
    BLOCK_A: "tab_I.TAB_I2A_VL_DIRCRED_RISCO",
    BLOCK_B: "tab_I.TAB_I2B_VL_DIRCRED_SEM_RISCO",
}

OVERDUE_TOTAL = {
    BLOCK_A: "tab_V.TAB_V_B_VL_DIRCRED_INAD",
    BLOCK_B: "tab_VI.TAB_VI_B_VL_DIRCRED_INAD",
}

# Itens da tab_I, pelo numero do dicionario da CVM (o modelo do Suplemento G
# numera um item a menos a partir do a.10, mas estes nao mudam).
TAB_I_DETAILS = {
    BLOCK_A: (
        ("a.2", "tab_I.TAB_I2A2_VL_CRED_VENC_INAD"),
        ("a.2.1", "tab_I.TAB_I2A21_VL_TOTAL_PARCELA_INAD"),
        ("a.3", "tab_I.TAB_I2A3_VL_CRED_INAD"),
    ),
    BLOCK_B: (
        ("b.2", "tab_I.TAB_I2B2_VL_CRED_VENC_INAD"),
        ("b.2.1", "tab_I.TAB_I2B21_VL_TOTAL_PARCELA_INAD"),
        ("b.3", "tab_I.TAB_I2B3_VL_CRED_INAD"),
    ),
}

# Rotulos = descricoes oficiais das faixas no dicionario (sem acento).
BUCKET_LABELS = (
    "Vencidos e nao Pagos entre 1 e 30 dias",
    "Vencidos e nao Pagos entre 31 e 60 dias",
    "Vencidos e nao Pagos entre 61 e 90 dias",
    "Vencidos e nao Pagos entre 91 e 120 dias",
    "Vencidos e nao Pagos entre 121 e 150 dias",
    "Vencidos e nao Pagos entre 151 e 180 dias",
    "Vencidos e nao Pagos entre 181 e 360 dias",
    "Vencidos e nao Pagos entre 361 e 720 dias",
    "Vencidos e nao Pagos entre 721 e 1080 dias",
    "Vencidos e nao Pagos acima de 1080 dias",
)

_DAYS = ("30", "60", "90", "120", "150", "180", "360", "720", "1080")


def _bucket_fields(table):
    prefix = table + "." + table.upper() + "_B"

    return tuple(
        prefix + str(index) + "_VL_INAD_" + days
        for index, days in enumerate(_DAYS, start=1)
    ) + (prefix + "10_VL_INAD_MAIOR_1080",)


BUCKET_FIELDS = {BLOCK_A: _bucket_fields("tab_V"), BLOCK_B: _bucket_fields("tab_VI")}

BUCKET_SPECS = {
    block: (OVERDUE_TOTAL[block], tuple(zip(BUCKET_LABELS, BUCKET_FIELDS[block])))
    for block in (BLOCK_A, BLOCK_B)
}


class Denominator(Enum):
    """Denominador do % de vencidos (D1 e D2; o PL nao e uma opcao)."""

    PORTFOLIO = "carteira"
    CREDIT_RIGHTS = "direitos_creditorios"


@dataclass(frozen=True)
class OverdueBlock:
    """Vencidos de um bloco (a, b ou a+b), o % e os itens da tab_I ao lado."""

    block: str
    overdue: Amount
    share: Ratio
    details: tuple[tuple[str, FieldValue], ...]


@dataclass(frozen=True)
class OverdueResult:
    """Vencidos na carteira de um assunto numa competencia."""

    subject: Subject
    reference_date: str
    denominator: Denominator
    blocks: tuple[OverdueBlock, ...]

    def block(self, name):
        """O bloco a, b ou a+b."""

        return next(block for block in self.blocks if block.block == name)


@dataclass(frozen=True)
class BucketsResult:
    """Faixas de atraso de um assunto numa competencia (blocos a, b e a+b)."""

    subject: Subject
    reference_date: str
    blocks: tuple[BucketBlock, ...]

    def block(self, name):
        """O bloco a, b ou a+b."""

        return next(block for block in self.blocks if block.block == name)


@dataclass(frozen=True)
class BucketChange:
    """Uma faixa em M-1 e em M: diferenca em R$ e em pontos percentuais."""

    label: str
    previous: Bucket
    current: Bucket
    amount_change: Change
    share_change: Change


@dataclass(frozen=True)
class EvolutionBlock:
    """Evolucao das faixas de um bloco (a, b ou a+b) entre M-1 e M."""

    block: str
    previous_total: Amount
    current_total: Amount
    total_change: Change
    buckets: tuple[BucketChange, ...]


@dataclass(frozen=True)
class EvolutionResult:
    """Evolucao das faixas de atraso de um assunto entre M-1 e M."""

    subject: Subject
    reference_date: str
    previous_reference_date: str
    blocks: tuple[EvolutionBlock, ...]

    def block(self, name):
        """O bloco a, b ou a+b."""

        return next(block for block in self.blocks if block.block == name)


def overdue_fields(denominator):
    """Campos lidos por overdue_in_portfolio para o denominador."""

    if not isinstance(denominator, Denominator):
        raise ValueError(
            "Denominador desconhecido: use Denominator.PORTFOLIO ou "
            "Denominator.CREDIT_RIGHTS."
        )

    fields = tuple(OVERDUE_TOTAL.values()) + tuple(
        name for block in (BLOCK_A, BLOCK_B) for _, name in TAB_I_DETAILS[block]
    )

    if denominator is Denominator.PORTFOLIO:
        return fields + (PORTFOLIO,)

    return fields + tuple(CREDIT_RIGHTS.values())


def bucket_fields():
    """Campos lidos pelas faixas de atraso e pela evolucao."""

    return tuple(OVERDUE_TOTAL.values()) + BUCKET_FIELDS[BLOCK_A] + BUCKET_FIELDS[BLOCK_B]


def _denominators(values, denominator):
    if denominator is Denominator.PORTFOLIO:
        portfolio = reported(values[PORTFOLIO])
        return portfolio, portfolio, portfolio

    return (
        reported(values[CREDIT_RIGHTS[BLOCK_A]]),
        reported(values[CREDIT_RIGHTS[BLOCK_B]]),
        summed(values[CREDIT_RIGHTS[BLOCK_A]], values[CREDIT_RIGHTS[BLOCK_B]]),
    )


def overdue_in_portfolio(connection, reference_date, denominator, subjects=None):
    """Vencidos em R$ e em % do denominador, por assunto (blocos a, b e a+b)."""

    fields = overdue_fields(denominator)
    results = []

    for subject, values in read_competence(
        connection, reference_date, fields, subjects
    ).items():
        block_a = reported(values[OVERDUE_TOTAL[BLOCK_A]])
        block_b = reported(values[OVERDUE_TOTAL[BLOCK_B]])
        total = summed(values[OVERDUE_TOTAL[BLOCK_A]], values[OVERDUE_TOTAL[BLOCK_B]])
        over_a, over_b, over_total = _denominators(values, denominator)
        results.append(
            OverdueResult(
                subject=subject,
                reference_date=block_a.parts[0].reference_date,
                denominator=denominator,
                blocks=(
                    OverdueBlock(
                        BLOCK_A,
                        block_a,
                        percentage(block_a, over_a),
                        tuple((item, values[name]) for item, name in TAB_I_DETAILS[BLOCK_A]),
                    ),
                    OverdueBlock(
                        BLOCK_B,
                        block_b,
                        percentage(block_b, over_b),
                        tuple((item, values[name]) for item, name in TAB_I_DETAILS[BLOCK_B]),
                    ),
                    OverdueBlock(BLOCK_TOTAL, total, percentage(total, over_total), ()),
                ),
            )
        )

    return tuple(results)


def delinquency_buckets(connection, reference_date, subjects=None):
    """Faixas de atraso (tab_V.b e tab_VI.b) por assunto, com o % no total."""

    return tuple(
        BucketsResult(
            subject=subject,
            reference_date=values[OVERDUE_TOTAL[BLOCK_A]].reference_date,
            blocks=bucket_blocks(values, BUCKET_SPECS),
        )
        for subject, values in read_competence(
            connection, reference_date, bucket_fields(), subjects
        ).items()
    )


def _evolution_block(previous, current):
    return EvolutionBlock(
        block=current.block,
        previous_total=previous.total,
        current_total=current.total,
        total_change=difference(previous.total, current.total),
        buckets=tuple(
            BucketChange(
                label=now.label,
                previous=before,
                current=now,
                amount_change=difference(before.amount, now.amount),
                share_change=difference(before.share, now.share),
            )
            for before, now in zip(previous.buckets, current.buckets)
        ),
    )


def bucket_evolution(connection, reference_date, subjects=None):
    """Faixas de atraso de M contra M-1, por assunto com dado em M."""

    previous_date = previous_month_end(reference_date)
    fields = bucket_fields()

    with read_snapshot(connection):
        current = read_competence(connection, reference_date, fields, subjects)
        previous = read_competence(connection, previous_date, fields, subjects)

    results = []

    for subject, values in current.items():
        before = previous.get(subject) or {
            name: FieldValue.missing(name, previous_date, REASON_PREVIOUS_NOT_LOADED)
            for name in fields
        }
        results.append(
            EvolutionResult(
                subject=subject,
                reference_date=values[OVERDUE_TOTAL[BLOCK_A]].reference_date,
                previous_reference_date=previous_date,
                blocks=tuple(
                    _evolution_block(old, new)
                    for old, new in zip(
                        bucket_blocks(before, BUCKET_SPECS),
                        bucket_blocks(values, BUCKET_SPECS),
                    )
                ),
            )
        )

    return tuple(results)
