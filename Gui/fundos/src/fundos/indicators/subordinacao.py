"""Subordinacao das classes de FIDC, calculada na leitura (FU6.3, decisao 8 de Fundos).

Formula: soma de TAB_X_QT_COTA x TAB_X_VL_COTA das series nao seniores /
soma de todas as series, na tab_X_2 da mesma competencia. O valor de cada
serie e o produto exato em Decimal, sem arredondar; o percentual tem 28
digitos e nao e arredondado (arredondar e decisao de exibicao). Nada e
gravado: o resultado e calculado por cima das observacoes, que continuam
sendo o dado da CVM.

Cada serie e classificada pelo quota_class_map (migration 006), pelo
rotulo normalizado, com as regras nao rejeitadas e vigentes na competencia
(proposto ou revisado; a situacao vai em cada resultado). Cada insumo sai
com o campo, a competencia, a fonte, a observacao e a coleta.

Estado "calculado" ou "sem_dado", com o motivo, nesta ordem:
1. mapa_nao_existe: o banco nao tem a migration 006;
2. sem_tab_X_2_na_competencia: o assunto nao tem serie na tab_X_2;
3. rotulo_nao_mapeado ou regras_em_conflito: alguma serie sem regra; nada
   parcial ("ausente (rotulo nao mapeado)");
4. campo_ausente, tipo_inesperado ou valor_negativo: na quantidade ou no
   valor da cota de alguma serie;
5. soma_das_series_zero: a soma de todas as series e 0.

Partes: senior, mezanino, subordinada e subtipo ausente, cada uma com as
series de origem e a parcela no total, quando existem.

Camadas (colchao): o do senior e a subordinacao total; o do mezanino e
subordinada / total, so com mezanino e nenhum subtipo ausente. Varios
mezaninos somam como uma camada.

Marcas:
- sem_serie_subordinada: so ha serie senior; a subordinacao e 0 e a
  exibicao diz "sem serie subordinada", nunca 0% sem explicacao;
- ordem_entre_subordinadas_nao_informada: 2 ou mais series de subtipo
  subordinada ou ausente, com ou sem mezanino. So avisa: nao muda a
  subordinacao total nem o colchao do mezanino, e a ordem nunca e
  inferida;
- subtipo_ausente e mais_de_uma_serie_mezanino;
- pl_ausente, pl_nao_positivo e soma_fora_de_1pct_do_pl: a conferencia com
  tab_IV.TAB_IV_A_VL_PL (1% puro, por multiplicacao cruzada). A formula nao
  usa o PL: o resultado continua calculado, com a marca;
- mapa_proposto: alguma regra usada ainda nao foi revisada por uma pessoa;
- conflito_aberto: algum insumo tem conflito aberto no banco.
"""

from dataclasses import dataclass
from decimal import Decimal
from decimal import Inexact
from decimal import Rounded
from decimal import localcontext

from fundos.database import normalize_iso_date
from fundos.indicators.reading import check_subjects
from fundos.indicators.reading import previous_month_end
from fundos.indicators.reading import read_competence
from fundos.indicators.reading import read_series_competence
from fundos.indicators.reading import read_snapshot
from fundos.indicators.reading import subjects_with_table
from fundos.indicators.values import NO_DATA
from fundos.indicators.values import PRESENT
from fundos.indicators.values import Amount
from fundos.indicators.values import FieldValue
from fundos.indicators.values import Ratio
from fundos.indicators.values import Subject
from fundos.indicators.values import percentage
from fundos.quota_classes.mapping import ABSENT
from fundos.quota_classes.mapping import MEZZANINE
from fundos.quota_classes.mapping import NOT_SENIOR
from fundos.quota_classes.mapping import PROPOSED
from fundos.quota_classes.mapping import REASON_UNMAPPED
from fundos.quota_classes.mapping import REVIEWED
from fundos.quota_classes.mapping import SENIOR
from fundos.quota_classes.mapping import SUBORDINATE
from fundos.quota_classes.mapping import classify_label
from fundos.quota_classes.mapping import load_rules
from fundos.quota_classes.mapping import map_table_exists


