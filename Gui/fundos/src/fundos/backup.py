"""Backup do banco de Fundos pela API de backup do SQLite, com validacao.

O nome do backup e curto (fundos_<UTC>.sqlite3) e o caminho final e
conferido contra o limite de 260 caracteres do Windows antes de qualquer
escrita: no compartilhamento de rede, um caminho longo faz o SQLite falhar
com "unable to open database file".

O banco e o backup ficam em disco local (decisao 9 de Fundos): SQLite em
compartilhamento de rede tem trava nao confiavel e deixa o journal na rede.
check_local_paths recusa o banco e o destino do backup em caminho de rede
(UNC, relativo dentro de pasta de rede ou unidade remota) e em caminho
longo, antes de qualquer leitura.
"""

from __future__ import annotations

import hashlib
import ntpath
import os
import sqlite3
import sys
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


# GetDriveTypeW: DRIVE_REMOTE (unidade mapeada de rede).
REMOTE_DRIVE = 4
UNC = "UNC"
REMOTE = "unidade remota"
NETWORK_HINT = "o banco de Fundos e o backup ficam em disco local, numa pasta curta."
DATABASE_HINT = "use um banco numa pasta de caminho curto, em disco local."


def _on_windows() -> bool:
    return sys.platform == "win32"


def _drive_type(drive: str) -> int | None:
    """GetDriveTypeW da unidade (por exemplo C:), so no Windows; None se nao der para saber."""

    if not _on_windows():
        return None

    try:
        import ctypes

        return int(ctypes.windll.kernel32.GetDriveTypeW(drive + "\\"))
    except Exception:
        return None


def _absolute(text: str) -> str:
    """O caminho completado com a pasta atual, sem resolver link nem tocar o disco."""

    return str(Path(text).absolute())


def network_reason(path: str | Path) -> str | None:
    """UNC, unidade remota ou None.

    So olha o texto do caminho (completado com a pasta atual quando e
    relativo) e, no Windows, o tipo da unidade. Nunca chama resolve, exists
    nem is_file: o caminho de rede e recusado antes de ser tocado. O prefixo
    de caminho estendido do Windows (duas barras invertidas e interrogacao)
    conta como UNC, um falso positivo seguro. E a regra de
    fundos_cli._is_network_path, copiada porque o modulo de Fundos nao
    importa a camada compartilhada.
    """

    text = os.fspath(path)

    if text.startswith(("\\\\", "//")):
        return UNC

    absolute = _absolute(text)

    if absolute.startswith(("\\\\", "//")):
        return UNC

    drive = ntpath.splitdrive(text)[0] or ntpath.splitdrive(absolute)[0]

    if len(drive) == 2 and drive[1] == ":" and _drive_type(drive) == REMOTE_DRIVE:
        return REMOTE

    return None


def check_local_path(path: str | Path, label: str) -> None:
    """Recusa o caminho de rede; a mensagem traz so o rotulo e o motivo, nunca o caminho."""

    reason = network_reason(path)

    if reason is not None:
        raise BackupError(label + " em caminho de rede (" + reason + "): " + NETWORK_HINT)


def check_local_paths(database: str | Path, backup_dir: str | Path | None = None) -> Path:
    """Confere o banco e o destino do backup; devolve o banco resolvido.

    Ordem: o texto do banco, o banco resolvido (link ou juncao para a rede),
    o comprimento do banco com o -journal, o destino do backup (o texto e,
    com backup_dir, a pasta resolvida) e o comprimento dele. O resolve so
    roda depois que o texto passou, entao um caminho de rede nunca e tocado.
    Levanta BackupError; nenhuma mensagem traz o caminho.
    """

    check_local_path(database, "--database")
    database_path = Path(database).resolve()
    check_local_path(database_path, "--database")

    try:
        check_path_length(database_path, hint=DATABASE_HINT)
    except BackupError as error:
        raise BackupError("Banco com " + str(error)) from error

    target = backup_path(database_path, backup_dir)
    check_local_path(target, "--backup-dir")

    if backup_dir is not None:
        check_local_path(Path(backup_dir).resolve(), "--backup-dir")

    check_path_length(target)
    return database_path


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
