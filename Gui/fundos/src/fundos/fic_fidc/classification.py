"""Classificacao de FIC-FIDC, calculada na leitura (decisao 6 de Fundos).

O sinal e a parcela do ativo em cotas de FIDC no informe mensal de FIDC:
tab_I.TAB_I2H_VL_COTA_FIDC sobre tab_I.TAB_I_VL_ATIVO, na mesma competencia.
E uma regra de corte, nao um dado da CVM:
- 95% ou mais: FIC-FIDC;
- de 67% (inclusive) a menos de 95%: em revisao manual;
- abaixo de 67%: nao classificado.

A faixa sai da multiplicacao cruzada em Decimal (100 x cotas contra 95 x
ativo e 67 x ativo), num contexto que nao arredonda, nunca da divisao. O
percentual (share) sai so para exibicao, com 28 digitos significativos e
sem arredondar.

Sem dado, com o motivo, nesta ordem (nunca zero, nunca estimado):
1. o assunto pedido nao tem informe na competencia
   (sem_informe_na_competencia);
2. falta um dos campos (campo_ausente) ou ele nao veio como numero
   (tipo_inesperado);
3. ativo igual a 0 (denominador_zero) ou negativo (denominador_negativo);
4. cotas de FIDC negativas (numerador_negativo).
Zero informado e zero: cotas 0 com ativo positivo e "nao classificado".

Marcas: acima_de_100 (as cotas passam o ativo: classifica, sem cortar),
conflito_aberto (algum dos dois campos tem conflito aberto no banco) e
tipo_no_cadastro_fiagro (o assunto e FIAGRO no cadastro e tem o informe de
FIDC: classifica pela regra e marca).

O valor de cada campo e o do read_competence (fontes ativas, prioridade,
coleta mais recente e id, dentro da competencia), com a proveniencia da
observacao. Nunca classifica pelo nome. Nada e gravado: a fila de revisao
manual (review_queue) e uma escrita explicita e separada.
"""

from dataclasses import dataclass
from decimal import Decimal
from decimal import Inexact
from decimal import Rounded
from decimal import localcontext

from fundos.cadastro import columns as cadastro_spec
from fundos.database import normalize_iso_date
from fundos.indicators.reading import check_subjects
from fundos.indicators.reading import previous_month_end
from fundos.indicators.reading import read_competence
from fundos.indicators.reading import read_snapshot
from fundos.indicators.reading import subjects_with_table
from fundos.indicators.values import CLASS_SUBJECT
from fundos.indicators.values import FUND_SUBJECT
from fundos.indicators.values import NO_DATA
from fundos.indicators.values import PRESENT
from fundos.indicators.values import REASON_NEGATIVE_DENOMINATOR
from fundos.indicators.values import REASON_ZERO_DENOMINATOR
from fundos.indicators.values import Amount
from fundos.indicators.values import FieldValue
from fundos.indicators.values import Ratio
from fundos.indicators.values import Subject
from fundos.indicators.values import percentage
from fundos.indicators.values import reported


RULE = "fic_fidc.v1"
NUMERATOR = "tab_I.TAB_I2H_VL_COTA_FIDC"
DENOMINATOR = "tab_I.TAB_I_VL_ATIVO"
FIELDS = (NUMERATOR, DENOMINATOR)

FIC_FIDC_CUT = Decimal(95)
REVIEW_CUT = Decimal(67)
HUNDRED = Decimal(100)

RULE_TEXT = (
    "fic_fidc.v1 (decisao 6 de Fundos): TAB_I2H_VL_COTA_FIDC / TAB_I_VL_ATIVO, "
    "na tab_I da mesma competencia; 95% ou mais: FIC-FIDC; de 67% a menos de "
    "95%: em revisao manual; abaixo de 67%: nao classificado. Regra de corte, "
    "nao dado da CVM; nunca pelo nome."
)

FIC_FIDC = "fic_fidc"
MANUAL_REVIEW = "em_revisao_manual"
NOT_CLASSIFIED = "nao_classificado"
BANDS = (FIC_FIDC, MANUAL_REVIEW, NOT_CLASSIFIED, NO_DATA)
LABELS = {
    FIC_FIDC: "FIC-FIDC",
    MANUAL_REVIEW: "em revisao manual",
    NOT_CLASSIFIED: "nao classificado",
    NO_DATA: "sem dado",
}

