from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CAFE_CANONICAL_CETIP = "CRA022009VM"
CAFE_ISIN = "BRECOACRABX0"


class AssetMigrationConflict(RuntimeError):
    """Raised when duplicate-asset relationships cannot be merged without loss."""


def migrate_cafe_brasil_duplicate_asset(
    connection: sqlite3.Connection,
) -> dict[str, Any]:
    if connection.in_transaction:
        raise RuntimeError("A migração exige uma conexão sem transação ativa")

    connection.execute("BEGIN IMMEDIATE")
    try:
        canonical = connection.execute(
            """SELECT * FROM assets
               WHERE UPPER(REPLACE(TRIM(codigo_cetip), ' ', '')) = ?""",
            (CAFE_CANONICAL_CETIP,),
        ).fetchall()
        if len(canonical) != 1:
            raise AssetMigrationConflict(
                f"Esperado um único ativo com CETIP {CAFE_CANONICAL_CETIP}; "
                f"encontrados {len(canonical)}"
            )
        canonical_row = canonical[0]
        canonical_id = int(canonical_row["asset_id"])
        if str(canonical_row["isin"] or "").strip().upper() != CAFE_ISIN:
            raise AssetMigrationConflict(
                f"asset_id={canonical_id} não possui ISIN canônico {CAFE_ISIN}"
            )

        isin_matches = connection.execute(
            """SELECT * FROM assets
               WHERE UPPER(REPLACE(TRIM(isin), ' ', '')) = ?""",
            (CAFE_ISIN,),
        ).fetchall()
        sources = [row for row in isin_matches if int(row["asset_id"]) != canonical_id]
        if not sources:
            connection.commit()
            return {
                "canonical_asset_id": canonical_id,
                "merged_asset_ids": [],
                "already_migrated": True,
                "documents_migrated": 0,
                "document_versions_preserved": 0,
                "collection_attempts_migrated": 0,
                "alerts_migrated": 0,
                "other_references_migrated": {},
                "duplicate_asset_removed": False,
            }
        if (
            len(sources) != 1
            or str(sources[0]["codigo_cetip"] or "").strip().upper()
            != CAFE_ISIN
        ):
            raise AssetMigrationConflict(
                "Encontrados registros duplicados fora do par de ativos aprovado: "
                + ", ".join(str(row["asset_id"]) for row in sources)
            )

        duplicate = sources[0]
        duplicate_id = int(duplicate["asset_id"])
        _validate_compatible_assets(canonical_row, duplicate)
        duplicate_documents = connection.execute(
            "SELECT * FROM documents WHERE asset_id = ? ORDER BY document_pk",
            (duplicate_id,),
        ).fetchall()
        canonical_documents = connection.execute(
            "SELECT * FROM documents WHERE asset_id = ? ORDER BY document_pk",
            (canonical_id,),
        ).fetchall()
        merge_pairs = _find_equivalent_documents(
            canonical_documents, duplicate_documents
        )
        _validate_document_hashes(canonical_documents, duplicate_documents, merge_pairs)
        version_count = int(
            connection.execute(
                """SELECT COUNT(*) FROM document_versions v
                   JOIN documents d ON d.document_pk = v.document_id
                   WHERE d.asset_id = ?""",
                (duplicate_id,),
            ).fetchone()[0]
        )
        _validate_physical_versions(connection, duplicate_id)

        source_ids_to_merge = {source_id for _, source_id in merge_pairs}
        preserved_source_document_ids = {
            int(row["document_pk"])
            for row in duplicate_documents
            if int(row["document_pk"]) not in source_ids_to_merge
        }

        connection.execute(
            """UPDATE assets SET
                codigo_cetip = ?, isin = ?, emissao = ?, serie = '1',
                tipo_ativo = ?, securitizadora = ?, cnpj_securitizadora = ?,
                devedor = ?, cnpj_devedor = ?, updated_at = ?
               WHERE asset_id = ?""",
            (
                CAFE_CANONICAL_CETIP,
                CAFE_ISIN,
                "190",
                canonical_row["tipo_ativo"],
                canonical_row["securitizadora"] or duplicate["securitizadora"],
                canonical_row["cnpj_securitizadora"]
                or duplicate["cnpj_securitizadora"],
                canonical_row["devedor"] or duplicate["devedor"],
                canonical_row["cnpj_devedor"] or duplicate["cnpj_devedor"],
                datetime.now(timezone.utc).isoformat(),
                canonical_id,
            ),
        )

        migrated_counts: dict[str, int] = {}
        foreign_key_tables = _asset_foreign_key_columns(connection)
        for table, columns in foreign_key_tables.items():
            moved = 0
            for column in columns:
                cursor = connection.execute(
                    f'UPDATE "{table}" SET "{column}" = ? WHERE "{column}" = ?',
                    (canonical_id, duplicate_id),
                )
                moved += cursor.rowcount
            migrated_counts[table] = moved

        for canonical_document_id, duplicate_document_id in merge_pairs:
            _merge_equivalent_document(
                connection, canonical_document_id, duplicate_document_id
            )

        remaining = _asset_references(connection, duplicate_id)
        if remaining:
            connection.execute(
                "UPDATE assets SET active = 0 WHERE asset_id = ?", (duplicate_id,)
            )
            duplicate_removed = False
        else:
            connection.execute("DELETE FROM assets WHERE asset_id = ?", (duplicate_id,))
            duplicate_removed = True

        if connection.execute(
            "SELECT 1 FROM assets WHERE asset_id = ?", (duplicate_id,)
        ).fetchone() is None:
            remaining = {}
        if duplicate_removed and remaining:
            raise AssetMigrationConflict(
                f"Referências ainda apontam para asset_id={duplicate_id}: {remaining}"
            )

        connection.commit()
        return {
            "canonical_asset_id": canonical_id,
            "merged_asset_ids": [duplicate_id],
            "already_migrated": False,
            "documents_migrated": len(preserved_source_document_ids),
            "equivalent_documents_merged": len(merge_pairs),
            "document_versions_preserved": version_count,
            "collection_attempts_migrated": migrated_counts.get(
                "collection_attempts", 0
            ),
            "alerts_migrated": migrated_counts.get("alerts", 0),
            "other_references_migrated": {
                table: count
                for table, count in migrated_counts.items()
                if table not in {"assets", "documents", "collection_attempts", "alerts"}
                and count
            },
            "duplicate_asset_removed": duplicate_removed,
            "duplicate_asset_deactivated": not duplicate_removed,
            "remaining_references": remaining,
        }
    except Exception:
        connection.rollback()
        raise


