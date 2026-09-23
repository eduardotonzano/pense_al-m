"""Testes do relatorio agregado de importacao."""

import pytest

from pense_alm.shared.integration import (
    BatchImportError,
    BatchImportReport,
)


def test_empty_report_is_valid():
    report = BatchImportReport()

    assert report.total_read == 0
    assert report.successful == 0
    assert report.pending == 0
    assert report.failed == 0
    assert report.dry_run is False


def test_report_calculates_aggregates():
    report = BatchImportReport(
        total_read=10,
        created=3,
        matched=2,
        review=2,
        blocked=1,
        errors=2,
        error_details=(
            BatchImportError(
                legacy_id=9,
                error_type="ValueError",
                message="Primeiro erro.",
            ),
            BatchImportError(
                legacy_id=10,
                error_type="TypeError",
                message="Segundo erro.",
            ),
        ),
    )

    assert report.successful == 5
    assert report.pending == 2
    assert report.failed == 3


def test_report_supports_dry_run():
    report = BatchImportReport(
        total_read=1,
        created=1,
        dry_run=True,
    )

    assert report.dry_run is True


def test_report_rejects_inconsistent_total():
    with pytest.raises(
        ValueError,
        match="soma dos resultados",
    ):
        BatchImportReport(
            total_read=2,
            created=1,
        )


def test_report_rejects_negative_counter():
    with pytest.raises(
        ValueError,
        match="nao podem ser negativos",
    ):
        BatchImportReport(
            total_read=0,
            errors=-1,
        )


def test_report_rejects_non_integer_counter():
    with pytest.raises(
        TypeError,
        match="devem ser inteiros",
    ):
        BatchImportReport(
            total_read=1,
            created=1.0,
        )


def test_report_rejects_invalid_dry_run():
    with pytest.raises(
        TypeError,
        match="dry_run deve ser booleano",
    ):
        BatchImportReport(
            dry_run="sim",
        )
