"""Testes dos detalhes de erro da importacao."""

import pytest

from pense_alm.shared.integration import (
    BatchImportError,
    BatchImportReport,
)


def test_error_normalizes_message():
    error = BatchImportError(
        legacy_id=15,
        error_type="ValueError",
        message="  Registro   invalido.  ",
    )

    assert error.legacy_id == 15
    assert error.error_type == "ValueError"
    assert error.message == "Registro invalido."


def test_error_accepts_missing_legacy_id():
    error = BatchImportError(
        legacy_id=None,
        error_type="RuntimeError",
        message="Falha sem identificador.",
    )

    assert error.legacy_id is None


def test_error_rejects_invalid_legacy_id():
    with pytest.raises(
        ValueError,
        match="maior que zero",
    ):
        BatchImportError(
            legacy_id=0,
            error_type="ValueError",
            message="Registro invalido.",
        )


def test_report_exposes_error_details():
    detail = BatchImportError(
        legacy_id=7,
        error_type="ValueError",
        message="Registro invalido.",
    )

    report = BatchImportReport(
        total_read=1,
        errors=1,
        error_details=(detail,),
    )

    assert report.errors == 1
    assert report.error_details == (detail,)
    assert report.failed == 1


def test_report_rejects_missing_error_detail():
    with pytest.raises(
        ValueError,
        match="quantidade de detalhes",
    ):
        BatchImportReport(
            total_read=1,
            errors=1,
        )


def test_report_rejects_extra_error_detail():
    detail = BatchImportError(
        legacy_id=8,
        error_type="TypeError",
        message="Tipo invalido.",
    )

    with pytest.raises(
        ValueError,
        match="quantidade de detalhes",
    ):
        BatchImportReport(
            total_read=0,
            error_details=(detail,),
        )
