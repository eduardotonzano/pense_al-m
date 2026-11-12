"""Backup consistente de bancos SQLite da camada compartilhada."""

import hashlib
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SQLiteBackup:
    """Backup validado de um banco SQLite."""

    path: Path
    size_bytes: int
    sha256: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file_handle:
        for block in iter(
            lambda: file_handle.read(1024 * 1024),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def create_sqlite_backup(
    database_path: str | Path,
    backup_dir: str | Path,
) -> SQLiteBackup:
    """Copia o banco com a API de backup do SQLite e valida a copia.

    A origem e aberta com PRAGMA query_only. Se a copia falhar ou nao
    passar no integrity_check, o arquivo parcial e removido.
    """

    source = Path(database_path)

    if not source.is_file():
        raise FileNotFoundError(
            f"Banco nao encontrado: {source}"
        )

    directory = Path(backup_dir)
    directory.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime(
        "%Y%m%dT%H%M%S_%fZ"
    )
    target = directory / f"{source.stem}_{timestamp}.sqlite3"

    if target.exists():
        raise FileExistsError(
            f"O backup ja existe: {target}"
        )

    try:
        with closing(
            sqlite3.connect(str(source), timeout=30)
        ) as origin, closing(
            sqlite3.connect(str(target))
        ) as copy:
            origin.execute("PRAGMA query_only = ON")
            origin.backup(copy)
            check = copy.execute(
                "PRAGMA integrity_check"
            ).fetchone()
    except BaseException:
        target.unlink(missing_ok=True)
        raise

    if check is None or check[0] != "ok":
        target.unlink(missing_ok=True)

        raise RuntimeError(
            "O backup nao passou na verificacao de integridade."
        )

    return SQLiteBackup(
        path=target,
        size_bytes=target.stat().st_size,
        sha256=_sha256(target),
    )
