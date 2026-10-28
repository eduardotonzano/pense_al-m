"""Backup do banco de Fundos pela API de backup do SQLite, com validacao.

O nome do backup e curto (fundos_<UTC>.sqlite3) e o caminho final e
conferido contra o limite de 260 caracteres do Windows antes de qualquer
escrita: no compartilhamento de rede, um caminho longo faz o SQLite falhar
com "unable to open database file".
"""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from pathlib import Path


MAX_PATH = 260
JOURNAL_SUFFIX = "-journal"


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


BACKUP_DIR_HINT = (
    "use --backup-dir com uma pasta curta, por exemplo C:\\bk\\fundos."
)


def check_path_length(path: str | Path, hint: str = BACKUP_DIR_HINT) -> None:
    """Recusa caminho que, com o sufixo -journal, chega a 260 caracteres."""

    total = len(str(path)) + len(JOURNAL_SUFFIX)

    if total >= MAX_PATH:
        raise BackupError(
            "caminho longo ("
            + str(total)
            + " caracteres contando o -journal; o limite do Windows e "
            + str(MAX_PATH - 1)
            + "): "
            + hint
        )


def backup_path(
    database_path: str | Path,
    backup_dir: str | Path | None = None,
    prefix: str = "fundos",
) -> Path:
    """Caminho do proximo backup: <pasta>/<prefixo>_<UTC>.sqlite3."""

    folder = (
        Path(backup_dir)
        if backup_dir is not None
        else Path(database_path).parent / "backups"
    )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")

    return folder / (prefix + "_" + stamp + ".sqlite3")


def _integrity(connection: sqlite3.Connection) -> str:
    return str(connection.execute("PRAGMA integrity_check").fetchone()[0])


def create_backup(
    database_path: str | Path,
    backup_dir: str | Path | None = None,
    prefix: str = "fundos",
) -> BackupResult:
    """Copia o banco e valida a copia.

    Recusa banco inexistente, corrompido ou com erro de chave estrangeira, e
    caminho de backup longo demais. Sem backup_dir usa a pasta backups ao
    lado do banco.
    """

    source_path = Path(database_path)

    if not source_path.is_file():
        raise BackupError("Banco nao encontrado: " + str(source_path))

    target_path = backup_path(source_path, backup_dir, prefix)
    check_path_length(target_path)

    try:
        source = sqlite3.connect(source_path)
    except sqlite3.Error as error:
        raise BackupError("Nao foi possivel abrir o banco: " + str(error)) from error

    try:
        try:
            integrity = _integrity(source)
            foreign_key_errors = source.execute(
                "PRAGMA foreign_key_check"
            ).fetchall()
        except sqlite3.Error as error:
            raise BackupError(
                "O banco de origem nao e valido: " + str(error)
            ) from error

        if integrity != "ok":
            raise BackupError("O banco de origem nao esta integro: " + integrity)

        if foreign_key_errors:
            raise BackupError(
                "O banco de origem tem erros de chave estrangeira."
            )

        target_path.parent.mkdir(parents=True, exist_ok=True)
        target = sqlite3.connect(target_path)

        try:
            source.backup(target)
            copy_integrity = _integrity(target)
        except BaseException:
            target.close()
            target_path.unlink(missing_ok=True)
            raise

        target.close()
    finally:
        source.close()

    if copy_integrity != "ok":
        target_path.unlink(missing_ok=True)
        raise BackupError("A copia nao passou na integridade: " + copy_integrity)

    return BackupResult(
        path=target_path,
        size_bytes=target_path.stat().st_size,
        sha256=file_sha256(target_path),
    )
