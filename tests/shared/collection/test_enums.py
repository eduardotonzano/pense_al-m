"""Testes das enumeracoes compartilhadas de coleta."""

from pense_alm.shared.collection.enums import (
    CollectionRunStatus,
    CollectionSourceType,
    RawRecordStatus,
)


def test_collection_source_types():
    assert {
        item.value
        for item in CollectionSourceType
    } == {
        "scraper",
        "api",
        "manual",
        "document",
        "internal",
    }


def test_collection_run_statuses():
    assert {
        item.value
        for item in CollectionRunStatus
    } == {
        "running",
        "success",
        "partial",
        "failed",
        "cancelled",
    }


def test_raw_record_statuses():
    assert {
        item.value
        for item in RawRecordStatus
    } == {
        "pending",
        "processed",
        "failed",
        "ignored",
    }


def test_enums_are_string_compatible():
    assert CollectionSourceType.API == "api"
    assert CollectionRunStatus.SUCCESS == "success"
    assert RawRecordStatus.PENDING == "pending"
