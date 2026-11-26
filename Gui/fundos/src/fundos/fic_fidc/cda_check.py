"""Conferencia das posicoes do CDA em cotas de FIDC contra a tab_I (FU6.1, parte 4).

Por assunto (classe ou fundo) e competencia: a soma de
cda_fie.VL_MERC_POS_FINAL das posicoes identificadas (holdings) cujo
investido e FIDC no cadastro carregado, contra tab_I.TAB_I2H_VL_COTA_FIDC
do informe de FIDC da MESMA competencia. Nunca se compara uma competencia
com outra: quando um dos lados nao tem a competencia, o resultado e
sem_dado, e o resultado traz as duas datas.

O tipo do investido e o do cadastro (cda.loader.cadastro_types e
investee_label): o Tipo_Classe da classe ou, sem classe, o Tipo_Fundo do
fundo; classe e fundo de tipos diferentes sao "misto". So FIDC entra na
soma. FIAGRO, misto e fora do cadastro carregado (o banco so tem FIDC e
FIAGRO, entao FIF, FII e FIP caem aqui) saem a parte, com marca. O
consolidado confidencial nao separa o tipo e nunca entra na soma.

Dentro da tolerancia: |CDA - informe| <= max(R$ 1; 1% do informe), por
multiplicacao cruzada em Decimal exato. A divergencia e nota de qualidade,
calculada na leitura: nao vai para data_conflicts (que liga duas
observacoes do mesmo campo; a posicao do CDA nao e observacao), e nada e
gravado nem sobrescrito.

Estados: dentro_da_tolerancia, fora_da_tolerancia ou sem_dado, com o
motivo, nesta ordem:
1. holdings_nao_existe (banco sem a migration 004);
2. do lado do informe: sem_informe_na_competencia, campo_ausente,
   tipo_inesperado ou valor_negativo;
3. do lado do CDA: cda_nao_carregado_na_competencia,
   sem_posicao_em_cotas_no_cda, so_posicao_confidencial ou valor_negativo.

Marcas: conflito_aberto (no campo do informe), conflito_de_posicao
(posicao ou consolidado do assunto com conflito aberto), investido_misto,
investido_fora_do_cadastro, tem_posicao_confidencial e
sem_cotas_nos_dois_lados (informe 0 e nenhuma posicao: so contado).

Posicao atual por chave (detentor, investido, competencia, line_order): so
fontes ativas, depois prioridade, coleta mais recente e id, a mesma regra
do read_competence. O CNPJ do investido so e lido para buscar o tipo:
nenhum resultado o traz. Nunca casa por nome.
"""

from collections import defaultdict
from dataclasses import dataclass
from dataclasses import field
from decimal import Decimal
from decimal import Inexact
from decimal import Rounded
from decimal import localcontext

from fundos.cda import columns as cda_spec
from fundos.cda.loader import MIXED
from fundos.cda.loader import OUTSIDE
from fundos.cda.loader import cadastro_types
from fundos.cda.loader import investee_label
from fundos.fic_fidc.classification import NUMERATOR
from fundos.fic_fidc.classification import OPEN_CONFLICT
from fundos.fic_fidc.classification import REASON_NO_INFORME
from fundos.fic_fidc.classification import informe_subjects
from fundos.fic_fidc.classification import month_end
from fundos.fic_fidc.classification import subject_types
from fundos.indicators.reading import check_subjects
from fundos.indicators.reading import read_competence
from fundos.indicators.reading import read_snapshot
from fundos.indicators.values import CLASS_SUBJECT
from fundos.indicators.values import FUND_SUBJECT
from fundos.indicators.values import NO_DATA
from fundos.indicators.values import PRESENT
from fundos.indicators.values import Amount
from fundos.indicators.values import FieldValue
from fundos.indicators.values import Subject
from fundos.indicators.values import reported


INFORME_FIELD = NUMERATOR
CDA_FIELD = cda_spec.VALUE_FIELD
CONFIDENTIAL_FIELD = cda_spec.CONFIDENTIAL_VALUE_FIELD
FIDC = "FIDC"

WITHIN = "dentro_da_tolerancia"
OUTSIDE_TOLERANCE = "fora_da_tolerancia"
STATES = (WITHIN, OUTSIDE_TOLERANCE, NO_DATA)

REASON_NO_HOLDINGS_TABLE = "holdings_nao_existe"
REASON_NO_CDA = "cda_nao_carregado_na_competencia"
REASON_NEGATIVE = "valor_negativo"
REASON_NO_POSITION = "sem_posicao_em_cotas_no_cda"
REASON_ONLY_CONFIDENTIAL = "so_posicao_confidencial"

