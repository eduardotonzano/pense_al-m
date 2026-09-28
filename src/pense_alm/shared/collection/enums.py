"""Enumeracoes da camada compartilhada de coleta."""

from enum import StrEnum


class CollectionSourceType(StrEnum):
    """Tipos de fonte suportados pelo catalogo."""

    SCRAPER = "scraper"
    API = "api"
    MANUAL = "manual"
    DOCUMENT = "document"
    INTERNAL = "internal"


class CollectionRunStatus(StrEnum):
    """Estados possiveis de uma execucao de coleta."""

    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RawRecordStatus(StrEnum):
    """Estados de processamento de um registro bruto."""

    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"
    IGNORED = "ignored"