QUANTITY = "tab_X_2.TAB_X_QT_COTA"
UNIT_VALUE = "tab_X_2.TAB_X_VL_COTA"
PL = "tab_IV.TAB_IV_A_VL_PL"
SERIES_FIELDS = (QUANTITY, UNIT_VALUE)
INFORME_TABLE = "tab_I"

FORMULA = (
    "soma de TAB_X_QT_COTA x TAB_X_VL_COTA das series nao seniores / soma de todas "
    "as series (tab_X_2, mesma competencia)"
)

CALCULATED = "calculado"
STATES = (CALCULATED, NO_DATA)

REASON_NO_MAP = "mapa_nao_existe"
REASON_NO_TAB_X_2 = "sem_tab_X_2_na_competencia"
REASON_NEGATIVE = "valor_negativo"
REASON_ZERO_TOTAL = "soma_das_series_zero"

NO_SUBORDINATE = "sem_serie_subordinada"
ORDER_NOT_INFORMED = "ordem_entre_subordinadas_nao_informada"
ABSENT_SUBTYPE = "subtipo_ausente"
MULTIPLE_MEZZANINE = "mais_de_uma_serie_mezanino"
SUM_OUTSIDE_PL = "soma_fora_de_1pct_do_pl"
PL_ABSENT = "pl_ausente"
PL_NOT_POSITIVE = "pl_nao_positivo"
PROPOSED_MAP = "mapa_proposto"
OPEN_CONFLICT = "conflito_aberto"
FLAGS = (
    NO_SUBORDINATE,
    ORDER_NOT_INFORMED,
    ABSENT_SUBTYPE,
    MULTIPLE_MEZZANINE,
    SUM_OUTSIDE_PL,
    PL_ABSENT,
    PL_NOT_POSITIVE,
    PROPOSED_MAP,
    OPEN_CONFLICT,
)

WITHIN_1PCT = "dentro_de_1pct"
OUTSIDE_1PCT = "fora_de_1pct"
PL_CHECKS = (WITHIN_1PCT, OUTSIDE_1PCT, PL_ABSENT, PL_NOT_POSITIVE)

PART_SENIOR = "senior"
PART_MEZZANINE = "mezanino"
PART_SUBORDINATE = "subordinada"
PART_ABSENT = "subtipo_ausente"
PARTS = (PART_SENIOR, PART_MEZZANINE, PART_SUBORDINATE, PART_ABSENT)

LAYER_SENIOR = "senior"
LAYER_MEZZANINE = "mezanino"

HUNDRED = Decimal(100)
_EXACT_PRECISION = 1000


@dataclass(frozen=True)
class SeriesLine:
    """Uma serie: a classificacao pelo mapa, os dois insumos e o valor (QT x VL)."""

    series_id: int
    label_key: str | None
    level: str | None
    subtype: str | None
    rule_id: int | None
    rule_status: str | None
    quantity: FieldValue
    unit_value: FieldValue
    value: Decimal | None
    reason: str | None = None


@dataclass(frozen=True)
class Part:
    """A soma de uma parte (senior, mezanino, subordinada ou subtipo ausente)."""

    name: str
    value: Decimal
    series_ids: tuple[int, ...]
    share: Ratio


@dataclass(frozen=True)
class Layer:
    """O colchao de uma camada: o que esta abaixo dela, em % do total."""

    name: str
    cushion: Ratio


@dataclass(frozen=True)
class SubordinacaoResult:
    """A subordinacao de um assunto (classe ou fundo) numa competencia."""

    subject: Subject
    reference_date: str
    state: str
    series: tuple[SeriesLine, ...]
    total: Decimal | None
    subordinacao_total: Ratio | None
    parts: tuple[Part, ...]
    layers: tuple[Layer, ...]
    pl: FieldValue
    pl_check: str | None
    map_review: str | None
    rules_used: tuple[int, ...]
    reason: str | None = None
    flags: tuple[str, ...] = ()
    formula: str = FORMULA

    def part(self, name):
        """A parte pelo nome, ou None."""

        return next((part for part in self.parts if part.name == name), None)

    def layer(self, name):
        """A camada pelo nome, ou None."""

        return next((layer for layer in self.layers if layer.name == name), None)


