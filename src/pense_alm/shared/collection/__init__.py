"""Contratos compartilhados de coleta."""

from .enums import (
    CollectionRunStatus,
    CollectionSourceType,
    RawRecordStatus,
)
from .errors import CollectionError
from .raw_records import RawCollectionRecord
from .requests import CollectionRequest
from .responses import CollectedResponse
from .runs import CollectionRun
from .sources import CollectionSource

__all__ = [
    "CollectedResponse",
    "CollectionError",
    "CollectionRequest",
    "CollectionRun",
    "CollectionRunStatus",
    "CollectionSource",
    "CollectionSourceType",
    "RawCollectionRecord",
    "RawRecordStatus",
]