HOLDING_CONFLICT = "conflito_de_posicao"
MIXED_INVESTEE = "investido_misto"
OUTSIDE_INVESTEE = "investido_fora_do_cadastro"
HAS_CONFIDENTIAL = "tem_posicao_confidencial"
NOTHING_ON_EITHER_SIDE = "sem_cotas_nos_dois_lados"
FLAGS = (
    OPEN_CONFLICT,
    HOLDING_CONFLICT,
    MIXED_INVESTEE,
    OUTSIDE_INVESTEE,
    HAS_CONFIDENTIAL,
    NOTHING_ON_EITHER_SIDE,
)

HUNDRED = Decimal(100)
# Precisao larga o bastante para somas e produtos exatos; qualquer
# arredondamento levanta erro (Inexact e Rounded).
_EXACT_PRECISION = 1000


@dataclass(frozen=True)
class Tolerance:
    """Dentro: |CDA - informe| <= max(absolute; percent% do informe)."""

    percent: Decimal = Decimal(1)
    absolute: Decimal = Decimal(1)

    @property
    def text(self):
        return "max(R$ " + str(self.absolute) + "; " + str(self.percent) + "% do informe)"


TOLERANCE = Tolerance()


@dataclass(frozen=True)
class Position:
    """Uma posicao atual do CDA (identificada ou confidencial); o CNPJ nao aparece no repr."""

    id: int
    subject: Subject
    value: Decimal
    source_code: str
    investee_cnpj: str | None = field(default=None, repr=False)


@dataclass(frozen=True)
class HoldingSum:
    """Soma de posicoes de um assunto numa competencia, com as posicoes de origem."""

    state: str
    value: Decimal | None
    field_name: str
    reference_date: str | None
    holding_ids: tuple[int, ...] = ()
    lines: int = 0
    source_codes: tuple[str, ...] = ()
    reason: str | None = None


@dataclass(frozen=True)
class CdaCheck:
    """A conferencia de um assunto: os dois lados, as duas datas e o estado."""

    subject: Subject
    informe_reference_date: str
    cda_reference_date: str | None
    state: str
    informe: Amount
    cda_fidc: HoldingSum
    cda_others: tuple[tuple[str, HoldingSum], ...]
    confidential: HoldingSum
    difference: Decimal | None
    tolerance: Tolerance
    reason: str | None = None
    flags: tuple[str, ...] = ()
    holder_type: str | None = None

    @property
    def cda_lines(self):
        """Linhas do CDA do assunto na competencia (identificadas e confidenciais)."""

        return (
            self.cda_fidc.lines
            + sum(item.lines for _, item in self.cda_others)
            + self.confidential.lines
        )


def _sum(values):
    with localcontext() as context:
        context.prec = _EXACT_PRECISION
        context.traps[Inexact] = True
        context.traps[Rounded] = True
        return sum(values, Decimal(0))


def within_tolerance(cda, informe, tolerance=TOLERANCE):
    """|cda - informe| <= max(absoluto; percentual do informe), sem divisao.

    So com Decimal e informe maior ou igual a 0 (o negativo e sem dado antes).
    """

    for value in (cda, informe):
        if not isinstance(value, Decimal) or not value.is_finite():
            raise TypeError("A tolerancia so e conferida com Decimal finito.")

    if informe < 0:
        raise ValueError("O valor do informe nao pode ser negativo.")

    with localcontext() as context:
        context.prec = _EXACT_PRECISION
        context.traps[Inexact] = True
        context.traps[Rounded] = True
        difference = abs(cda - informe)

        return (
            difference <= tolerance.absolute
            or difference * HUNDRED <= informe * tolerance.percent
        )


def holdings_table_exists(connection):
    """Indica se o banco tem as tabelas da migration 004 (so le)."""

    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
        " AND name IN ('holdings', 'confidential_holdings')"
    ).fetchall()

    return len(rows) == 2


def cda_competences(connection):
    """Competencias (em ordem) com posicao do CDA de fonte ativa; None sem a 004."""

    if not holdings_table_exists(connection):
        return None

    rows = connection.execute(
        "SELECT h.reference_date FROM holdings h JOIN sources s ON s.id = h.source_id"
        " WHERE s.active = 1"
        " UNION SELECT c.reference_date FROM confidential_holdings c"
        " JOIN sources s ON s.id = c.source_id WHERE s.active = 1"
        " ORDER BY 1"
    ).fetchall()

    return tuple(row[0] for row in rows)


