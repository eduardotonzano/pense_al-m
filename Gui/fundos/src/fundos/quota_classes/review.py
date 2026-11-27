"""Relatorio de revisao e revisao de uma regra do quota_class_map (decisao 8 de Fundos).

Relatorio (so le; so contagens e rotulos normalizados de serie, nunca CNPJ,
nome, valor de linha nem o rotulo original):
- as regras, com a situacao da revisao, o papel do revisor, a data e a
  vigencia, e quantas series e rotulos cada uma classifica por competencia;
- os rotulos de FIDC sem regra (ou com regras em conflito);
- os rotulos novos desde a ultima revisao (primeira coleta do rotulo depois
  da maior data de revisao); sem revisao nenhuma, so a contagem;
- os assuntos com 2 ou mais series nao seniores e nenhum mezanino (a ordem
  entre as subordinadas nao e informada) e as series com subtipo ausente;
- as series de FIAGRO, fora desta etapa: as subclasses de FIAGRO nao dizem
  senior ou subordinada.
As series de FIDC de uma competencia sao as que tem observacao tab_X_2 nela,
de fonte ativa. O rotulo e o normalizado (quota_series.series_label_key).

Revisao: so uma pessoa revisa, identificada por um papel da lista fechada
(nunca pelo nome). A nota e conferida antes de tudo: so ASCII imprimivel,
ate 200 caracteres, sem quebra de linha, sem sequencia de 11 digitos ou
mais e sem mascara de CPF ou CNPJ; o erro nunca repete o texto da nota.
review_rule grava so dentro da transacao de quem chama: atualiza as colunas
da revisao (os triggers da 006 so deixam ir de proposto para revisado ou
rejeitado, ou de revisado para rejeitado) e grava uma linha no audit_log,
com o antes e o depois.
"""

import json
import re
from collections import Counter
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone

from fundos.database import normalize_iso_date
from fundos.database import utc_now
from fundos.quota_classes.mapping import MEZZANINE
from fundos.quota_classes.mapping import NOT_SENIOR
from fundos.quota_classes.mapping import PROPOSED
from fundos.quota_classes.mapping import REJECTED
from fundos.quota_classes.mapping import REVIEWED
from fundos.quota_classes.mapping import ABSENT
from fundos.quota_classes.mapping import all_rules
from fundos.quota_classes.mapping import classify_label
from fundos.quota_classes.mapping import load_rules


REVIEWERS = ("papel:dono_da_frente_fundos", "papel:revisor_fundos")
ACTION = "quota_class_map_revisao"
ENTITY_TYPE = "quota_class_map"
MAX_NOTE = 200

# Transicoes que a revisao aceita (as mesmas dos triggers da 006).
TRANSITIONS = {PROPOSED: (REVIEWED, REJECTED), REVIEWED: (REJECTED,)}

_LONG_DIGITS = re.compile(r"[0-9]{11,}")
_MASK = re.compile(
    r"[0-9]{3}\.[0-9]{3}\.[0-9]{3}-[0-9]{2}|[0-9A-Za-z]{2}\.[0-9A-Za-z]{3}\.[0-9A-Za-z]{3}/[0-9A-Za-z]{4}-[0-9]{2}"
)
_PRINTABLE_ASCII = re.compile(r"[ -~]*")

_SERIES_LABEL_FIELDS = "tab\\_X\\_%.TAB\\_X\\_CLASSE\\_SERIE"
_TAB_X_2 = "tab\\_X\\_2.%"
_TAB_X = "tab\\_X\\_%"
_FIAGRO_SUBCLASS = "inf\\_mensal\\_fiagro\\_subclasse.%"


class ReviewError(Exception):
    """Erro da revisao ou do relatorio, com mensagem sem valor de linha nem texto de nota."""


def check_note(note):
    """Recusa a nota fora da regra; a mensagem diz so o motivo, nunca o texto."""

    if not isinstance(note, str) or not note.strip():
        raise ReviewError("Nota recusada: a nota e obrigatoria.")

    if "\n" in note or "\r" in note:
        raise ReviewError("Nota recusada: sem quebra de linha.")

    if _PRINTABLE_ASCII.fullmatch(note) is None:
        raise ReviewError("Nota recusada: so ASCII imprimivel.")

    if len(note) > MAX_NOTE:
        raise ReviewError("Nota recusada: ate " + str(MAX_NOTE) + " caracteres.")

    if _LONG_DIGITS.search(note):
        raise ReviewError("Nota recusada: sem sequencia de 11 digitos ou mais.")

    if _MASK.search(note):
        raise ReviewError("Nota recusada: sem mascara de CPF ou CNPJ.")

    return note.strip()


def check_reviewer(reviewer):
    """So um papel da lista fechada; a mensagem nunca repete o que foi informado."""

    if reviewer not in REVIEWERS:
        raise ReviewError(
            "Revisor recusado: use um papel da lista (" + ", ".join(REVIEWERS) + "), nunca um nome."
        )

    return reviewer


