import pathlib

import pytest

from debenture_search.database import Database
from debenture_search.repositories.source_repository import (
    SourceRecord,
    SourceRepository,
)


PROJECT_DIR = pathlib.Path(__file__).resolve().parent.parent
MIGRATION_PATH = PROJECT_DIR / "migrations" / "001_initial_schema.sql"


@pytest.fixture
def context(tmp_path):
    db = Database(tmp_path / "sources.db")
    sql = MIGRATION_PATH.read_text(encoding="utf-8")

    with db.connection() as connection:
        connection.executescript(sql)
        connection.commit()

    return {
        "db": db,
        "repository": SourceRepository(db),
    }


def test_initial_sources_exist(context):
    repository = context["repository"]

    assert repository.get_by_code("SND") is not None
    assert repository.get_by_code("manual") is not None
    assert repository.count() == 4


def test_create_source(context):
    source = context["repository"].create(
        code="teste_api",
        name="  Fonte   de Teste  ",
        source_type="API",
        priority=500,
        active=True,
    )

    assert isinstance(source, SourceRecord)
    assert source.code == "TESTE_API"
    assert source.name == "Fonte de Teste"
    assert source.source_type == "api"
    assert source.priority == 500
    assert source.active is True


def test_rejects_duplicate_code(context):
    repository = context["repository"]
    repository.create(
        code="NOVA",
        name="Nova Fonte",
        source_type="internal",
    )

    with pytest.raises(ValueError, match="Ja existe"):
        repository.create(
            code="nova",
            name="Outra Fonte",
            source_type="api",
        )


def test_rejects_empty_code(context):
    with pytest.raises(ValueError, match="codigo"):
        context["repository"].create(
            code="   ",
            name="Fonte",
            source_type="api",
        )


def test_rejects_empty_name(context):
    with pytest.raises(ValueError, match="nome"):
        context["repository"].create(
            code="FONTE",
            name="   ",
            source_type="api",
        )


def test_rejects_invalid_type(context):
    with pytest.raises(ValueError, match="Tipo de fonte invalido"):
        context["repository"].create(
            code="FONTE",
            name="Fonte",
            source_type="desconhecido",
        )


def test_rejects_negative_priority(context):
    with pytest.raises(ValueError, match="negativa"):
        context["repository"].create(
            code="FONTE",
            name="Fonte",
            source_type="api",
            priority=-1,
        )


def test_get_or_create(context):
    repository = context["repository"]

    first, first_created = repository.get_or_create(
        code="EXTERNA",
        name="Fonte Externa",
        source_type="api",
    )
    second, second_created = repository.get_or_create(
        code="externa",
        name="Outro Nome",
        source_type="scraper",
    )

    assert first_created is True
    assert second_created is False
    assert first.id == second.id


def test_list_active_by_priority(context):
    repository = context["repository"]
    active_sources = repository.list_active()

    assert all(item.active for item in active_sources)
    priorities = [item.priority for item in active_sources]
    assert priorities == sorted(priorities, reverse=True)
    assert "ANBIMA_API" not in {
        item.code for item in active_sources
    }


def test_deactivate_and_activate(context):
    repository = context["repository"]
    source = repository.get_by_code("SND")

    deactivated = repository.deactivate(source.id)
    assert deactivated.active is False

    activated = repository.activate(source.id)
    assert activated.active is True


def test_update_priority(context):
    repository = context["repository"]
    source = repository.get_by_code("CVM")

    updated = repository.update_priority(
        source.id,
        750,
    )

    assert updated.priority == 750


def test_update_source(context):
    repository = context["repository"]
    source = repository.create(
        code="EDITAVEL",
        name="Nome Antigo",
        source_type="internal",
    )

    updated = repository.update(
        source.id,
        name="Nome Novo",
        source_type="document",
        priority=600,
        active=False,
    )

    assert updated.code == "EDITAVEL"
    assert updated.name == "Nome Novo"
    assert updated.source_type == "document"
    assert updated.priority == 600
    assert updated.active is False


def test_update_unknown_source(context):
    with pytest.raises(ValueError, match="Fonte nao encontrada"):
        context["repository"].update(
            999999,
            name="Inexistente",
        )


def test_count_with_active_filter(context):
    repository = context["repository"]

    assert repository.count() == 4
    assert repository.count(active=True) == 3
    assert repository.count(active=False) == 1


def test_database_integrity(context):
    repository = context["repository"]
    repository.create(
        code="INTEGRIDADE",
        name="Fonte de Integridade",
        source_type="internal",
    )

    assert context["db"].integrity_check() == "ok"
    assert context["db"].foreign_key_check() == []