def _subject(fund_id, class_id, fund_cnpj, class_cnpj):
    if fund_id is not None:
        return Subject(FUND_SUBJECT, int(fund_id), fund_cnpj)

    return Subject(CLASS_SUBJECT, int(class_id), class_cnpj)


def _current(connection, table, partition, reference, investee):
    rows = connection.execute(
        "SELECT h.id, h.fund_id, h.fund_class_id, h.market_value, h.source_code, "
        + investee
        + ", f.cnpj, c.cnpj"
        " FROM (SELECT h.*, s.code AS source_code, ROW_NUMBER() OVER ("
        "   PARTITION BY " + partition + ""
        "   ORDER BY s.priority DESC, h.collected_at DESC, h.id DESC) AS rn"
        "  FROM " + table + " h JOIN sources s ON s.id = h.source_id"
        "  WHERE s.active = 1 AND h.reference_date = ?) h"
        " LEFT JOIN funds f ON f.id = h.fund_id"
        " LEFT JOIN fund_classes c ON c.id = h.fund_class_id"
        " WHERE h.rn = 1 ORDER BY h.id",
        (reference,),
    ).fetchall()

    return tuple(
        Position(
            id=int(row[0]),
            subject=_subject(row[1], row[2], row[6], row[7]),
            value=Decimal(row[3]),
            source_code=str(row[4]),
            investee_cnpj=None if row[5] is None else str(row[5]),
        )
        for row in rows
    )


def current_holdings(connection, reference_date):
    """Posicoes identificadas atuais da competencia, uma por chave (so le)."""

    return _current(
        connection,
        "holdings",
        "h.fund_id, h.fund_class_id, h.investee_cnpj, h.reference_date, h.line_order",
        month_end(reference_date),
        "h.investee_cnpj",
    )


def current_confidential(connection, reference_date):
    """Consolidados confidenciais atuais da competencia, um por assunto (so le)."""

    return _current(
        connection,
        "confidential_holdings",
        "h.fund_id, h.fund_class_id, h.reference_date",
        month_end(reference_date),
        "NULL",
    )


def _conflicted_subjects(connection, reference):
    """(tipo, id) dos assuntos com posicao ou consolidado em conflito aberto."""

    found = set()

    for table, conflicts, first, second in (
        ("holdings", "holding_conflicts", "holding_a_id", "holding_b_id"),
        (
            "confidential_holdings",
            "confidential_holding_conflicts",
            "confidential_holding_a_id",
            "confidential_holding_b_id",
        ),
    ):
        rows = connection.execute(
            "SELECT h.fund_id, h.fund_class_id FROM " + conflicts + " k"
            " JOIN " + table + " h ON h.id = k." + first + " OR h.id = k." + second
            + " WHERE k.status = 'open' AND k.reference_date = ?",
            (reference,),
        ).fetchall()

        for fund_id, class_id in rows:
            found.add(
                (FUND_SUBJECT, int(fund_id))
                if fund_id is not None
                else (CLASS_SUBJECT, int(class_id))
            )

    return found


def _holding_sum(positions, field_name, reference, reason):
    if not positions:
        return HoldingSum(NO_DATA, None, field_name, reference, reason=reason)

    return HoldingSum(
        state=PRESENT,
        value=_sum(p.value for p in positions),
        field_name=field_name,
        reference_date=reference,
        holding_ids=tuple(p.id for p in positions),
        lines=len(positions),
        source_codes=tuple(sorted({p.source_code for p in positions})),
    )


