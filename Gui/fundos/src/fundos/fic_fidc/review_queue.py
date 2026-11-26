"""Fila de revisao manual de FIC-FIDC no audit_log (decisao 6 de Fundos).

Os assuntos em revisao manual (razao de 67% a menos de 95%) entram numa
fila no audit_log, uma linha por assunto, competencia e evidencia:
- actor: fundos.fic_fidc.v1 (o processo; nunca nome de pessoa);
- action: fic_fidc_revisao_manual_pendente;
- entity_type e entity_id: fund_classes ou funds, e o id do assunto;
- before_data: vazio;
- after_data: JSON canonico (chaves em ordem, separadores fixos, ASCII)
  com a competencia, a regra, a fonte que vai decidir (MANUAL) e, de cada
  campo, o nome e a observacao de origem. Nenhum valor, CNPJ nem nome: as
  observacoes sao imutaveis, e os ids bastam para reler os numeros;
- reason: a regra que mandou o assunto para a fila.

O audit_log nao tem coluna de fonte: a fonte MANUAL fica no after_data,
como a fonte da decisao. A decisao humana (a resolucao da fila) nao e
gravada aqui: a entrada MANUAL em observations so vem depois da migration
005 (ADR-010).

Sem duplicar: classificar e ler a fila nunca escrevem. enqueue so grava
dentro da transacao de quem chama e, antes de gravar, procura a mesma
linha (mesma action, actor, entity_type, entity_id e after_data
identico); se achar, conta como ja na fila. Valor reapresentado muda a
observacao de origem e gera linha nova; a antiga fica (este codigo so faz
INSERT no audit_log). queued mostra a mais recente por assunto, com a marca
classificacao_atual_diferente quando a faixa atual nao e mais a de revisao
ou a evidencia mudou.
"""

import json
import re
from collections import Counter
from dataclasses import dataclass

from fundos.fic_fidc.classification import DENOMINATOR
from fundos.fic_fidc.classification import MANUAL_REVIEW
from fundos.fic_fidc.classification import NUMERATOR
from fundos.fic_fidc.classification import RULE
from fundos.fic_fidc.classification import month_end
from fundos.indicators.values import CLASS_SUBJECT
from fundos.indicators.values import FUND_SUBJECT


ACTION = "fic_fidc_revisao_manual_pendente"
ACTOR = "fundos.fic_fidc.v1"
DECISION_SOURCE = "MANUAL"
REASON = "decisao 6 de Fundos: razao de 67% a menos de 95%"
ENTITY_TYPES = {CLASS_SUBJECT: "fund_classes", FUND_SUBJECT: "funds"}

STALE = "classificacao_atual_diferente"

# Varredura antes do COMMIT: o after_data gravado so tem ASCII imprimivel e
# nenhuma sequencia de 11 digitos ou mais (formato de CPF ou CNPJ).
_LONG_DIGITS = re.compile(r"[0-9]{11,}")
_PRINTABLE_ASCII = re.compile(r"[ -~]*")


