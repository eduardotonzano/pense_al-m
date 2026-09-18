import pathlib

import pytest

from debenture_search.database import Database
from debenture_search.repositories.issuer_repository import (
    IssuerRecord,
    IssuerRepository,
)


PROJECT_DIR = pathlib.Path(__file__).resolve().parent.parent
MIGRATION_PATH = (
    PROJECT_DIR
    / "migrations"
    / "001_initial_schema.sql"
)


@pytest.fixture
def repository(tmp_path):
    database_path = tmp_path / "issuer_repository.db"
    test_database = Database(database_path)

    migration_sql = MIGRATION_PATH.read_text(
        encoding="utf-8"
    )

    with test_database.connection() as connection:
        connection.executescript(migration_sql)
        connection.commit()

    return IssuerRepository(test_database)


def test_create_issuer(repository):
    issuer = repository.create(
        legal_name="Empresa Brasileira de Teste S.A.",
        cnpj="12345678000199",
        trade_name="Empresa Teste",
    )

    assert isinstance(issuer, IssuerRecord)
    assert issuer.id > 0
    assert issuer.cnpj == "12345678000199"
    assert issuer.legal_name == (
        "Empresa Brasileira de Teste S.A."
    )
    assert issuer.trade_name == "Empresa Teste"


def test_create_normalizes_cnpj(repository):
    issuer = repository.create(
        legal_name="Empresa Normalizada S.A.",
        cnpj="12.345.678/0001-99",
    )

    assert issuer.cnpj == "12345678000199"


def test_create_normalizes_names(repository):
    issuer = repository.create(
        legal_name=(
            "  Empresa   com   Espacos   S.A.  "
        ),
        cnpj="22345678000198",
        trade_name="  Nome   Fantasia  ",
    )

    assert issuer.legal_name == (
        "Empresa com Espacos S.A."
    )
    assert issuer.trade_name == "Nome Fantasia"


def test_create_without_cnpj(repository):
    issuer = repository.create(
        legal_name="Emissor sem CNPJ",
    )

    assert issuer.id > 0
    assert issuer.cnpj is None
    assert issuer.legal_name == "Emissor sem CNPJ"


def test_rejects_invalid_cnpj(repository):
    with pytest.raises(
        ValueError,
        match="14 digitos",
    ):
        repository.create(
            legal_name="Empresa Invalida",
            cnpj="123",
        )


def test_rejects_empty_legal_name(repository):
    with pytest.raises(
        ValueError,
        match="nao pode ficar vazia",
    ):
        repository.create(
            legal_name="   ",
            cnpj="32345678000197",
        )


def test_rejects_duplicate_cnpj(repository):
    repository.create(
        legal_name="Empresa Original",
        cnpj="42345678000196",
    )

    with pytest.raises(
        ValueError,
        match="Ja existe um emissor",
    ):
        repository.create(
            legal_name="Empresa Duplicada",
            cnpj="42.345.678/0001-96",
        )

    assert repository.count() == 1


def test_get_by_id(repository):
    created = repository.create(
        legal_name="Empresa Localizada por ID",
        cnpj="52345678000195",
    )

    found = repository.get_by_id(created.id)

    assert found is not None
    assert found.id == created.id
    assert found.cnpj == "52345678000195"
    assert found.legal_name == (
        "Empresa Localizada por ID"
    )


def test_get_by_id_returns_none(repository):
    found = repository.get_by_id(999999)

    assert found is None


def test_get_by_cnpj(repository):
    created = repository.create(
        legal_name="Empresa Localizada por CNPJ",
        cnpj="62345678000194",
    )

    found = repository.get_by_cnpj(
        "62.345.678/0001-94"
    )

    assert found is not None
    assert found.id == created.id
    assert found.cnpj == "62345678000194"


def test_get_by_cnpj_returns_none(repository):
    found = repository.get_by_cnpj(
        "72345678000193"
    )

    assert found is None


def test_get_or_create_creates_new_issuer(repository):
    issuer, was_created = repository.get_or_create(
        legal_name="Empresa Nova",
        cnpj="82345678000192",
    )

    assert was_created is True
    assert issuer.cnpj == "82345678000192"
    assert repository.count() == 1


def test_get_or_create_returns_existing_issuer(
    repository,
):
    original = repository.create(
        legal_name="Empresa Existente",
        cnpj="92345678000191",
    )

    found, was_created = repository.get_or_create(
        legal_name="Nome que nao deve substituir",
        cnpj="92.345.678/0001-91",
    )

    assert was_created is False
    assert found.id == original.id
    assert found.legal_name == "Empresa Existente"
    assert repository.count() == 1


