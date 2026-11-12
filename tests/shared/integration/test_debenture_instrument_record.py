"""Testes do registro intermediario de debentures."""

import pytest

from pense_alm.shared.integration import (
    DebentureInstrumentRecord,
)

from ..cnpj_amostras import cnpj_ficticio, com_mascara


ALFA_CNPJ = cnpj_ficticio(1)
ALFA_CNPJ_MASCARA = com_mascara(ALFA_CNPJ)
ALFA_CNPJ_ALFANUMERICO = cnpj_ficticio(1, alfanumerico=True)


def with_wrong_last_digit(cnpj):
    return cnpj[:-1] + str((int(cnpj[-1]) + 1) % 10)


def create_record(**overrides):
    values = {
        "legacy_id": 7,
        "asset_code": "ALFA11",
        "isin": "BRALFADBS001",
        "status": "active",
        "issuer_legacy_id": 1,
        "issuer_cnpj": ALFA_CNPJ_MASCARA,
        "created_at": "2026-09-20 10:00:00",
        "updated_at": "2026-09-21 12:00:00",
    }
    values.update(overrides)
    return DebentureInstrumentRecord(**values)


def test_record_normalizes_identifiers_status_and_cnpj():
    record = create_record(
        asset_code=" alfa11 ",
        isin="bralfadbs001",
        status=" ACTIVE ",
    )

    assert record.asset_code == "ALFA11"
    assert record.isin == "BRALFADBS001"
    assert record.status == "active"
    assert record.issuer_cnpj == ALFA_CNPJ


def test_record_accepts_only_asset_code():
    record = create_record(isin=None)

    assert record.asset_code == "ALFA11"
    assert record.isin is None


def test_record_accepts_only_isin():
    record = create_record(asset_code=None)

    assert record.asset_code is None
    assert record.isin == "BRALFADBS001"


def test_record_accepts_missing_issuer():
    record = create_record(
        issuer_legacy_id=None,
        issuer_cnpj=None,
    )

    assert record.issuer_legacy_id is None
    assert record.issuer_cnpj is None


def test_record_accepts_issuer_without_cnpj():
    record = create_record(issuer_cnpj=None)

    assert record.issuer_legacy_id == 1
    assert record.issuer_cnpj is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"asset_code": None, "isin": None},
        {"asset_code": "   ", "isin": "  "},
    ],
)
def test_record_requires_asset_code_or_isin(overrides):
    with pytest.raises(ValueError):
        create_record(**overrides)


@pytest.mark.parametrize(
    "isin",
    ["BRALFADBS00", "BRALFADBS0011", "BR-ALFA-0001"],
)
def test_record_rejects_malformed_isin(isin):
    with pytest.raises(ValueError):
        create_record(isin=isin)


def test_record_rejects_asset_code_with_spaces():
    with pytest.raises(ValueError):
        create_record(asset_code="ALFA 11")


def test_record_rejects_unknown_status():
    with pytest.raises(ValueError):
        create_record(status="vencida")


@pytest.mark.parametrize("legacy_id", [0, -1])
def test_record_rejects_non_positive_legacy_id(legacy_id):
    with pytest.raises(ValueError):
        create_record(legacy_id=legacy_id)


def test_record_rejects_non_integer_legacy_id():
    with pytest.raises(TypeError):
        create_record(legacy_id="7")


def test_record_rejects_cnpj_without_issuer_id():
    with pytest.raises(ValueError):
        create_record(issuer_legacy_id=None)


def test_record_rejects_invalid_issuer_cnpj():
    with pytest.raises(ValueError):
        create_record(issuer_cnpj="123")


@pytest.mark.parametrize(
    "issuer_cnpj",
    [
        ALFA_CNPJ_ALFANUMERICO,
        com_mascara(ALFA_CNPJ_ALFANUMERICO),
        ALFA_CNPJ_ALFANUMERICO.lower(),
        com_mascara(ALFA_CNPJ_ALFANUMERICO).lower(),
    ],
    ids=["puro", "mascara", "minusculas", "mascara-minusculas"],
)
def test_record_accepts_alphanumeric_issuer_cnpj(issuer_cnpj):
    record = create_record(issuer_cnpj=issuer_cnpj)

    assert record.issuer_cnpj == ALFA_CNPJ_ALFANUMERICO


@pytest.mark.parametrize(
    ("issuer_cnpj", "message"),
    [
        (
            with_wrong_last_digit(ALFA_CNPJ_ALFANUMERICO),
            "digito verificador",
        ),
        # 14 digitos com DV invalido: antes passava no registro.
        (with_wrong_last_digit(ALFA_CNPJ), "digito verificador"),
        # Digitos fora do ASCII: isdigit os aceitava.
        (
            "".join(chr(0xFF10 + int(digit)) for digit in ALFA_CNPJ),
            "14 caracteres",
        ),
    ],
    ids=["alfanumerico-dv-errado", "numerico-dv-errado", "digitos-largura-total"],
)
def test_record_rejects_issuer_cnpj_outside_the_shared_rule(
    issuer_cnpj,
    message,
):
    with pytest.raises(ValueError, match=message):
        create_record(issuer_cnpj=issuer_cnpj)


@pytest.mark.parametrize(
    "field_name",
    ["created_at", "updated_at"],
)
def test_record_rejects_empty_timestamps(field_name):
    with pytest.raises(ValueError):
        create_record(**{field_name: "  "})


def test_record_is_immutable():
    record = create_record()

    with pytest.raises(AttributeError):
        record.isin = "BRBETADBS002"
