from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from pathlib import Path

from debenture_search.database import database


REQUIRED_TABLES = {
    "schema_migrations",
    "issuers",
    "debentures",
    "sources",
    "collection_runs",
    "raw_records",
    "observations",
    "data_conflicts",
    "audit_log",
}

REQUIRED_VIEWS = {
    "current_observations",
}

REQUIRED_SOURCES = {
    "SND",
    "CVM",
    "ANBIMA_API",
    "MANUAL",
}


@dataclass(frozen=True)
class DatabaseHealthReport:
    """Representa o diagnostico de saude do banco."""

    status: str
    checked_at: str
    integrity: str
    foreign_key_errors: tuple
    migration_version: int | None
    missing_tables: tuple
    missing_views: tuple
    missing_sources: tuple
    stuck_collection_runs: int
    pending_raw_records: int
    failed_raw_records: int
    open_conflicts: int
    database_size_bytes: int
    backup_count: int
    latest_backup: str | None
    issues: tuple

    @property
    def healthy(self):
        """Informa se o banco esta saudavel."""

        return self.status == "healthy"


class DatabaseHealthService:
    """Executa verificacoes operacionais e estruturais."""

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

        return datetime.now(timezone.utc).isoformat()

    def list_objects(self, object_type):
        """Lista tabelas ou views registradas no SQLite."""

        rows = self.db.fetch_all(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = ?
            ORDER BY name
            """,
            (object_type,),
        )

        return {str(row["name"]) for row in rows}

    def migration_version(self):
        """Retorna a migration mais recente."""

        if not self.db.table_exists("schema_migrations"):
            return None

        row = self.db.fetch_one(
            "SELECT MAX(version) AS version FROM schema_migrations"
        )

        if row is None or row["version"] is None:
            return None

        return int(row["version"])

    def source_codes(self):
        """Retorna os codigos das fontes existentes."""

        if not self.db.table_exists("sources"):
            return set()

        rows = self.db.fetch_all(
            "SELECT code FROM sources"
        )
        return {str(row["code"]) for row in rows}

    def count_if_table_exists(self, table_name, where_clause=None):
        """Conta registros apenas quando a tabela existe."""

        if not self.db.table_exists(table_name):
            return 0

        sql = "SELECT COUNT(*) AS total FROM " + table_name

        if where_clause:
            sql += " WHERE " + where_clause

        row = self.db.fetch_one(sql)
        return 0 if row is None else int(row["total"])

    def backup_information(self):
        """Retorna quantidade e backup mais recente."""

        if not self.backup_dir.exists():
            return 0, None

        backups = sorted(
            self.backup_dir.glob("debenture_*.sqlite3"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )

        if not backups:
            return 0, None

        latest = datetime.fromtimestamp(
            backups[0].stat().st_mtime,
            tz=timezone.utc,
        ).isoformat()

        return len(backups), latest

    def check(self):
        """Executa o diagnostico completo do banco."""

        issues = []

        integrity = self.db.integrity_check()
        foreign_key_errors = tuple(
            tuple(row) for row in self.db.foreign_key_check()
        )

        tables = self.list_objects("table")
        views = self.list_objects("view")
        sources = self.source_codes()

        missing_tables = tuple(
            sorted(REQUIRED_TABLES.difference(tables))
        )
        missing_views = tuple(
            sorted(REQUIRED_VIEWS.difference(views))
        )
        missing_sources = tuple(
            sorted(REQUIRED_SOURCES.difference(sources))
        )

        version = self.migration_version()
        stuck_runs = self.count_if_table_exists(
            "collection_runs",
            "status = 'running'",
        )
        pending_raw = self.count_if_table_exists(
            "raw_records",
            "processing_status = 'pending'",
        )
        failed_raw = self.count_if_table_exists(
            "raw_records",
            "processing_status = 'failed'",
        )
        open_conflicts = self.count_if_table_exists(
            "data_conflicts",
            "status = 'open'",
        )

        database_size = (
            self.db.database_path.stat().st_size
            if self.db.database_path.exists()
            else 0
        )
        backup_count, latest_backup = self.backup_information()

        if integrity != "ok":
            issues.append("Falha na integridade SQLite.")

        if foreign_key_errors:
            issues.append("Existem violacoes de chaves estrangeiras.")

        if version is None:
            issues.append("Nenhuma migration foi registrada.")

        if missing_tables:
            issues.append("Existem tabelas obrigatorias ausentes.")

        if missing_views:
            issues.append("Existem views obrigatorias ausentes.")

        if missing_sources:
            issues.append("Existem fontes obrigatorias ausentes.")

        if stuck_runs > 0:
            issues.append("Existem coletas presas em running.")

        if failed_raw > 0:
            issues.append("Existem registros brutos com falha.")

        if open_conflicts > 0:
            issues.append("Existem conflitos de dados abertos.")

        status = "healthy" if not issues else "attention"

        return DatabaseHealthReport(
            status=status,
            checked_at=self.utc_now(),
            integrity=integrity,
            foreign_key_errors=foreign_key_errors,
            migration_version=version,
            missing_tables=missing_tables,
            missing_views=missing_views,
            missing_sources=missing_sources,
            stuck_collection_runs=stuck_runs,
            pending_raw_records=pending_raw,
            failed_raw_records=failed_raw,
            open_conflicts=open_conflicts,
            database_size_bytes=database_size,
            backup_count=backup_count,
            latest_backup=latest_backup,
            issues=tuple(issues),
        )


health_service = DatabaseHealthService()
