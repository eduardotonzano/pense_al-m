"""Backup do banco SQLite pela API de backup, com validacao."""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


class BackupError(Exception):
    """Nao foi possivel criar um backup valido."""


@dataclass(frozen=True)
class BackupResult:
    path: Path
    size_bytes: int
    sha256: str


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()

    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def _integrity(connection: sqlite3.Connection) -> str:
    return str(connection.execute("PRAGMA integrity_check").fetchone()[0])


def create_backup(
    database_path: str | Path,
    backup_dir: str | Path | None = None,
    prefix: str = "cri_cra",
) -> BackupResult:
    """Copia o banco para ``<pasta>/<prefixo>_<UTC>.sqlite3`` e valida a copia.

    Recusa banco inexistente, corrompido ou com erro de chave estrangeira.
    Sem ``backup_dir`` usa a pasta ``backups`` ao lado do banco.
    """

    source_path = Path(database_path)

    if not source_path.is_file():
        raise BackupError(f"Banco nao encontrado: {source_path}")

    folder = (
        Path(backup_dir)
        if backup_dir is not None
        else source_path.parent / "backups"
    )
    folder.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    target_path = folder / f"{prefix}_{stamp}.sqlite3"

    try:
        source = sqlite3.connect(source_path)
    except sqlite3.Error as error:
        raise BackupError(f"Nao foi possivel abrir o banco: {error}") from error

    try:
        try:
            integrity = _integrity(source)
            foreign_key_errors = source.execute(
                "PRAGMA foreign_key_check"
            ).fetchall()
        except sqlite3.Error as error:
            raise BackupError(f"O banco de origem nao e valido: {error}") from error

        if integrity != "ok":
            raise BackupError(f"O banco de origem nao esta integro: {integrity}")

        if foreign_key_errors:
            raise BackupError(
                "O banco de origem tem erros de chave estrangeira."
            )

        target = sqlite3.connect(target_path)

        try:
            source.backup(target)
        except BaseException:
            target.close()
            target_path.unlink(missing_ok=True)
            raise

        try:
            copy_integrity = _integrity(target)
        finally:
            target.close()
    finally:
        source.close()

    if copy_integrity != "ok":
        target_path.unlink(missing_ok=True)
        raise BackupError(f"A copia nao passou na integridade: {copy_integrity}")

    return BackupResult(
        path=target_path,
        size_bytes=target_path.stat().st_size,
        sha256=file_sha256(target_path),
    )
