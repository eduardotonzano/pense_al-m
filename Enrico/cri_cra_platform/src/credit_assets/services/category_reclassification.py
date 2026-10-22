"""Previa e gravacao da reclassificacao de documentos hoje em "Outro".

A previa so le o banco. A gravacao so troca linhas que estao em "Outro", com
backup antes, uma transacao, uma linha de auditoria por troca e verificacao
antes do COMMIT. Categoria ja especifica nunca e alterada: se a regra nova
discorda dela, o documento aparece na lista de desacordos e nada e gravado.
"""

from __future__ import annotations

import sqlite3
import time
import uuid
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from credit_assets.database.backup import create_backup
from credit_assets.database.connection import connect
from credit_assets.utils.document_category_rules import (
    CLASSIFIER_VERSION,
    OTHER,
    classify_strict,
)

GRID_COLUMNS = ("source_category", "source_type", "source_species")


class ReclassificationError(Exception):
    """Nao foi possivel gerar a previa ou gravar a reclassificacao."""


def open_read_only(database_path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def table_exists(connection: sqlite3.Connection, name: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (name,),
    ).fetchone() is not None


def load_documents(connection: sqlite3.Connection):
    """Linhas de documents e se as colunas da grade (migration 001) existem."""

    if not table_exists(connection, "documents"):
        raise ReclassificationError("Tabela documents nao encontrada no banco.")

    columns = {row[1] for row in connection.execute("PRAGMA table_info(documents)")}
    grid_available = all(column in columns for column in GRID_COLUMNS)
    selected = ["document_pk", "category", "document_name"]

    if grid_available:
        selected += list(GRID_COLUMNS)

    rows = connection.execute(
        f"SELECT {', '.join(selected)} FROM documents ORDER BY document_pk"
    ).fetchall()

    return rows, grid_available


def _change(row, classification) -> dict:
    return {
        "document_pk": int(row["document_pk"]),
        "name": row["document_name"],
        "from": row["category"],
        "to": classification.category,
        "rule_id": classification.rule_id,
        "group": classification.group,
        "matched_field": classification.matched_field,
        "matched_value": classification.matched_value,
    }


def _section(changes, extra=None) -> dict:
    section = {
        "changes": changes,
        "by_transition": dict(
            Counter(f"{item['from']} -> {item['to']}" for item in changes)
        ),
        "by_rule": dict(Counter(item["rule_id"] for item in changes)),
    }
    section.update(extra or {})
    return section


def build_preview(rows, grid_available: bool, database: str = "") -> dict:
    """Quantos documentos mudariam, separando o grupo verificado do nao verificado."""

    verified_changes = []
    verified_ambiguous = []
    verified_disagreements = []
    vetoed = unmatched = 0
    unverified_added = []
    unverified_lost = []
    unverified_ambiguous = []
    unverified_disagreements = []
    other_total = 0

    for row in rows:
        fields = {key: row[key] for key in row.keys()}
        default = classify_strict(fields, include_unverified=False)
        enabled = classify_strict(fields, include_unverified=True)
        current = row["category"]

        if current == OTHER:
            other_total += 1

            if default.category != OTHER:
                verified_changes.append(_change(row, default))

                if enabled.category != default.category:
                    unverified_lost.append({
                        **_change(row, default),
                        "candidates": list(enabled.candidates),
                    })
            elif default.vetoed:
                vetoed += 1
            elif default.ambiguous:
                verified_ambiguous.append({
                    "document_pk": int(row["document_pk"]),
                    "name": row["document_name"],
                    "candidates": list(default.candidates),
                })
            else:
                unmatched += 1

                if enabled.category != OTHER:
                    unverified_added.append(_change(row, enabled))
                elif enabled.ambiguous:
                    unverified_ambiguous.append({
                        "document_pk": int(row["document_pk"]),
                        "name": row["document_name"],
                        "candidates": list(enabled.candidates),
                    })

            continue

        # Categoria ja especifica: nunca e gravada; so acusa desacordo.
        default_disagrees = default.vetoed or default.category not in (OTHER, current)
        enabled_disagrees = enabled.vetoed or enabled.category not in (OTHER, current)
        entry = {
            "document_pk": int(row["document_pk"]),
            "name": row["document_name"],
            "current": current,
            "strict": enabled.category,
            "rule_id": enabled.rule_id,
            "vetoed": enabled.vetoed,
        }

        if default_disagrees:
            verified_disagreements.append({
                **entry,
                "strict": default.category,
                "rule_id": default.rule_id,
                "vetoed": default.vetoed,
            })
        elif enabled_disagrees:
            unverified_disagreements.append(entry)

    return {
        "database": database,
        "classifier_version": CLASSIFIER_VERSION,
        "documents": len(rows),
        "currently_other": other_total,
        "grid_fields_available": grid_available,
        "documents_with_grid_fields": sum(
            1 for row in rows
            if grid_available and any(row[column] for column in GRID_COLUMNS)
        ),
        "verified": _section(
            verified_changes,
            {
                "ambiguous": verified_ambiguous,
                "vetoed": vetoed,
                "unmatched": unmatched,
                "disagreements": verified_disagreements,
            },
        ),
        "unverified": _section(
            unverified_added,
            {
                "lost_to_ambiguity": unverified_lost,
                "ambiguous": unverified_ambiguous,
                "disagreements": unverified_disagreements,
            },
        ),
    }


def select_changes(preview: dict, include_unverified: bool = False) -> list[dict]:
    """O que o --commit grava: so o grupo verificado, ou os dois com a opcao."""

    changes = list(preview["verified"]["changes"])

    if include_unverified:
        lost = {item["document_pk"] for item in preview["unverified"]["lost_to_ambiguity"]}
        changes = [item for item in changes if item["document_pk"] not in lost]
        changes += preview["unverified"]["changes"]

    return sorted(changes, key=lambda item: item["document_pk"])


def _example_line(item: dict) -> str:
    where = f" em {item['matched_field']}" if item.get("matched_field") else ""
    return (
        f"  doc {item['document_pk']} \"{item['name']}\": "
        f"{item['from']} -> {item['to']} ({item['rule_id']}{where})"
    )


def _counts(counts: dict) -> str:
    return ", ".join(f"{key}: {total}" for key, total in sorted(counts.items())) or "nenhuma"


def _transitions(section: dict) -> list[str]:
    return [
        f"  {transition}: {total}"
        for transition, total in sorted(section["by_transition"].items())
    ] or ["  nenhuma"]


def _disagreement_lines(items: list[dict]) -> list[str]:
    lines = []

    for item in items:
        reason = "veto" if item["vetoed"] else f"regra indica {item['strict']}"
        lines.append(
            f"  doc {item['document_pk']} \"{item['name']}\": atual "
            f"{item['current']}, {item['rule_id']} ({reason})"
        )

    return lines


def format_preview(preview: dict, examples: int = 3) -> str:
    verified = preview["verified"]
    unverified = preview["unverified"]
    default_total = len(select_changes(preview, False))
    enabled_total = len(select_changes(preview, True))
    grid_note = (
        "migration 001 aplicada"
        if preview["grid_fields_available"]
        else "migration 001 pendente: so o nome do documento e usado"
    )
    lines = [
        f"Banco: {preview['database']} (aberto somente para leitura)",
        f"Classificador estrito {preview['classifier_version']}",
        f"Documentos: {preview['documents']} | em \"Outro\": "
        f"{preview['currently_other']} | com campos da grade: "
        f"{preview['documents_with_grid_fields']} ({grid_note})",
        "",
        "== Regras verificadas (valem por padrao) ==",
        f"Mudariam de categoria: {len(verified['changes'])}",
        *_transitions(verified),
        f"Por regra: {_counts(verified['by_rule'])}",
        f"Ambiguos (ficam em Outro): {len(verified['ambiguous'])}",
        f"Vetados (ficam em Outro): {verified['vetoed']}",
        f"Sem regra (ficam em Outro): {verified['unmatched']}",
        f"Desacordos com a categoria atual (nunca gravados): "
        f"{len(verified['disagreements'])}",
        *_disagreement_lines(verified["disagreements"]),
    ]

    if verified["changes"]:
        lines.append("Exemplos:")
        lines += [_example_line(item) for item in verified["changes"][:examples]]

    lines += [
        "",
        "== Regras nao verificadas (so valem com --enable-unverified-rules) ==",
        "(previa apenas: nada disto e gravado sem a opcao)",
        f"Mudariam alem das verificadas: {len(unverified['changes'])}",
        *_transitions(unverified),
        f"Por regra: {_counts(unverified['by_rule'])}",
        f"Cancelariam mudancas verificadas por ambiguidade: "
        f"{len(unverified['lost_to_ambiguity'])}",
        f"Novos ambiguos: {len(unverified['ambiguous'])}",
        f"Desacordos adicionais (nunca gravados): {len(unverified['disagreements'])}",
        *_disagreement_lines(unverified["disagreements"]),
    ]

    if unverified["changes"]:
        lines.append("Exemplos:")
        lines += [_example_line(item) for item in unverified["changes"][:examples]]

    lines += [
        "",
        "== O que o --commit gravaria ==",
        f"Sem --enable-unverified-rules: {default_total} documento(s) (grupo verificado).",
        f"Com --enable-unverified-rules: {enabled_total} documento(s).",
    ]

    return "\n".join(lines)


def apply_changes(
    connection: sqlite3.Connection,
    changes: list[dict],
    run_id: str,
) -> None:
    """Grava as trocas numa transacao e so confirma se a verificacao passar."""

    started = time.perf_counter()
    total_before = connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    other_before = connection.execute(
        "SELECT COUNT(*) FROM documents WHERE category = ?", (OTHER,)
    ).fetchone()[0]
    now = datetime.now(timezone.utc).isoformat()
    connection.commit()
    connection.execute("BEGIN IMMEDIATE")

    try:
        connection.execute(
            "INSERT INTO executions (run_id, started_at, status) VALUES (?, ?, 'running')",
            (run_id, now),
        )

        for item in changes:
            updated = connection.execute(
                "UPDATE documents SET category = ? "
                "WHERE document_pk = ? AND category = ?",
                (item["to"], item["document_pk"], OTHER),
            ).rowcount

            if updated != 1:
                raise ReclassificationError(
                    f"O documento {item['document_pk']} mudou durante a "
                    "regravacao; nada foi gravado."
                )

            connection.execute(
                """INSERT INTO document_category_changes (
                    document_id, old_category, new_category, rule_id, rule_group,
                    matched_field, matched_value, classifier_version, run_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    item["document_pk"], item["from"], item["to"], item["rule_id"],
                    item["group"], item["matched_field"], item["matched_value"],
                    CLASSIFIER_VERSION, run_id,
                ),
            )

        problems = []
        total_after = connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        other_after = connection.execute(
            "SELECT COUNT(*) FROM documents WHERE category = ?", (OTHER,)
        ).fetchone()[0]
        audited = connection.execute(
            "SELECT COUNT(*) FROM document_category_changes WHERE run_id = ?",
            (run_id,),
        ).fetchone()[0]

        if total_after != total_before:
            problems.append("a contagem de documentos mudou")

        if other_before - other_after != len(changes):
            problems.append("o numero de documentos em Outro nao caiu como previsto")

        if audited != len(changes):
            problems.append("a auditoria nao tem uma linha por troca")

        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            problems.append("integrity_check falhou")

        if connection.execute("PRAGMA foreign_key_check").fetchall():
            problems.append("foreign_key_check encontrou problemas")

        if problems:
            raise ReclassificationError(
                "Verificacao antes do COMMIT falhou: " + "; ".join(problems) + "."
            )

        connection.execute(
            """UPDATE executions SET finished_at = ?, status = 'success',
               duration_seconds = ?, documents_found = ? WHERE run_id = ?""",
            (
                datetime.now(timezone.utc).isoformat(),
                round(time.perf_counter() - started, 4),
                len(changes),
                run_id,
            ),
        )
        connection.execute("COMMIT")
    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK")

        raise


def commit_reclassification(
    database_path: str | Path,
    include_unverified: bool = False,
    backup_dir: str | Path | None = None,
) -> dict:
    """Backup, trocas e verificacao. Sem nada a trocar, nao faz backup."""

    path = Path(database_path)

    with closing(open_read_only(path)) as reader:
        rows, grid_available = load_documents(reader)
        has_audit = table_exists(reader, "document_category_changes")

    if not has_audit:
        raise ReclassificationError(
            "A tabela document_category_changes nao existe: aplique a "
            "migration 001 com scripts/apply_migration.py antes de gravar."
        )

    preview = build_preview(rows, grid_available, str(path))
    changes = select_changes(preview, include_unverified)

    if not changes:
        return {"changes": 0, "backup": None, "run_id": None}

    try:
        backup = create_backup(path, backup_dir)
    except Exception as error:
        raise ReclassificationError(
            f"Nao foi possivel criar o backup; o banco nao foi alterado: {error}"
        ) from error

    run_id = uuid.uuid4().hex
    connection = connect(path)

    try:
        apply_changes(connection, changes, run_id)
    finally:
        connection.close()

    return {
        "changes": len(changes),
        "backup": backup,
        "run_id": run_id,
        "by_transition": dict(
            Counter(f"{item['from']} -> {item['to']}" for item in changes)
        ),
    }
