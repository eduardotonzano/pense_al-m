import pathlib

import pytest

from debenture_search.database import Database
from debenture_search.repositories.debenture_repository import (
    DebentureRecord,
    DebentureRepository,
)
from debenture_search.repositories.issuer_repository import (
    IssuerRepository,
)


PROJECT_DIR = pathlib.Path(__file__).resolve().parent.parent

MIGRATION_PATH = (
    PROJECT_DIR
    / "migrations"
    / "001_initial_schema.sql"
)


@pytest.fixture
def repositories(tmp_path):
    database_path = tmp_path / "debenture_repository.db"
    test_database = Database(database_path)

    migration_sql = MIGRATION_PATH.read_text(
        encoding="utf-8"
    )

    with test_database.connection() as connection:
        connection.executescript(migration_sql)
        connection.commit()

    issuer_repository = IssuerRepository(
        test_database
    )

    debenture_repository = DebentureRepository(
        test_database
    )

    return issuer_repository, debenture_repository


def create_issuer(issuer_repository):
    return issuer_repository.create(
        legal_name="Companhia Teste S.A.",
        cnpj="12345678000199",
        trade_name="Companhia Teste",
    )


def test_create_with_asset_code(repositories):
    issuer_repository, repository = repositories
    issuer = create_issuer(issuer_repository)

    debenture = repository.create(
        asset_code="TEST12",
        issuer_id=issuer.id,
        status="active",
    )

    assert isinstance(debenture, DebentureRecord)
    assert debenture.id > 0
    assert debenture.asset_code == "TEST12"
    assert debenture.issuer_id == issuer.id
    assert debenture.status == "active"


def test_create_with_isin(repositories):
    issuer_repository, repository = repositories
    issuer = create_issuer(issuer_repository)

    debenture = repository.create(
        isin="BRTESTDBS001",
        issuer_id=issuer.id,
        status="active",
    )

    assert debenture.isin == "BRTESTDBS001"
    assert debenture.asset_code is None
    assert debenture.issuer_id == issuer.id


def test_create_with_code_and_isin(repositories):
    issuer_repository, repository = repositories
    issuer = create_issuer(issuer_repository)

    debenture = repository.create(
        asset_code="TEST13",
        isin="BRTESTDBS002",
        issuer_id=issuer.id,
        issue_number="1",
        series="2",
        status="active",
    )

    assert debenture.asset_code == "TEST13"
    assert debenture.isin == "BRTESTDBS002"
    assert debenture.issue_number == "1"
    assert debenture.series == "2"


def test_identifiers_are_normalized(repositories):
    _, repository = repositories

    debenture = repository.create(
        asset_code="  test14  ",
        isin="  brtestdbs003  ",
    )

    assert debenture.asset_code == "TEST14"
    assert debenture.isin == "BRTESTDBS003"


def test_rejects_invalid_isin_length(repositories):
    _, repository = repositories

    with pytest.raises(
        ValueError,
        match="12 caracteres",
    ):
        repository.create(
            isin="INVALIDO",
        )


def test_rejects_invalid_isin_characters(
    repositories,
):
    _, repository = repositories

    with pytest.raises(
        ValueError,
        match="letras e numeros",
    ):
        repository.create(
            isin="BRTESTDBS-04",
        )


def test_rejects_missing_identifier(repositories):
    _, repository = repositories

    with pytest.raises(
        ValueError,
        match="codigo do ativo ou o ISIN",
    ):
        repository.create()


def test_rejects_unknown_issuer(repositories):
    _, repository = repositories

    with pytest.raises(
        ValueError,
        match="emissor informado nao existe",
    ):
        repository.create(
            asset_code="TEST15",
            issuer_id=999999,
        )


def test_rejects_duplicate_asset_code(
    repositories,
):
    _, repository = repositories

    repository.create(
        asset_code="DUPL12",
    )

    with pytest.raises(
        ValueError,
        match="codigo de ativo",
    ):
        repository.create(
            asset_code="dupl12",
        )

    assert repository.count() == 1


def test_rejects_duplicate_isin(repositories):
    _, repository = repositories

    repository.create(
        isin="BRTESTDBS005",
    )

    with pytest.raises(
        ValueError,
        match="esse ISIN",
    ):
        repository.create(
            isin="brtestdbs005",
        )

    assert repository.count() == 1


def test_get_by_id_code_and_isin(repositories):
    _, repository = repositories

    created = repository.create(
        asset_code="TEST16",
        isin="BRTESTDBS006",
    )

    by_id = repository.get_by_id(
        created.id
    )

    by_code = repository.get_by_asset_code(
        "test16"
    )

    by_isin = repository.get_by_isin(
        "brtestdbs006"
    )

    assert by_id is not None
    assert by_code is not None
    assert by_isin is not None

    assert by_id.id == created.id
    assert by_code.id == created.id
    assert by_isin.id == created.id


def test_get_or_create_returns_existing_record(
    repositories,
):
    _, repository = repositories

    original = repository.create(
        asset_code="TEST19",
        isin="BRTESTDBS007",
    )

    found, was_created = repository.get_or_create(
        asset_code="test19",
    )

    assert was_created is False
    assert found.id == original.id
    assert repository.count() == 1