def check_status(status):
    if status not in (REVIEWED, REJECTED):
        raise ReviewError("Situacao recusada: use revisado ou rejeitado.")

    return status


def canonical_json(data):
    return json.dumps(data, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _review_columns(row):
    return {
        "review_status": row[1],
        "reviewer": row[2],
        "reviewed_at": row[3],
        "review_note": row[4],
    }


def _read_rule(connection, rule_id):
    if isinstance(rule_id, bool) or not isinstance(rule_id, int) or rule_id < 1:
        raise ReviewError("Regra recusada: o id e um inteiro a partir de 1.")

    row = connection.execute(
        "SELECT id, review_status, reviewer, reviewed_at, review_note, pattern FROM quota_class_map"
        " WHERE id = ?",
        (rule_id,),
    ).fetchone()

    if row is None:
        raise ReviewError("Regra nao encontrada no quota_class_map.")

    return row


@dataclass(frozen=True)
class ReviewPlan:
    """O que a revisao faria: a regra, a situacao antes e depois, ou nada."""

    rule_id: int
    pattern: str
    before: str
    after: str
    changes: bool


@dataclass(frozen=True)
class ReviewResult:
    """O que a revisao gravou: a regra, a linha do audit_log e as situacoes."""

    plan: ReviewPlan
    audit_id: int | None


def plan_review(connection, rule_id, status):
    """Confere a revisao sem gravar: transicao aceita, ou nada a revisar (so le)."""

    check_status(status)
    row = _read_rule(connection, rule_id)
    before = str(row[1])

    if before == status:
        return ReviewPlan(int(row[0]), str(row[5]), before, status, False)

    if status not in TRANSITIONS.get(before, ()):
        raise ReviewError(
            "Revisao recusada: a regra esta " + before + " e nao pode ir para " + status + "."
        )

    return ReviewPlan(int(row[0]), str(row[5]), before, status, True)


def review_rule(connection, rule_id, status, reviewer, note, reviewed_at=None):
    """Revisa uma regra dentro da transacao de quem chama, com uma linha no audit_log."""

    note = check_note(note)
    check_reviewer(reviewer)

    if not connection.in_transaction:
        raise ReviewError("A revisao so e gravada dentro de uma transacao de quem chama.")

    plan = plan_review(connection, rule_id, status)

    if not plan.changes:
        return ReviewResult(plan, None)

    before = _review_columns(_read_rule(connection, rule_id))
    when = reviewed_at or utc_now()
    connection.execute(
        "UPDATE quota_class_map SET review_status = ?, reviewer = ?, reviewed_at = ?,"
        " review_note = ? WHERE id = ?",
        (status, reviewer, when, note, rule_id),
    )
    after = _review_columns(_read_rule(connection, rule_id))
    audit_id = connection.execute(
        "INSERT INTO audit_log (actor, action, entity_type, entity_id, before_data, after_data, reason)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (reviewer, ACTION, ENTITY_TYPE, rule_id, canonical_json(before), canonical_json(after), note),
    ).lastrowid

    return ReviewResult(plan, int(audit_id))


@dataclass(frozen=True)
class UnmappedLabel:
    """Um rotulo normalizado sem regra na competencia (ou com regras em conflito)."""

    label_key: str
    series: int
    variants: int
    reason: str


@dataclass(frozen=True)
class CompetenceReview:
    """O que o mapa classifica numa competencia: so contagens e rotulos sem regra."""

    reference_date: str
    series: int
    label_keys: int
    by_rule: tuple[tuple[int, int, int], ...]
    unmapped: tuple[UnmappedLabel, ...]
    subjects_without_mezzanine: int
    absent_subtype_series: int
    absent_subtype_subjects: int


@dataclass(frozen=True)
class NewLabel:
    """Um rotulo normalizado coletado pela primeira vez depois da ultima revisao."""

    label_key: str
    series: int
    rule_id: int | None


@dataclass(frozen=True)
class ReviewReport:
    """O relatorio de revisao inteiro."""

    rules: tuple
    last_review: str | None
    competences: tuple[CompetenceReview, ...]
    label_keys_total: int
    new_labels: tuple[NewLabel, ...] | None
    fiagro_series: int


def fidc_competences(connection):
    """Competencias (em ordem) com alguma observacao tab_X_2 de fonte ativa."""

    return tuple(
        row[0]
        for row in connection.execute(
            "SELECT DISTINCT o.reference_date FROM observations o JOIN sources s ON s.id = o.source_id"
            " WHERE s.active = 1 AND o.quota_series_id IS NOT NULL"
            " AND o.field_name LIKE ? ESCAPE '\\' ORDER BY 1",
            (_TAB_X_2,),
        )
    )


def competence_series(connection, reference_date):
    """(id, rotulo normalizado, pai) das series com tab_X_2 na competencia (fonte ativa)."""

    rows = connection.execute(
        "SELECT q.id, q.series_label_key, q.fund_class_id, q.fund_id FROM quota_series q"
        " WHERE q.series_label_key IS NOT NULL AND EXISTS ("
        "  SELECT 1 FROM observations o JOIN sources s ON s.id = o.source_id"
        "  WHERE s.active = 1 AND o.quota_series_id = q.id AND o.reference_date = ?"
        "  AND o.field_name LIKE ? ESCAPE '\\')"
        " ORDER BY q.id",
        (reference_date, _TAB_X_2),
    ).fetchall()

    return tuple(
        (
            int(row[0]),
            str(row[1]),
            ("classe", int(row[2])) if row[2] is not None else ("fundo", int(row[3])),
        )
        for row in rows
    )


def _variants(connection, label_key):
    return connection.execute(
        "SELECT COUNT(DISTINCT o.value_text) FROM observations o"
        " JOIN quota_series q ON q.id = o.quota_series_id"
        " WHERE q.series_label_key = ? AND o.field_name LIKE ? ESCAPE '\\'",
        (label_key, _SERIES_LABEL_FIELDS),
    ).fetchone()[0]


def _competence_review(connection, reference_date):
    rules = load_rules(connection, reference_date)
    series = competence_series(connection, reference_date)
    by_rule = defaultdict(lambda: [0, set()])
    unmapped = defaultdict(lambda: [0, None])
    not_senior = Counter()
    mezzanine = Counter()
    absent = Counter()

    for _, key, parent in series:
        label = classify_label(key, rules)

        if not label.mapped:
            unmapped[key][0] += 1
            unmapped[key][1] = label.reason
            continue

        by_rule[label.rule.id][0] += 1
        by_rule[label.rule.id][1].add(key)

        if label.level == NOT_SENIOR:
            not_senior[parent] += 1

            if label.subtype == MEZZANINE:
                mezzanine[parent] += 1

            if label.subtype == ABSENT:
                absent[parent] += 1

    return CompetenceReview(
        reference_date=reference_date,
        series=len(series),
        label_keys=len({key for _, key, _ in series}),
        by_rule=tuple(
            (rule_id, count, len(keys)) for rule_id, (count, keys) in sorted(by_rule.items())
        ),
        unmapped=tuple(
            UnmappedLabel(key, count, _variants(connection, key), reason)
            for key, (count, reason) in sorted(unmapped.items())
        ),
        subjects_without_mezzanine=sum(
            1 for parent, count in not_senior.items() if count >= 2 and not mezzanine[parent]
        ),
        absent_subtype_series=sum(absent.values()),
        absent_subtype_subjects=len(absent),
    )


def _as_datetime(text):
    """Data e hora para comparar; sem fuso, vale como UTC (o banco grava em UTC)."""

    parsed = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _new_labels(connection, last_review, rules):
    """Rotulos de FIDC coletados pela primeira vez depois da ultima revisao."""

    first_seen = connection.execute(
        "SELECT q.series_label_key, MIN(o.collected_at), COUNT(DISTINCT q.id)"
        " FROM observations o JOIN quota_series q ON q.id = o.quota_series_id"
        " WHERE q.series_label_key IS NOT NULL AND o.field_name LIKE ? ESCAPE '\\'"
        " GROUP BY q.series_label_key ORDER BY q.series_label_key",
        (_SERIES_LABEL_FIELDS,),
    ).fetchall()

    if last_review is None:
        return len(first_seen), None

    limit = _as_datetime(last_review)
    found = []

    for key, first, series in first_seen:
        if _as_datetime(first) > limit:
            label = classify_label(key, rules)
            found.append(
                NewLabel(str(key), int(series), label.rule.id if label.mapped else None)
            )

    return len(first_seen), tuple(found)


def fiagro_series_without_map(connection):
    """Series de FIAGRO (subclasse), sem nenhum campo tab_X: o mapa nao as cobre."""

    return connection.execute(
        "SELECT COUNT(DISTINCT o.quota_series_id) FROM observations o"
        " WHERE o.quota_series_id IS NOT NULL AND o.field_name LIKE ? ESCAPE '\\'"
        " AND NOT EXISTS (SELECT 1 FROM observations x WHERE x.quota_series_id = o.quota_series_id"
        "  AND x.field_name LIKE ? ESCAPE '\\')",
        (_FIAGRO_SUBCLASS, _TAB_X),
    ).fetchone()[0]


def review_report(connection, reference_dates=None):
    """O relatorio de revisao (so le). Sem competencias: todas as com tab_X_2."""

    if reference_dates is None:
        references = fidc_competences(connection)
    else:
        references = tuple(normalize_iso_date(value, "Competencia") for value in reference_dates)

    rules = all_rules(connection)
    reviewed = [rule.reviewed_at for rule in rules if rule.reviewed_at is not None]
    last_review = max(reviewed, key=_as_datetime) if reviewed else None
    total, new_labels = _new_labels(connection, last_review, load_rules(connection))

    return ReviewReport(
        rules=rules,
        last_review=last_review,
        competences=tuple(_competence_review(connection, reference) for reference in references),
        label_keys_total=total,
        new_labels=new_labels,
        fiagro_series=fiagro_series_without_map(connection),
    )