def test_search_by_legal_name(repository):
    repository.create(
        legal_name="Companhia Alfa de Energia",
        cnpj="10345678000190",
    )

    repository.create(
        legal_name="Companhia Beta de Logistica",
        cnpj="11345678000189",
    )

    results = repository.search_by_name("Alfa")

    assert len(results) == 1
    assert results[0].legal_name == (
        "Companhia Alfa de Energia"
    )


def test_search_by_trade_name(repository):
    repository.create(
        legal_name="Companhia Brasileira de Academias",
        cnpj="12345678000188",
        trade_name="Academia Teste",
    )

    results = repository.search_by_name(
        "Academia"
    )

    assert len(results) == 1
    assert results[0].trade_name == (
        "Academia Teste"
    )


def test_search_is_case_insensitive(repository):
    repository.create(
        legal_name="Companhia Gama S.A.",
        cnpj="13345678000187",
    )

    results = repository.search_by_name(
        "companhia gama"
    )

    assert len(results) == 1
    assert results[0].legal_name == (
        "Companhia Gama S.A."
    )


def test_search_empty_query_returns_empty_list(
    repository,
):
    assert repository.search_by_name("") == []
    assert repository.search_by_name("   ") == []
    assert repository.search_by_name(None) == []


def test_list_all_orders_by_legal_name(repository):
    repository.create(
        legal_name="Empresa Zeta",
        cnpj="14345678000186",
    )

    repository.create(
        legal_name="Empresa Alfa",
        cnpj="15345678000185",
    )

    repository.create(
        legal_name="Empresa Delta",
        cnpj="16345678000184",
    )

    results = repository.list_all()

    names = [
        issuer.legal_name
        for issuer in results
    ]

    assert names == [
        "Empresa Alfa",
        "Empresa Delta",
        "Empresa Zeta",
    ]


def test_list_all_supports_pagination(repository):
    repository.create(
        legal_name="Empresa A",
        cnpj="17345678000183",
    )

    repository.create(
        legal_name="Empresa B",
        cnpj="18345678000182",
    )

    repository.create(
        legal_name="Empresa C",
        cnpj="19345678000181",
    )

    first_page = repository.list_all(
        limit=2,
        offset=0,
    )

    second_page = repository.list_all(
        limit=2,
        offset=2,
    )

    assert len(first_page) == 2
    assert len(second_page) == 1

    assert first_page[0].legal_name == "Empresa A"
    assert first_page[1].legal_name == "Empresa B"
    assert second_page[0].legal_name == "Empresa C"


def test_count_returns_total(repository):
    assert repository.count() == 0

    repository.create(
        legal_name="Empresa Um",
        cnpj="20345678000180",
    )

    repository.create(
        legal_name="Empresa Dois",
        cnpj="21345678000179",
    )

    assert repository.count() == 2


def test_update_issuer(repository):
    created = repository.create(
        legal_name="Nome Antigo",
        cnpj="22345678000178",
        trade_name="Marca Antiga",
    )

    updated = repository.update(
        issuer_id=created.id,
        legal_name="Nome Atualizado",
        trade_name="Marca Atualizada",
    )

    assert updated.id == created.id
    assert updated.cnpj == created.cnpj
    assert updated.legal_name == "Nome Atualizado"
    assert updated.trade_name == "Marca Atualizada"

    persisted = repository.get_by_id(created.id)

    assert persisted is not None
    assert persisted.legal_name == "Nome Atualizado"
    assert persisted.trade_name == "Marca Atualizada"


def test_update_rejects_unknown_issuer(repository):
    with pytest.raises(
        ValueError,
        match="Emissor nao encontrado",
    ):
        repository.update(
            issuer_id=999999,
            legal_name="Empresa Inexistente",
        )


def test_update_rejects_empty_name(repository):
    created = repository.create(
        legal_name="Empresa Valida",
        cnpj="23345678000177",
    )

    with pytest.raises(
        ValueError,
        match="nao pode ficar vazia",
    ):
        repository.update(
            issuer_id=created.id,
            legal_name="   ",
        )

    persisted = repository.get_by_id(created.id)

    assert persisted is not None
    assert persisted.legal_name == "Empresa Valida"


def test_repository_keeps_database_integrity(
    repository,
):
    repository.create(
        legal_name="Empresa de Integridade",
        cnpj="24345678000176",
    )

    assert repository.db.integrity_check() == "ok"
    assert repository.db.foreign_key_check() == []