def _product(first, second):
    with localcontext() as context:
        context.prec = _EXACT_PRECISION
        context.traps[Inexact] = True
        context.traps[Rounded] = True
        return first * second


def _sum(values):
    with localcontext() as context:
        context.prec = _EXACT_PRECISION
        context.traps[Inexact] = True
        context.traps[Rounded] = True
        return sum(values, Decimal(0))


def within_one_percent(total, pl):
    """|total - PL| <= 1% do PL, por multiplicacao cruzada (PL maior que 0)."""

    with localcontext() as context:
        context.prec = _EXACT_PRECISION
        context.traps[Inexact] = True
        context.traps[Rounded] = True
        return abs(total - pl) * HUNDRED <= pl


def _month_end(reference_date):
    reference = normalize_iso_date(reference_date, "Competencia")
    previous_month_end(reference)
    return reference


def _amount(value):
    return Amount(PRESENT, value, ())


def _line(series_values, rules):
    quantity = series_values.values[QUANTITY]
    unit_value = series_values.values[UNIT_VALUE]

    if series_values.label_key is None:
        label = None
    else:
        label = classify_label(series_values.label_key, rules)

    rule = None if label is None else label.rule
    reason = None
    value = None

    for field in (quantity, unit_value):
        if field.state != PRESENT:
            reason = field.reason
            break

    if reason is None and (quantity.value < 0 or unit_value.value < 0):
        reason = REASON_NEGATIVE

    if reason is None:
        value = _product(quantity.value, unit_value.value)

    return SeriesLine(
        series_id=series_values.series_id,
        label_key=series_values.label_key,
        level=None if label is None else label.level,
        subtype=None if label is None else label.subtype,
        rule_id=None if rule is None else rule.id,
        rule_status=None if rule is None else rule.review_status,
        quantity=quantity,
        unit_value=unit_value,
        value=value,
        reason=reason,
    ), (label.reason if label is not None and not label.mapped else None)


def _no_data(subject, reference, reason, lines=(), pl=None, rules_used=(), map_review=None, flags=()):
    return SubordinacaoResult(
        subject=subject,
        reference_date=reference,
        state=NO_DATA,
        series=tuple(lines),
        total=None,
        subordinacao_total=None,
        parts=(),
        layers=(),
        pl=pl or FieldValue.missing(PL, reference),
        pl_check=None,
        map_review=map_review,
        rules_used=tuple(rules_used),
        reason=reason,
        flags=tuple(flags),
    )


def _structural_flags(lines):
    not_senior = [line for line in lines if line.level == NOT_SENIOR]
    flags = []

    if not not_senior:
        flags.append(NO_SUBORDINATE)

    if sum(1 for line in not_senior if line.subtype in (SUBORDINATE, ABSENT)) >= 2:
        flags.append(ORDER_NOT_INFORMED)

    if any(line.subtype == ABSENT for line in not_senior):
        flags.append(ABSENT_SUBTYPE)

    if sum(1 for line in not_senior if line.subtype == MEZZANINE) >= 2:
        flags.append(MULTIPLE_MEZZANINE)

    return flags


def _pl_check(total, pl):
    if pl.state != PRESENT:
        return PL_ABSENT

    if pl.value <= 0:
        return PL_NOT_POSITIVE

    return WITHIN_1PCT if within_one_percent(total, pl.value) else OUTSIDE_1PCT


