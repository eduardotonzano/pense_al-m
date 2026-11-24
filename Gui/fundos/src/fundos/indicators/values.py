"""Tipos de valor dos indicadores do informe de FIDC (FU11.1).

Todo valor sai com estado: PRESENT ("presente") ou NO_DATA ("sem_dado", com
o motivo). Valor ausente nunca vira zero nem estimativa. Os valores sao
Decimal exatos, como gravados; o percentual e calculado com 28 digitos
significativos e nao e arredondado aqui (arredondar e decisao de exibicao).

Motivos de sem_dado:
- campo_ausente: o assunto nao tem o campo na competencia;
- tipo_inesperado: o campo nao veio como numero (o valor nunca e repetido);
- competencia_anterior_nao_carregada: o assunto nao tem nenhum campo do
  indicador na competencia anterior (so na evolucao entre competencias);
- denominador_zero e denominador_negativo: o percentual nao e calculado; o
  valor em R$ continua presente.

Blocos do informe: "a" (direitos creditorios com aquisicao substancial dos
riscos e beneficios: tab_I bloco I.2.a e tab_V) e "b" (sem aquisicao
substancial: tab_I bloco I.2.b e tab_VI). O total "a+b" soma a mesma medida
dos dois blocos, que nao se sobrepoem, e so existe com os dois presentes.
"""

from dataclasses import dataclass
from dataclasses import field
from decimal import Decimal
from decimal import localcontext


PRESENT = "presente"
NO_DATA = "sem_dado"

REASON_MISSING = "campo_ausente"
REASON_UNEXPECTED_TYPE = "tipo_inesperado"
REASON_PREVIOUS_NOT_LOADED = "competencia_anterior_nao_carregada"
REASON_ZERO_DENOMINATOR = "denominador_zero"
REASON_NEGATIVE_DENOMINATOR = "denominador_negativo"

CLASS_SUBJECT = "classe"
FUND_SUBJECT = "fundo"

BLOCK_A = "a"
BLOCK_B = "b"
BLOCK_TOTAL = "a+b"
BLOCKS = (BLOCK_A, BLOCK_B)

PRECISION = 28
HUNDRED = Decimal(100)


@dataclass(frozen=True, order=True)
class Subject:
    """Assunto do informe: a classe ou o fundo do cadastro (tipo e id do banco).

    A identidade e o par (tipo, id); o CNPJ vem junto para quem chama, mas
    nao entra na comparacao nem no repr (nao vaza em log, erro ou teste).
    """

    kind: str
    id: int
    cnpj: str = field(compare=False, repr=False)


@dataclass(frozen=True)
class FieldValue:
    """Um campo do informe numa competencia, com a proveniencia da observacao.

    field_name e a tabela.coluna da CVM, sem renomear. Com estado sem_dado,
    value e None e reason diz o motivo.
    """

    field_name: str
    reference_date: str
    state: str
    value: Decimal | None = None
    reason: str | None = None
    observation_id: int | None = None
    source_code: str | None = None
    collected_at: str | None = None
    open_conflict: bool = False

    @classmethod
    def missing(cls, field_name, reference_date, reason=REASON_MISSING):
        """Campo sem dado na competencia, com o motivo."""

        return cls(
            field_name=field_name,
            reference_date=reference_date,
            state=NO_DATA,
            reason=reason,
        )


@dataclass(frozen=True)
class Amount:
    """Valor em R$ de um indicador: um campo informado ou a soma de campos.

    parts traz os campos de origem, com a proveniencia de cada um. A soma so
    existe com todas as partes presentes; com uma parte sem dado, o valor e
    sem dado, com o motivo da primeira parte que falta.
    """

    state: str
    value: Decimal | None
    parts: tuple[FieldValue, ...]
    reason: str | None = None

    @property
    def fields(self):
        """Os campos de origem (tabela.coluna), na ordem das partes."""

        return tuple(part.field_name for part in self.parts)

    @property
    def open_conflict(self):
        """Verdadeiro se alguma parte tem conflito aberto no banco."""

        return any(part.open_conflict for part in self.parts)


