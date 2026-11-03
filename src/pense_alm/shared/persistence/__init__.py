"""Persistencia compartilhada do PENSE-AL-M."""

from .backup import SQLiteBackup, create_sqlite_backup
from .connection import SQLiteConnectionManager
from .migration_runner import MigrationRunner
from .sqlite_entity_repository import (
    SQLiteEntityRepository,
)
from .sqlite_relationship_repository import (
    SQLiteRelationshipRepository,
)

__all__ = [
    "MigrationRunner",
    "SQLiteBackup",
    "SQLiteConnectionManager",
    "SQLiteEntityRepository",
    "SQLiteRelationshipRepository",
    "create_sqlite_backup",
]