REASON_NEGATIVE_NUMERATOR = "numerador_negativo"
REASON_NO_INFORME = "sem_informe_na_competencia"

ABOVE_100 = "acima_de_100"
OPEN_CONFLICT = "conflito_aberto"
FIAGRO_IN_CADASTRO = "tipo_no_cadastro_fiagro"
FLAGS = (ABOVE_100, OPEN_CONFLICT, FIAGRO_IN_CADASTRO)

# Tipo do assunto no cadastro (so para marca e contagem): o rotulo do mapa
# SCOPE do cadastro; um valor fora do mapa fica como OUTSIDE_SCOPE.
OUTSIDE_SCOPE = "fora do escopo do cadastro"

# A tabela do informe que define o universo dos assuntos.
INFORME_TABLE = "tab_I"


@dataclass(frozen=True)
class Classification:
    """A classificacao de um assunto numa competencia, com a regra e os dois numeros.

    numerator e denominator trazem o FieldValue de cada campo (tabela.coluna,
    competencia, fonte, observacao, coleta e conflito aberto). share e o
    percentual so para exibicao; a faixa (band) sai da multiplicacao
    cruzada. Com band sem_dado, reason diz o motivo.
    """

    subject: Subject
    reference_date: str
    band: str
    numerator: Amount
    denominator: Amount
    share: Ratio
    reason: str | None = None
    flags: tuple[str, ...] = ()
    cadastro_type: str | None = None
    rule: str = RULE
    rule_text: str = RULE_TEXT

    @property
    def label(self):
        """O rotulo da faixa: FIC-FIDC, em revisao manual, nao classificado ou sem dado."""

        return LABELS[self.band]


def month_end(reference_date):
    """A competencia em AAAA-MM-DD; tem de ser o ultimo dia do mes."""

    reference = normalize_iso_date(reference_date, "Competencia")
    previous_month_end(reference)
    return reference


def _digits(value):
    return len(value.as_tuple().digits)


def band(numerator, denominator):
    """Faixa da decisao 6 por multiplicacao cruzada, so com Decimal.

    Exige ativo maior que 0 e cotas maiores ou iguais a 0 (os outros casos
    sao sem_dado antes de chegar aqui). O contexto tem precisao para o
    produto exato e recusa qualquer arredondamento.
    """

    for value in (numerator, denominator):
        if not isinstance(value, Decimal):
            raise TypeError("A faixa so e calculada com Decimal.")

        if not value.is_finite():
            raise ValueError("A faixa so e calculada com valor finito.")

    if denominator <= 0:
        raise ValueError("O ativo deve ser maior que zero.")

    if numerator < 0:
        raise ValueError("As cotas de FIDC nao podem ser negativas.")

    with localcontext() as context:
        context.prec = max(_digits(numerator), _digits(denominator)) + 10
        context.traps[Inexact] = True
        context.traps[Rounded] = True
        scaled = numerator * HUNDRED

        if scaled >= denominator * FIC_FIDC_CUT:
            return FIC_FIDC

        if scaled >= denominator * REVIEW_CUT:
            return MANUAL_REVIEW

    return NOT_CLASSIFIED


def subject_types(connection):
    """{(tipo do assunto, id): rotulo} pelo valor atual do tipo no cadastro.

    Classe: registro_classe.Tipo_Classe; fundo: registro_fundo.Tipo_Fundo. O
    rotulo e o do mapa SCOPE do cadastro (FIDC ou FIAGRO); fora dele, fica
    OUTSIDE_SCOPE. Assunto sem a observacao nao entra. So le.
    """

    found = {}

    for kind, column, table in (
        (CLASS_SUBJECT, "fund_class_id", cadastro_spec.CLASS_TABLE),
        (FUND_SUBJECT, "fund_id", cadastro_spec.FUND_TABLE),
    ):
        field_name = cadastro_spec.field_name(table, cadastro_spec.TYPE_COLUMN[table])
        scope = cadastro_spec.SCOPE[table]
        rows = connection.execute(
            "SELECT " + column + ", value_text FROM current_observations"
            " WHERE field_name = ? AND " + column + " IS NOT NULL",
            (field_name,),
        ).fetchall()

        for subject_id, text in rows:
            found[(kind, int(subject_id))] = scope.get(str(text).strip(), OUTSIDE_SCOPE)

    return found


