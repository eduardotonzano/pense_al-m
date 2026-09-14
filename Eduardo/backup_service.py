import hashlib
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from pathlib import Path

from debenture_search.database import database


@dataclass(frozen=True)
class BackupRecord:
    """Representa um backup valido do banco."""

    path: Path
    created_at: str
    size_bytes: int
    sha256: str


class BackupService:
    """Cria, valida, lista e restaura backups SQLite."""

    def __init__(self, db=database, backup_dir=None):
        self.db = db
        self.backup_dir = Path(
            backup_dir
            if backup_dir is not None
            else self.db.database_path.parent / "backups"
        )

    @staticmethod
    def utc_now():
        """Retorna o horario atual em UTC."""

        return datetime.now(timezone.utc)

    @staticmethod
    def sha256(path):
        """Calcula o SHA-256 de um arquivo."""

        digest = hashlib.sha256()

        with Path(path).open("rb") as file_handle:
            for block in iter(
                lambda: file_handle.read(1024 * 1024),
                b"",
            ):
                digest.update(block)

        return digest.hexdigest()

    @staticmethod
    def validate_sqlite(path):
        """Valida a integridade de um arquivo SQLite."""

        candidate = Path(path)

        if not candidate.exists():
            raise ValueError("Arquivo de banco nao encontrado.")

        if candidate.stat().st_size == 0:
            raise ValueError("O arquivo de banco esta vazio.")

        try:
            connection = sqlite3.connect(
                "file:" + candidate.as_posix() + "?mode=ro",
                uri=True,
            )

            try:
                result = connection.execute(
                    "PRAGMA integrity_check"
                ).fetchone()[0]
            finally:
                connection.close()
        except sqlite3.DatabaseError as error:
            raise ValueError(
                "O arquivo informado nao e um SQLite valido."
            ) from error

        if result != "ok":
            raise ValueError(
                "Falha na integridade do backup: " + str(result)
            )

        return True

    def build_backup_path(self):
        """Cria um nome unico para o backup."""

        timestamp = self.utc_now().strftime(
            "%Y%m%dT%H%M%S_%fZ"
        )
        return self.backup_dir / (
            "debenture_" + timestamp + ".sqlite3"
        )

    def create_backup(self):
        """Cria um backup consistente usando a API do SQLite."""

        if self.db.integrity_check() != "ok":
            raise RuntimeError(
                "O banco principal nao esta integro."
            )

        foreign_key_errors = self.db.foreign_key_check()

        if foreign_key_errors:
            raise RuntimeError(
                "O banco principal possui erros de chave estrangeira."
            )

        self.backup_dir.mkdir(parents=True, exist_ok=True)
        target = self.build_backup_path()

        source_connection = self.db.connect()
        target_connection = sqlite3.connect(target)

        try:
            source_connection.backup(target_connection)
            target_connection.commit()
        except Exception:
            target_connection.close()
            source_connection.close()
            target.unlink(missing_ok=True)
            raise
        else:
            target_connection.close()
            source_connection.close()

        self.validate_sqlite(target)

        return BackupRecord(
            path=target,
            created_at=self.utc_now().isoformat(),
            size_bytes=target.stat().st_size,
            sha256=self.sha256(target),
        )

    def get_record(self, path):
        """Valida um backup e retorna seus metadados."""

        candidate = Path(path)
        self.validate_sqlite(candidate)

        modified = datetime.fromtimestamp(
            candidate.stat().st_mtime,
            tz=timezone.utc,
        ).isoformat()

        return BackupRecord(
            path=candidate,
            created_at=modified,
            size_bytes=candidate.stat().st_size,
            sha256=self.sha256(candidate),
        )

    def list_backups(self):
        """Lista backups validos do mais recente ao mais antigo."""

        if not self.backup_dir.exists():
            return []

        records = []

        for path in self.backup_dir.glob(
            "debenture_*.sqlite3"
        ):
            try:
                records.append(self.get_record(path))
            except ValueError:
                continue

        records.sort(
            key=lambda item: item.path.stat().st_mtime,
            reverse=True,
        )
        return records

    def restore(self, backup_path):
        """Restaura um backup valido no banco principal."""

        backup = Path(backup_path)
        self.validate_sqlite(backup)

        safety_copy = None

        if self.db.database_path.exists():
            safety_copy = self.create_backup()

        self.db.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_path = self.db.database_path.with_suffix(
            ".restore.tmp"
        )
        temporary_path.unlink(missing_ok=True)

        try:
            shutil.copy2(backup, temporary_path)
            self.validate_sqlite(temporary_path)
            temporary_path.replace(self.db.database_path)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise

        restored_integrity = self.db.integrity_check()

        if restored_integrity != "ok":
            raise RuntimeError(
                "O banco restaurado nao esta integro."
            )

        return {
            "restored_from": backup,
            "safety_backup": (
                None if safety_copy is None else safety_copy.path
            ),
            "sha256": self.sha256(self.db.database_path),
        }

    def prune(self, keep=10):
        """Mantem somente a quantidade indicada de backups."""

        keep_count = int(keep)

        if keep_count < 1:
            raise ValueError(
                "A quantidade de backups deve ser maior que zero."
            )

        backups = self.list_backups()
        removed = []

        for record in backups[keep_count:]:
            record.path.unlink(missing_ok=True)
            removed.append(record.path)

        return removed


backup_service = BackupService()