def _result(subject, reference, by_series, pl, rules):
    lines = []
    unmapped_reason = None

    for _, series_values in sorted(by_series.items()):
        line, label_reason = _line(series_values, rules)
        lines.append(line)

        if line.rule_id is None and unmapped_reason is None:
            unmapped_reason = label_reason or REASON_UNMAPPED

    rules_used = tuple(sorted({line.rule_id for line in lines if line.rule_id is not None}))
    statuses = {line.rule_status for line in lines if line.rule_status is not None}
    map_review = None if not statuses else (REVIEWED if statuses == {REVIEWED} else PROPOSED)
    flags = []

    if PROPOSED in statuses:
        flags.append(PROPOSED_MAP)

    if any(line.quantity.open_conflict or line.unit_value.open_conflict for line in lines) or pl.open_conflict:
        flags.append(OPEN_CONFLICT)

    if unmapped_reason is not None:
        return _no_data(subject, reference, unmapped_reason, lines, pl, rules_used, map_review, flags)

    value_reason = next((line.reason for line in lines if line.reason is not None), None)
    structural = _structural_flags(lines)

    if value_reason is not None:
        return _no_data(
            subject, reference, value_reason, lines, pl, rules_used, map_review, structural + flags
        )

    total = _sum(line.value for line in lines)

    if total == 0:
        return _no_data(
            subject, reference, REASON_ZERO_TOTAL, lines, pl, rules_used, map_review, structural + flags
        )

    groups = {
        PART_SENIOR: [line for line in lines if line.level == SENIOR],
        PART_MEZZANINE: [line for line in lines if line.subtype == MEZZANINE],
        PART_SUBORDINATE: [line for line in lines if line.subtype == SUBORDINATE],
        PART_ABSENT: [line for line in lines if line.subtype == ABSENT],
    }
    total_amount = _amount(total)
    parts = tuple(
        Part(
            name=name,
            value=_sum(line.value for line in groups[name]),
            series_ids=tuple(line.series_id for line in groups[name]),
            share=percentage(_amount(_sum(line.value for line in groups[name])), total_amount),
        )
        for name in PARTS
        if groups[name]
    )
    not_senior = _sum(line.value for line in lines if line.level == NOT_SENIOR)
    subordination = percentage(_amount(not_senior), total_amount)
    layers = [Layer(LAYER_SENIOR, subordination)]

    if groups[PART_MEZZANINE] and not groups[PART_ABSENT]:
        below_mezzanine = _sum(line.value for line in groups[PART_SUBORDINATE])
        layers.append(Layer(LAYER_MEZZANINE, percentage(_amount(below_mezzanine), total_amount)))

    check = _pl_check(total, pl)
    pl_flags = []

    if check == PL_ABSENT:
        pl_flags.append(PL_ABSENT)
    elif check == PL_NOT_POSITIVE:
        pl_flags.append(PL_NOT_POSITIVE)
    elif check == OUTSIDE_1PCT:
        pl_flags.append(SUM_OUTSIDE_PL)

    return SubordinacaoResult(
        subject=subject,
        reference_date=reference,
        state=CALCULATED,
        series=tuple(lines),
        total=total,
        subordinacao_total=subordination,
        parts=parts,
        layers=tuple(layers),
        pl=pl,
        pl_check=check,
        map_review=map_review,
        rules_used=rules_used,
        flags=tuple(structural + pl_flags + flags),
    )


def subordinacao(connection, reference_date, subjects=None):
    """Subordinacao por assunto (classe ou fundo) numa competencia (so le).

    Sem subjects: os assuntos com a tab_I na competencia mais os pais de
    series com a tab_X_2 nela. Devolve uma tupla em ordem de assunto.
    """

    reference = _month_end(reference_date)

    if subjects is not None:
        subjects = check_subjects(subjects)

        if not subjects:
            return ()

    with read_snapshot(connection):
        has_map = map_table_exists(connection)
        rules = load_rules(connection, reference) if has_map else ()
        series = read_series_competence(connection, reference, SERIES_FIELDS, subjects)
        universe = subjects_with_table(connection, reference, INFORME_TABLE)
        pl_values = {
            (subject.kind, subject.id): values[PL]
            for subject, values in read_competence(connection, reference, (PL,), subjects).items()
        }

    by_key = {(parent.kind, parent.id): (parent, values) for parent, values in series.items()}

    if subjects is not None:
        wanted = {(s.kind, s.id): s for s in subjects}
    else:
        wanted = {**universe, **{key: parent for key, (parent, _) in by_key.items()}}

    results = []

    for key, subject in sorted(wanted.items()):
        pl = pl_values.get(key) or FieldValue.missing(PL, reference)

        if not has_map:
            results.append(_no_data(subject, reference, REASON_NO_MAP, pl=pl))
        elif key not in by_key:
            results.append(_no_data(subject, reference, REASON_NO_TAB_X_2, pl=pl))
        else:
            results.append(_result(subject, reference, by_key[key][1], pl, rules))

    return tuple(results)