def test_list_by_issuer(repositories):
    issuer_repository, repository = repositories
    issuer = create_issuer(issuer_repository)

    repository.create(
        asset_code="EMPR11",
        issuer_id=issuer.id,
    )

    repository.create(
        asset_code="EMPR12",
        issuer_id=issuer.id,
    )

    repository.create(
        asset_code="OUTR11",
    )

    results = repository.list_by_issuer(
        issuer.id
    )

    asset_codes = [
        item.asset_code
        for item in results
    ]

    assert asset_codes == [
        "EMPR11",
        "EMPR12",
    ]


def test_search_by_asset_code(repositories):
    _, repository = repositories

    repository.create(
        asset_code="BUSC12",
    )

    repository.create(
        asset_code="OUTR12",
    )

    results = repository.search(
        "BUSC"
    )

    assert len(results) == 1
    assert results[0].asset_code == "BUSC12"


def test_search_by_issuer_name(repositories):
    issuer_repository, repository = repositories

    issuer = issuer_repository.create(
        legal_name="Companhia Alfa de Energia",
        cnpj="22345678000198",
    )

    repository.create(
        asset_code="ALFA12",
        issuer_id=issuer.id,
    )

    results = repository.search(
        "Alfa de Energia"
    )

    assert len(results) == 1
    assert results[0].asset_code == "ALFA12"


def test_search_empty_query_returns_empty_list(
    repositories,
):
    _, repository = repositories

    assert repository.search("") == []
    assert repository.search("   ") == []
    assert repository.search(None) == []


def test_list_all_supports_pagination(
    repositories,
):
    _, repository = repositories

    repository.create(
        asset_code="PAGE11",
    )

    repository.create(
        asset_code="PAGE12",
    )

    repository.create(
        asset_code="PAGE13",
    )

    first_page = repository.list_all(
        limit=2,
        offset=0,
    )

    second_page = repository.list_all(
        limit=2,
        offset=2,
    )

    first_codes = [
        item.asset_code
        for item in first_page
    ]

    second_codes = [
        item.asset_code
        for item in second_page
    ]

    assert first_codes == [
        "PAGE11",
        "PAGE12",
    ]

    assert second_codes == [
        "PAGE13",
    ]


def test_count_and_status_filter(repositories):
    _, repository = repositories

    repository.create(
        asset_code="ATIV12",
        status="active",
    )

    repository.create(
        asset_code="ATIV13",
        status="active",
    )

    repository.create(
        asset_code="VENC12",
        status="matured",
    )

    active_records = repository.list_all(
        status="active"
    )

    assert repository.count() == 3
    assert repository.count("active") == 2
    assert repository.count("matured") == 1
    assert len(active_records) == 2


def test_update_identification(repositories):
    issuer_repository, repository = repositories
    issuer = create_issuer(issuer_repository)

    created = repository.create(
        asset_code="ANTG12",
    )

    updated = repository.update_identification(
        debenture_id=created.id,
        asset_code="NOVO12",
        isin="BRTESTDBS008",
        issuer_id=issuer.id,
        issue_number="2",
        series="3",
    )

    assert updated.asset_code == "NOVO12"
    assert updated.isin == "BRTESTDBS008"
    assert updated.issuer_id == issuer.id
    assert updated.issue_number == "2"
    assert updated.series == "3"

    old_record = repository.get_by_asset_code(
        "ANTG12"
    )

    assert old_record is None


def test_update_rejects_duplicate_code_and_rolls_back(
    repositories,
):
    _, repository = repositories

    first = repository.create(
        asset_code="PRIM12",
    )

    repository.create(
        asset_code="SEGU12",
    )

    with pytest.raises(
        ValueError,
        match="ja cadastrado",
    ):
        repository.update_identification(
            debenture_id=first.id,
            asset_code="SEGU12",
        )

    persisted = repository.get_by_id(
        first.id
    )

    assert persisted is not None
    assert persisted.asset_code == "PRIM12"


def test_update_status_inactive_and_active(
    repositories,
):
    _, repository = repositories

    created = repository.create(
        asset_code="REAT12",
        status="active",
    )

    inactive = repository.update_status(
        created.id,
        "inactive",
    )

    assert inactive.status == "inactive"
    assert inactive.inactive_at is not None

    active = repository.update_status(
        created.id,
        "active",
    )

    assert active.status == "active"
    assert active.inactive_at is None


def test_update_unknown_record_is_rejected(
    repositories,
):
    _, repository = repositories

    with pytest.raises(
        ValueError,
        match="Debenture nao encontrada",
    ):
        repository.update_status(
            999999,
            "active",
        )


def test_repository_preserves_database_integrity(
    repositories,
):
    _, repository = repositories

    repository.create(
        asset_code="INTE12",
        isin="BRTESTDBS009",
        status="active",
    )

    integrity = repository.db.integrity_check()

    foreign_key_errors = (
        repository.db.foreign_key_check()
    )

    assert integrity == "ok"
    assert foreign_key_errors == []