def _validate_compatible_assets(canonical: sqlite3.Row, duplicate: sqlite3.Row) -> None:
    for field in (
        "tipo_ativo",
        "securitizadora",
        "cnpj_securitizadora",
        "emissao",
        "devedor",
        "cnpj_devedor",
    ):
        canonical_value = (canonical[field] or "").strip()
        duplicate_value = (duplicate[field] or "").strip()
        if canonical_value and duplicate_value and canonical_value != duplicate_value:
            raise AssetMigrationConflict(
                f"Conflito no campo {field}: asset_id={canonical['asset_id']} "
                f"tem {canonical_value!r}, asset_id={duplicate['asset_id']} "
                f"tem {duplicate_value!r}"
            )
    if str(duplicate["serie"] or "").strip().casefold() not in {
        "1",
        "unica",
        "única",
    }:
        raise AssetMigrationConflict(
            f"Série inesperada no ativo duplicado: {duplicate['serie']!r}"
        )


def _find_equivalent_documents(
    canonical_documents: list[sqlite3.Row],
    duplicate_documents: list[sqlite3.Row],
) -> list[tuple[int, int]]:
    pairs: list[tuple[int, int]] = []
    canonical_by_key = {
        (row["source_document_id"], row["source"]): row
        for row in canonical_documents
    }
    canonical_by_url = {row["source_url"]: row for row in canonical_documents}
    for duplicate in duplicate_documents:
        key = (duplicate["source_document_id"], duplicate["source"])
        candidates = {
            int(candidate["document_pk"]): candidate
            for candidate in (
                canonical_by_key.get(key),
                canonical_by_url.get(duplicate["source_url"]),
            )
            if candidate is not None
        }
        if not candidates:
            continue
        if len(candidates) != 1:
            raise AssetMigrationConflict(
                f"Documento {duplicate['document_pk']} colide com múltiplos "
                "documentos canônicos"
            )
        canonical = next(iter(candidates.values()))
        for field in ("source", "category", "reference_date"):
            left = canonical[field] or ""
            right = duplicate[field] or ""
            if left and right and left != right:
                raise AssetMigrationConflict(
                    f"Documentos {canonical['document_pk']} e "
                    f"{duplicate['document_pk']} divergem em {field}"
                )
        same_key = (
            canonical["source_document_id"],
            canonical["source"],
        ) == key
        same_url = canonical["source_url"] == duplicate["source_url"]
        if not (same_key or same_url):
            raise AssetMigrationConflict(
                f"Documentos {canonical['document_pk']} e "
                f"{duplicate['document_pk']} não são equivalentes"
            )
        if canonical["publication_date"] and duplicate["publication_date"]:
            if canonical["publication_date"] != duplicate["publication_date"]:
                raise AssetMigrationConflict(
                    f"Documentos {canonical['document_pk']} e "
                    f"{duplicate['document_pk']} divergem em publication_date"
                )
        pairs.append(
            (int(canonical["document_pk"]), int(duplicate["document_pk"]))
        )
    return pairs