def _check(subject, reference, context):
    key = (subject.kind, subject.id)
    flags = []

    if key not in context["informe_universe"]:
        informe = reported(FieldValue.missing(INFORME_FIELD, reference, REASON_NO_INFORME))
    else:
        informe = reported(
            context["informe_values"].get(key) or FieldValue.missing(INFORME_FIELD, reference)
        )

    if informe.open_conflict:
        flags.append(OPEN_CONFLICT)

    cda_loaded = context["cda_loaded"]
    cda_reference = reference if cda_loaded else None
    identified = context["identified"].get(key, [])
    confidential_rows = context["confidential"].get(key, [])

    if not context["has_table"]:
        empty_reason = REASON_NO_HOLDINGS_TABLE
    elif not cda_loaded:
        empty_reason = REASON_NO_CDA
    else:
        empty_reason = REASON_NO_POSITION

    groups = defaultdict(list)

    for position in identified:
        groups[investee_label(position.investee_cnpj, context["classes"], context["funds"])].append(
            position
        )

    fidc_positions = groups.pop(FIDC, [])

    if fidc_positions:
        fidc = _holding_sum(fidc_positions, CDA_FIELD, cda_reference, None)
    elif identified:
        # Ha posicoes identificadas, nenhuma em FIDC: o CDA informa 0 em FIDC.
        fidc = HoldingSum(PRESENT, Decimal(0), CDA_FIELD, cda_reference)
    else:
        fidc = _holding_sum((), CDA_FIELD, cda_reference, empty_reason)

    others = tuple(
        (label, _holding_sum(groups[label], CDA_FIELD, cda_reference, None))
        for label in sorted(groups)
    )
    confidential = _holding_sum(
        confidential_rows, CONFIDENTIAL_FIELD, cda_reference, empty_reason
    )

    if MIXED in groups:
        flags.append(MIXED_INVESTEE)

    if OUTSIDE in groups:
        flags.append(OUTSIDE_INVESTEE)

    if confidential_rows:
        flags.append(HAS_CONFIDENTIAL)

    if key in context["conflicted"]:
        flags.append(HOLDING_CONFLICT)

    reason = None
    difference = None

    if not context["has_table"]:
        reason = REASON_NO_HOLDINGS_TABLE
    elif informe.state != PRESENT:
        reason = informe.reason
    elif informe.value < 0:
        reason = REASON_NEGATIVE
    elif not cda_loaded:
        reason = REASON_NO_CDA
    elif not identified and not confidential_rows:
        reason = REASON_NO_POSITION

        if informe.value == 0:
            flags.append(NOTHING_ON_EITHER_SIDE)
    elif not identified:
        reason = REASON_ONLY_CONFIDENTIAL
    elif fidc.value < 0:
        reason = REASON_NEGATIVE

    if reason is None:
        with localcontext() as exact:
            exact.prec = _EXACT_PRECISION
            exact.traps[Inexact] = True
            exact.traps[Rounded] = True
            difference = fidc.value - informe.value

        state = (
            WITHIN
            if within_tolerance(fidc.value, informe.value, context["tolerance"])
            else OUTSIDE_TOLERANCE
        )
    else:
        state = NO_DATA

    return CdaCheck(
        subject=subject,
        informe_reference_date=reference,
        cda_reference_date=cda_reference,
        state=state,
        informe=informe,
        cda_fidc=fidc,
        cda_others=others,
        confidential=confidential,
        difference=difference,
        tolerance=context["tolerance"],
        reason=reason,
        flags=tuple(flags),
        holder_type=context["holder_types"].get(key),
    )


def cda_vs_informe(connection, reference_date, subjects=None, tolerance=TOLERANCE):
    """Conferencia do CDA em cotas de FIDC contra a tab_I, por assunto (so le).

    Sem subjects: os assuntos com alguma observacao da tab_I na competencia
    mais os detentores com posicao do CDA nela. Com subjects: so eles.
    Devolve uma tupla de CdaCheck em ordem de assunto.
    """

    reference = month_end(reference_date)

    if not isinstance(tolerance, Tolerance):
        raise TypeError("Use Tolerance para a tolerancia.")

    if subjects is not None:
        subjects = check_subjects(subjects)

        if not subjects:
            return ()

    with read_snapshot(connection):
        informe_universe = informe_subjects(connection, reference)
        informe_values = {
            (s.kind, s.id): values[INFORME_FIELD]
            for s, values in read_competence(connection, reference, (INFORME_FIELD,)).items()
        }
        holder_types = subject_types(connection)
        has_table = holdings_table_exists(connection)
        identified = confidential = ()
        conflicted = set()
        classes = funds = {}

        if has_table:
            identified = current_holdings(connection, reference)
            confidential = current_confidential(connection, reference)
            conflicted = _conflicted_subjects(connection, reference)
            classes, funds = cadastro_types(connection)

    by_identified = defaultdict(list)
    by_confidential = defaultdict(list)
    holders = {}

    for position in identified:
        key = (position.subject.kind, position.subject.id)
        by_identified[key].append(position)
        holders[key] = position.subject

    for position in confidential:
        key = (position.subject.kind, position.subject.id)
        by_confidential[key].append(position)
        holders[key] = position.subject

    if subjects is not None:
        wanted = {(s.kind, s.id): s for s in subjects}
    else:
        wanted = {**holders, **informe_universe}

    context = {
        "informe_universe": informe_universe,
        "informe_values": informe_values,
        "holder_types": holder_types,
        "has_table": has_table,
        "cda_loaded": bool(identified or confidential),
        "identified": by_identified,
        "confidential": by_confidential,
        "conflicted": conflicted,
        "classes": classes,
        "funds": funds,
        "tolerance": tolerance,
    }

    return tuple(_check(subject, reference, context) for _, subject in sorted(wanted.items()))