def canonical_json(data):
    """JSON com as chaves em ordem, separadores fixos e so ASCII."""

    return json.dumps(data, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


@dataclass(frozen=True)
class QueueEntry:
    """Uma linha da fila, antes de gravar."""

    entity_type: str
    entity_id: int
    reference_date: str
    after_data: str


@dataclass(frozen=True)
class EnqueueResult:
    """O que enqueue gravou (ids no audit_log) e quantas ja estavam na fila."""

    created: tuple[int, ...]
    already: int


@dataclass(frozen=True)
class QueuedReview:
    """A entrada mais recente da fila de um assunto numa competencia."""

    entity_type: str
    entity_id: int
    reference_date: str
    audit_id: int
    occurred_at: str
    numerator_observation_id: int
    denominator_observation_id: int
    entries: int
    flags: tuple[str, ...] = ()


def _evidence(amount, field_name):
    (part,) = amount.parts

    if part.field_name != field_name or part.observation_id is None:
        raise ValueError("A evidencia da fila precisa da observacao de origem do campo.")

    return {"campo": field_name, "observation_id": int(part.observation_id)}


def queue_entry(classification):
    """A linha da fila de um assunto em revisao manual."""

    if classification.band != MANUAL_REVIEW:
        raise ValueError("So o assunto em revisao manual entra na fila.")

    data = {
        "competencia": classification.reference_date,
        "regra": classification.rule,
        "fonte_da_decisao": DECISION_SOURCE,
        "numerador": _evidence(classification.numerator, NUMERATOR),
        "denominador": _evidence(classification.denominator, DENOMINATOR),
    }

    return QueueEntry(
        entity_type=ENTITY_TYPES[classification.subject.kind],
        entity_id=int(classification.subject.id),
        reference_date=classification.reference_date,
        after_data=canonical_json(data),
    )


def _existing_id(connection, entry):
    row = connection.execute(
        "SELECT id FROM audit_log WHERE action = ? AND actor = ? AND entity_type = ?"
        " AND entity_id = ? AND after_data = ? ORDER BY id LIMIT 1",
        (ACTION, ACTOR, entry.entity_type, entry.entity_id, entry.after_data),
    ).fetchone()

    return None if row is None else int(row[0])


def to_enqueue(connection, classifications):
    """(novas, ja na fila): as entradas dos assuntos em revisao manual (so le)."""

    new = []
    already = []
    seen = set()

    for classification in classifications:
        if classification.band != MANUAL_REVIEW:
            continue

        entry = queue_entry(classification)

        if entry in seen:
            continue

        seen.add(entry)

        if _existing_id(connection, entry) is None:
            new.append(entry)
        else:
            already.append(entry)

    return tuple(new), tuple(already)


def enqueue(connection, classifications):
    """Grava as entradas novas da fila, dentro da transacao de quem chama.

    Nunca atualiza nem apaga: so INSERT. A entrada que ja esta na fila
    (mesmo after_data) e contada e nao e gravada de novo.
    """

    if not connection.in_transaction:
        raise ValueError("A fila so e gravada dentro de uma transacao de quem chama.")

    new, already = to_enqueue(connection, classifications)
    created = []

    for entry in new:
        created.append(
            connection.execute(
                "INSERT INTO audit_log"
                " (actor, action, entity_type, entity_id, before_data, after_data, reason)"
                " VALUES (?, ?, ?, ?, NULL, ?, ?)",
                (ACTOR, ACTION, entry.entity_type, entry.entity_id, entry.after_data, REASON),
            ).lastrowid
        )

    return EnqueueResult(tuple(int(i) for i in created), len(already))


def scan_created(connection, audit_ids):
    """Quantas linhas gravadas tem after_data fora do formato (deve dar 0)."""

    problems = 0

    for audit_id in audit_ids:
        row = connection.execute(
            "SELECT after_data, before_data FROM audit_log WHERE id = ?", (audit_id,)
        ).fetchone()

        if row is None or row[1] is not None:
            problems += 1
            continue

        text = str(row[0])

        if _PRINTABLE_ASCII.fullmatch(text) is None or _LONG_DIGITS.search(text):
            problems += 1

    return problems


def queued(connection, reference_date, classifications=None):
    """As entradas da fila na competencia, a mais recente por assunto (so le).

    Com classifications (as da mesma competencia), marca
    classificacao_atual_diferente quando o assunto nao esta mais em revisao
    manual ou a evidencia mudou.
    """

    reference = month_end(reference_date)
    rows = connection.execute(
        "SELECT id, entity_type, entity_id, after_data, occurred_at FROM audit_log"
        " WHERE action = ? AND actor = ? ORDER BY id",
        (ACTION, ACTOR),
    ).fetchall()
    latest = {}
    entries = Counter()

    for row in rows:
        try:
            data = json.loads(row[3])
            competence = data["competencia"]
            rule = data["regra"]
        except (TypeError, ValueError, KeyError):
            raise ValueError("Linha da fila fora do formato no audit_log.") from None

        if competence != reference or rule != RULE:
            continue

        key = (str(row[1]), int(row[2]))
        entries[key] += 1
        latest[key] = (row, data)

    current = None

    if classifications is not None:
        current = {
            (ENTITY_TYPES[c.subject.kind], int(c.subject.id)): c for c in classifications
        }

    results = []

    for key in sorted(latest):
        row, data = latest[key]
        flags = ()

        if current is not None:
            classification = current.get(key)

            if (
                classification is None
                or classification.band != MANUAL_REVIEW
                or queue_entry(classification).after_data != row[3]
            ):
                flags = (STALE,)

        results.append(
            QueuedReview(
                entity_type=key[0],
                entity_id=key[1],
                reference_date=reference,
                audit_id=int(row[0]),
                occurred_at=str(row[4]),
                numerator_observation_id=int(data["numerador"]["observation_id"]),
                denominator_observation_id=int(data["denominador"]["observation_id"]),
                entries=entries[key],
                flags=flags,
            )
        )

    return tuple(results)
