"""AssetRepository: o CNPJ da securitizadora é comparado inteiro, com letras (IN RFB 2.229/2024).

Bancos só em tmp_path. CNPJs fictícios de tests/cnpj_amostras.py, com DV calculado lá.
"""
from __future__ import annotations

import pytest

from credit_assets.database.connection import connect, initialize_database
from credit_assets.models.asset import Asset
from credit_assets.repositories.asset_repository import AssetRepository
from tests.cnpj_amostras import com_mascara, dv_errado, montar_cnpj

# Z vale ord("Z") - 48 = 42 e O vale 31: a diferença é 11, então trocar Z por O não muda nenhum dígito verificador.
# As duas securitizadoras têm os mesmos dígitos e só diferem numa letra.
SECURITIZADORA_A = montar_cnpj("ZZZZZZZ1ZZZZ")
SECURITIZADORA_B = montar_cnpj("ZZZZZZZ1ZZZO")


def _asset(cnpj_securitizadora: str) -> Asset:
    return Asset("CRAFICT0001", "CRA", "Securitizadora Fictícia", cnpj_securitizadora, "190", "1",
                 "Devedor Fictício", "", "BRFICTCRA001")


def _repository(tmp_path):
    connection = connect(tmp_path / "assets.db")
    initialize_database(connection)
    return connection, AssetRepository(connection)


def _count(connection) -> int:
    return connection.execute("SELECT COUNT(*) FROM assets").fetchone()[0]


def test_alphanumeric_issuers_with_same_digits_are_different(tmp_path):
    a, b = SECURITIZADORA_A, SECURITIZADORA_B
    assert a != b and [c for c in a if c.isdigit()] == [c for c in b if c.isdigit()]
    connection, repository = _repository(tmp_path)
    asset_id = repository.upsert(_asset(a))

    with pytest.raises(ValueError, match="outra securitizadora"):
        repository.upsert(_asset(b))

    row = connection.execute("SELECT cnpj_securitizadora FROM assets WHERE asset_id = ?", (asset_id,)).fetchone()
    assert row[0] == a and _count(connection) == 1


@pytest.mark.parametrize("variant", [
    com_mascara(SECURITIZADORA_A),
    SECURITIZADORA_A.lower(),
    com_mascara(SECURITIZADORA_A).lower(),
    "  " + SECURITIZADORA_A + " ",
], ids=["mascara", "minuscula", "mascara-minuscula", "espacos"])
def test_mask_and_case_variants_of_same_cnpj_do_not_conflict(tmp_path, variant):
    connection, repository = _repository(tmp_path)
    asset_id = repository.upsert(_asset(SECURITIZADORA_A))

    assert repository.upsert(_asset(variant)) == asset_id
    assert _count(connection) == 1


def test_invalid_check_digit_alone_never_refuses(tmp_path):
    # O repositório não valida CNPJ: DV errado não é motivo de recusa.
    wrong = dv_errado(SECURITIZADORA_A)
    connection, repository = _repository(tmp_path)
    asset_id = repository.upsert(_asset(wrong))

    for variant in (wrong, com_mascara(wrong), com_mascara(wrong).lower()):
        assert repository.upsert(_asset(variant)) == asset_id
    assert _count(connection) == 1


def _with_inner_space(cnpj: str) -> str:
    return cnpj[:8] + " " + cnpj[8:]


@pytest.mark.parametrize("stored, incoming, conflict", [
    ("10 753 164 0001 43", "10.753.164/0001-43", False),  # numérico fora do formato: só os dígitos, como hoje
    ("N/A", "10.753.164/0001-43", False),  # sem dígito: não compara, como hoje
    (_with_inner_space(SECURITIZADORA_A), com_mascara(SECURITIZADORA_A), False),
    (com_mascara(SECURITIZADORA_A), _with_inner_space(SECURITIZADORA_B), True),  # letra nunca é descartada
], ids=["numerico-espacos", "sem-digito", "alfanumerico-espaco-interno", "alfanumerico-fora-do-formato-outra-letra"])
def test_out_of_format_values(tmp_path, stored, incoming, conflict):
    connection, repository = _repository(tmp_path)
    asset_id = repository.upsert(_asset(stored))

    if conflict:
        with pytest.raises(ValueError, match="outra securitizadora"):
            repository.upsert(_asset(incoming))
    else:
        assert repository.upsert(_asset(incoming)) == asset_id
    assert _count(connection) == 1


def test_label_before_numeric_cnpj_does_not_conflict(tmp_path):
    connection, repository = _repository(tmp_path)
    asset_id = repository.upsert(_asset("CNPJ 10.753.164/0001-43"))

    assert repository.upsert(_asset("10.753.164/0001-43")) == asset_id
    assert _count(connection) == 1