def informe_subjects(connection, reference_date):
    """{(tipo, id): Subject} com alguma observacao da tab_I na competencia (fonte ativa)."""

    return subjects_with_table(connection, reference_date, INFORME_TABLE)


def _no_informe(subject, reference, cadastro_type):
    parts = {
        name: FieldValue.missing(name, reference, REASON_NO_INFORME) for name in FIELDS
    }
    numerator = reported(parts[NUMERATOR])
    denominator = reported(parts[DENOMINATOR])

    return Classification(
        subject=subject,
        reference_date=reference,
        band=NO_DATA,
        numerator=numerator,
        denominator=denominator,
        share=Ratio(NO_DATA, None, numerator, denominator, REASON_NO_INFORME),
        reason=REASON_NO_INFORME,
        flags=_type_flags(cadastro_type),
        cadastro_type=cadastro_type,
    )


def _type_flags(cadastro_type):
    return (FIAGRO_IN_CADASTRO,) if cadastro_type == "FIAGRO" else ()


def classify_values(subject, reference, values, cadastro_type=None):
    """Classifica um assunto a partir de {campo: FieldValue} dos dois campos."""

    numerator = reported(values[NUMERATOR])
    denominator = reported(values[DENOMINATOR])
    flags = []

    if numerator.open_conflict or denominator.open_conflict:
        flags.append(OPEN_CONFLICT)

    flags.extend(_type_flags(cadastro_type))
    reason = None

    for amount in (numerator, denominator):
        if amount.state != PRESENT:
            reason = amount.reason
            break

    if reason is None and denominator.value == 0:
        reason = REASON_ZERO_DENOMINATOR
    elif reason is None and denominator.value < 0:
        reason = REASON_NEGATIVE_DENOMINATOR
    elif reason is None and numerator.value < 0:
        reason = REASON_NEGATIVE_NUMERATOR

    if reason is not None:
        return Classification(
            subject=subject,
            reference_date=reference,
            band=NO_DATA,
            numerator=numerator,
            denominator=denominator,
            share=Ratio(NO_DATA, None, numerator, denominator, reason),
            reason=reason,
            flags=tuple(flags),
            cadastro_type=cadastro_type,
        )

    if numerator.value > denominator.value:
        flags.insert(0, ABOVE_100)

    return Classification(
        subject=subject,
        reference_date=reference,
        band=band(numerator.value, denominator.value),
        numerator=numerator,
        denominator=denominator,
        share=percentage(numerator, denominator),
        flags=tuple(flags),
        cadastro_type=cadastro_type,
    )


def classify(connection, reference_date, subjects=None):
    """Classificacao de FIC-FIDC por assunto numa competencia (so le).

    Sem subjects: os assuntos com alguma observacao da tab_I na competencia.
    Com subjects: so eles; o que nao tem informe na competencia volta como
    sem_dado (sem_informe_na_competencia). Devolve uma tupla em ordem de
    assunto.
    """

    reference = month_end(reference_date)

    if subjects is not None:
        subjects = check_subjects(subjects)

        if not subjects:
            return ()

    with read_snapshot(connection):
        universe = informe_subjects(connection, reference)
        types = subject_types(connection)
        values = read_competence(connection, reference, FIELDS)

    wanted = (
        {(s.kind, s.id): s for s in subjects}
        if subjects is not None
        else dict(universe)
    )
    by_key = {(s.kind, s.id): v for s, v in values.items()}
    results = []

    for key, subject in sorted(wanted.items()):
        cadastro_type = types.get(key)

        if key not in universe:
            results.append(_no_informe(subject, reference, cadastro_type))
            continue

        found = by_key.get(key) or {
            name: FieldValue.missing(name, reference) for name in FIELDS
        }
        results.append(classify_values(subject, reference, found, cadastro_type))

    return tuple(results)
