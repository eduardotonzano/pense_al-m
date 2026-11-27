"""Regras do quota_class_map e classificacao de um rotulo de serie (decisao 8 de Fundos).

Cada regra tem um padrao ja normalizado, o tipo de casamento, o nivel e o
subtipo:
- 'inicio': a chave e igual ao padrao ou comeca com o padrao seguido de
  espaco ("subclasse senior serie 1" casa com "subclasse senior");
- 'igual': so a chave igual ao padrao.
Nivel 'senior' (subtipo 'nao_se_aplica') ou 'nao_senior' (subtipo
'mezanino', 'subordinada' ou 'ausente', quando o rotulo nao diz o subtipo;
nada e estimado).

Classificacao: o rotulo e normalizado como em quota_series.series_label_key
(QuotaSeriesRepository.normalize_series_label). Valem so as regras nao
rejeitadas e vigentes na competencia. Entre as que casam, vence a mais
especifica (o padrao mais longo); duas regras com o mesmo comprimento que
casam ficam em conflito e nenhuma vale. Sem regra: "ausente (rotulo nao
mapeado)". A situacao da revisao (proposto ou revisado) vai junto de cada
classificacao. So le o banco.
"""

from dataclasses import dataclass

from fundos.database import normalize_iso_date
from fundos.repositories.quota_series_repository import QuotaSeriesRepository


SENIOR = "senior"
NOT_SENIOR = "nao_senior"
LEVELS = (SENIOR, NOT_SENIOR)

NOT_APPLICABLE = "nao_se_aplica"
MEZZANINE = "mezanino"
SUBORDINATE = "subordinada"
ABSENT = "ausente"
SUBTYPES = (NOT_APPLICABLE, MEZZANINE, SUBORDINATE, ABSENT)

PROPOSED = "proposto"
REVIEWED = "revisado"
REJECTED = "rejeitado"
STATUSES = (PROPOSED, REVIEWED, REJECTED)

STARTS_WITH = "inicio"
EQUALS = "igual"
MATCH_TYPES = (STARTS_WITH, EQUALS)

REASON_UNMAPPED = "rotulo_nao_mapeado"
REASON_CONFLICT = "regras_em_conflito"
UNMAPPED_TEXT = "ausente (rotulo nao mapeado)"

TABLE = "quota_class_map"

_COLUMNS = (
    "id, pattern, match_type, level, subtype, origin_note, review_status, reviewer,"
    " reviewed_at, review_note, valid_from, valid_to"
)


@dataclass(frozen=True)
class QuotaClassRule:
    """Uma regra do quota_class_map, como gravada."""

    id: int
    pattern: str
    match_type: str
    level: str
    subtype: str
    review_status: str
    reviewer: str | None = None
    reviewed_at: str | None = None
    review_note: str | None = None
    valid_from: str | None = None
    valid_to: str | None = None
    origin_note: str | None = None

    def matches(self, label_key):
        """Indica se a chave normalizada casa com o padrao."""

        if self.match_type == EQUALS:
            return label_key == self.pattern

        return label_key == self.pattern or label_key.startswith(self.pattern + " ")

    def valid_on(self, reference_date):
        """Indica se a regra vale na competencia (vigencia aberta vale sempre)."""

        if self.valid_from is not None and reference_date < self.valid_from:
            return False

        return self.valid_to is None or reference_date <= self.valid_to


@dataclass(frozen=True)
class LabelClass:
    """A classificacao de um rotulo: a regra, o nivel e o subtipo, ou o motivo."""

    label_key: str
    level: str | None
    subtype: str | None
    rule: QuotaClassRule | None
    reason: str | None = None

    @property
    def mapped(self):
        return self.rule is not None

    @property
    def review_status(self):
        """proposto ou revisado (None sem regra)."""

        return None if self.rule is None else self.rule.review_status


def normalized(label):
    """O rotulo na forma de quota_series.series_label_key."""

    return QuotaSeriesRepository.normalize_series_label(label)


def map_table_exists(connection):
    """Indica se o banco tem o quota_class_map (migration 006)."""

    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (TABLE,)
        ).fetchone()
        is not None
    )


def _rule(row):
    return QuotaClassRule(
        id=int(row[0]),
        pattern=str(row[1]),
        match_type=str(row[2]),
        level=str(row[3]),
        subtype=str(row[4]),
        origin_note=row[5],
        review_status=str(row[6]),
        reviewer=row[7],
        reviewed_at=row[8],
        review_note=row[9],
        valid_from=row[10],
        valid_to=row[11],
    )


def all_rules(connection):
    """Todas as regras, rejeitadas inclusive, em ordem de id (so le)."""

    return tuple(
        _rule(row)
        for row in connection.execute("SELECT " + _COLUMNS + " FROM " + TABLE + " ORDER BY id")
    )


def load_rules(connection, reference_date=None):
    """As regras que valem: nao rejeitadas e, com a competencia, vigentes nela."""

    reference = None

    if reference_date is not None:
        reference = normalize_iso_date(reference_date, "Competencia")

    return tuple(
        rule
        for rule in all_rules(connection)
        if rule.review_status != REJECTED and (reference is None or rule.valid_on(reference))
    )


def classify_label(label, rules):
    """Classifica um rotulo (original ou ja normalizado) pelas regras dadas."""

    key = normalized(label)
    found = [rule for rule in rules if rule.review_status != REJECTED and rule.matches(key)]

    if not found:
        return LabelClass(key, None, None, None, REASON_UNMAPPED)

    longest = max(len(rule.pattern) for rule in found)
    best = [rule for rule in found if len(rule.pattern) == longest]

    if len(best) > 1:
        return LabelClass(key, None, None, None, REASON_CONFLICT)

    (rule,) = best
    return LabelClass(key, rule.level, rule.subtype, rule)