@dataclass(frozen=True)
class Ratio:
    """Percentual (em %) de um valor sobre outro, so com denominador > 0."""

    state: str
    value: Decimal | None
    numerator: Amount
    denominator: Amount
    reason: str | None = None


@dataclass(frozen=True)
class Change:
    """Diferenca entre duas competencias: a atual menos a anterior."""

    state: str
    value: Decimal | None
    reason: str | None = None


@dataclass(frozen=True)
class Bucket:
    """Uma faixa: o valor informado e o % dela no total da mesma tabela."""

    label: str
    amount: Amount
    share: Ratio


@dataclass(frozen=True)
class BucketBlock:
    """As faixas de um bloco (a, b ou a+b) e o total informado do bloco.

    O total nunca e recalculado pelas faixas: e o campo de total do informe
    (ou, em a+b, a soma dos totais dos dois blocos).
    """

    block: str
    total: Amount
    buckets: tuple[Bucket, ...]


def reported(field_value):
    """Amount de um unico campo informado."""

    return summed(field_value)


def summed(*field_values):
    """Soma de campos da mesma medida; sem dado se faltar alguma parte."""

    if not field_values:
        raise ValueError("A soma precisa de pelo menos um campo.")

    for part in field_values:
        if part.state != PRESENT:
            return Amount(NO_DATA, None, tuple(field_values), part.reason)

    return Amount(
        PRESENT,
        sum((part.value for part in field_values), Decimal(0)),
        tuple(field_values),
    )


def percentage(numerator, denominator):
    """numerator / denominator * 100, so com os dois presentes e denominador > 0."""

    for amount in (numerator, denominator):
        if amount.state != PRESENT:
            return Ratio(NO_DATA, None, numerator, denominator, amount.reason)

    if denominator.value == 0:
        return Ratio(NO_DATA, None, numerator, denominator, REASON_ZERO_DENOMINATOR)

    if denominator.value < 0:
        return Ratio(
            NO_DATA, None, numerator, denominator, REASON_NEGATIVE_DENOMINATOR
        )

    with localcontext() as context:
        context.prec = PRECISION
        value = numerator.value / denominator.value * HUNDRED

    return Ratio(PRESENT, value, numerator, denominator)


def difference(previous, current):
    """current - previous (Amount ou Ratio); sem dado se faltar um dos lados."""

    for item in (previous, current):
        if item.state != PRESENT:
            return Change(NO_DATA, None, item.reason)

    with localcontext() as context:
        context.prec = PRECISION
        value = current.value - previous.value

    return Change(PRESENT, value)


def bucket_block(block, total, labeled_amounts):
    """Monta um BucketBlock: cada faixa com o % dela no total do bloco."""

    return BucketBlock(
        block=block,
        total=total,
        buckets=tuple(
            Bucket(label, amount, percentage(amount, total))
            for label, amount in labeled_amounts
        ),
    )


def bucket_blocks(values, specs):
    """Blocos a, b e a+b de uma tabela de faixas.

    values: {campo: FieldValue} de um assunto numa competencia.
    specs: {bloco: (campo do total, ((rotulo, campo da faixa), ...))} para
    os blocos a e b, com os mesmos rotulos, na mesma ordem.
    """

    blocks = []

    for block in BLOCKS:
        total_field, buckets = specs[block]
        blocks.append(
            bucket_block(
                block,
                reported(values[total_field]),
                [(label, reported(values[name])) for label, name in buckets],
            )
        )

    total_a, buckets_a = specs[BLOCK_A]
    total_b, buckets_b = specs[BLOCK_B]
    blocks.append(
        bucket_block(
            BLOCK_TOTAL,
            summed(values[total_a], values[total_b]),
            [
                (label, summed(values[name_a], values[name_b]))
                for (label, name_a), (_, name_b) in zip(buckets_a, buckets_b)
            ],
        )
    )

    return tuple(blocks)