def _validate_document_hashes(
    canonical_documents: list[sqlite3.Row],
    duplicate_documents: list[sqlite3.Row],
    merge_pairs: list[tuple[int, int]],
) -> None:
    canonical_by_hash: dict[str, list[sqlite3.Row]] = {}
    for document in canonical_documents:
        file_hash = document["file_hash"]
        if file_hash:
            canonical_by_hash.setdefault(file_hash, []).append(document)
    merge_by_duplicate = {duplicate_id: canonical_id for canonical_id, duplicate_id in merge_pairs}
    for duplicate in duplicate_documents:
        file_hash = duplicate["file_hash"]
        if not file_hash or file_hash not in canonical_by_hash:
            continue
        related = [
            row
            for row in canonical_by_hash[file_hash]
            if int(row["document_pk"]) == merge_by_duplicate.get(
                int(duplicate["document_pk"])
            )
        ]
        if not related:
            raise AssetMigrationConflict(
                f"file_hash compartilhado por documentos não equivalentes: {file_hash}"
            )


def _validate_physical_versions(
    connection: sqlite3.Connection, asset_id: int
) -> None:
    versions = connection.execute(
        """SELECT v.version_id, v.local_file_path, v.file_hash, v.file_size_bytes
           FROM document_versions v
           JOIN documents d ON d.document_pk = v.document_id
           WHERE d.asset_id = ?""",
        (asset_id,),
    ).fetchall()
    for version in versions:
        if not version["local_file_path"]:
            raise AssetMigrationConflict(
                f"Versão {version['version_id']} não possui caminho físico"
            )
        path = Path(version["local_file_path"])
        if not path.is_absolute():
            path = Path.cwd() / path
        if not path.is_file():
            raise AssetMigrationConflict(
                f"Arquivo da versão {version['version_id']} não encontrado: {path}"
            )
        if version["file_size_bytes"] and path.stat().st_size != version["file_size_bytes"]:
            raise AssetMigrationConflict(
                f"Tamanho físico divergente na versão {version['version_id']}"
            )
        if version["file_hash"]:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != version["file_hash"]:
                raise AssetMigrationConflict(
                    f"SHA-256 divergente na versão {version['version_id']}"
                )


def _merge_equivalent_document(
    connection: sqlite3.Connection,
    canonical_document_id: int,
    duplicate_document_id: int,
) -> None:
    canonical = connection.execute(
        "SELECT * FROM documents WHERE document_pk = ?", (canonical_document_id,)
    ).fetchone()
    duplicate = connection.execute(
        "SELECT * FROM documents WHERE document_pk = ?", (duplicate_document_id,)
    ).fetchone()
    if not canonical or not duplicate:
        raise AssetMigrationConflict("Documento desapareceu durante a mesclagem")
    if (
        canonical["run_id"]
        and duplicate["run_id"]
        and canonical["run_id"] != duplicate["run_id"]
    ):
        raise AssetMigrationConflict(
            "Documentos equivalentes têm run_id distintos, sem campo para "
            "preservar ambos no registro documental"
        )

    duplicate_versions = connection.execute(
        "SELECT * FROM document_versions WHERE document_id = ?",
        (duplicate_document_id,),
    ).fetchall()
    canonical_versions = connection.execute(
        "SELECT * FROM document_versions WHERE document_id = ?",
        (canonical_document_id,),
    ).fetchall()
    canonical_hashes = {
        row["file_hash"] for row in canonical_versions if row["file_hash"]
    }
    for version in duplicate_versions:
        if version["file_hash"] and version["file_hash"] in canonical_hashes:
            raise AssetMigrationConflict(
                "Documentos equivalentes contêm versões com o mesmo hash; "
                "mesclagem exige reconciliação explícita das versões"
            )

    latest_current = [
        row for row in canonical_versions + duplicate_versions if row["is_current"]
    ]
    current_winner = None
    if latest_current:
        current_winner = max(
            latest_current,
            key=lambda row: (
                row["downloaded_at"] or "",
                row["created_at"] or "",
                int(row["version_id"]),
            ),
        )
    connection.execute(
        "UPDATE document_versions SET document_id = ?, is_current = 0 WHERE document_id = ?",
        (canonical_document_id, duplicate_document_id),
    )
    if current_winner:
        connection.execute(
            "UPDATE document_versions SET is_current = 1 WHERE version_id = ?",
            (current_winner["version_id"],),
        )
    connection.execute(
        "UPDATE collection_attempts SET document_id = ? WHERE document_id = ?",
        (canonical_document_id, duplicate_document_id),
    )
    chosen_hash = (
        current_winner["file_hash"]
        if current_winner
        else canonical["file_hash"] or duplicate["file_hash"]
    )
    connection.execute(
        """UPDATE documents SET
             document_name = COALESCE(NULLIF(document_name, ''), ?),
             reference_date = COALESCE(reference_date, ?),
             publication_date = COALESCE(publication_date, ?),
             file_hash = COALESCE(?, file_hash),
             collected_at = CASE
               WHEN collected_at <= ? THEN collected_at ELSE ? END,
             run_id = COALESCE(run_id, ?)
           WHERE document_pk = ?""",
        (
            duplicate["document_name"],
            duplicate["reference_date"],
            duplicate["publication_date"],
            chosen_hash,
            duplicate["collected_at"],
            duplicate["collected_at"],
            duplicate["run_id"],
            canonical_document_id,
        ),
    )
    connection.execute(
        "DELETE FROM documents WHERE document_pk = ?", (duplicate_document_id,)
    )


def _asset_foreign_key_columns(
    connection: sqlite3.Connection,
) -> dict[str, list[str]]:
    tables = [
        row["name"]
        for row in connection.execute(
            """SELECT name FROM sqlite_master
               WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"""
        )
    ]
    references: dict[str, list[str]] = {}
    for table in tables:
        columns = [
            row["from"]
            for row in connection.execute(f'PRAGMA foreign_key_list("{table}")')
            if row["table"] == "assets" and row["to"] == "asset_id"
        ]
        if columns:
            references[table] = columns
    return references


def _asset_references(connection: sqlite3.Connection, asset_id: int) -> dict[str, int]:
    references: dict[str, int] = {}
    for table, columns in _asset_foreign_key_columns(connection).items():
        count = sum(
            int(
                connection.execute(
                    f'SELECT COUNT(*) FROM "{table}" WHERE "{column}" = ?',
                    (asset_id,),
                ).fetchone()[0]
            )
            for column in columns
        )
        if count:
            references[table] = count
    return references
