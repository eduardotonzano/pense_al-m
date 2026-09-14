import pathlib

import pytest

from debenture_search.database import Database
from debenture_search.repositories.audit_repository import (
    AuditRecord,
    AuditRepository,
)


PROJECT_DIR = pathlib.Path(__file__).resolve().parent.parent
MIGRATION_PATH = (
    PROJECT_DIR
    / "migrations"
    / "001_initial_schema.sql"
)


@pytest.fixture
def context(tmp_path):
    db = Database(tmp_path / "audit.db")
    sql = MIGRATION_PATH.read_text(encoding="utf-8")

    with db.connection() as connection:
        connection.executescript(sql)
        connection.commit()

    return {
        "db": db,
        "repository": AuditRepository(db),
    }


def test_create_audit_record(context):
    record = context["repository"].create(
        actor="Eduardo",
        action="manual_update",
        entity_type="debenture",
        entity_id=1,
        before={"rating": "A+"},
        after={"rating": "AA-"},
        reason="Atualizacao de rating",
    )

    assert isinstance(record, AuditRecord)
    assert record.actor == "Eduardo"
    assert record.action == "manual_update"
    assert record.entity_type == "debenture"
    assert record.entity_id == 1
    assert record.before == {"rating": "A+"}
    assert record.after == {"rating": "AA-"}
    assert record.reason == "Atualizacao de rating"
    assert "+00:00" in record.occurred_at


def test_create_with_only_after_state(context):
    record = context["repository"].create(
        actor="system",
        action="create",
        entity_type="issuer",
        entity_id=2,
        after={"legal_name": "Empresa Teste"},
    )

    assert record.before is None
    assert record.after == {
        "legal_name": "Empresa Teste"
    }


def test_create_with_json_strings(context):
    record = context["repository"].create(
        actor="system",
        action="update",
        entity_type="source",
        entity_id=3,
        before='{"active":true}',
        after='{"active":false}',
    )

    assert record.before == {"active": True}
    assert record.after == {"active": False}


def test_rejects_empty_actor(context):
    with pytest.raises(ValueError, match="responsavel"):
        context["repository"].create(
            actor="   ",
            action="update",
            entity_type="debenture",
            entity_id=1,
            after={"status": "active"},
        )


def test_rejects_empty_action(context):
    with pytest.raises(ValueError, match="acao"):
        context["repository"].create(
            actor="Eduardo",
            action="",
            entity_type="debenture",
            entity_id=1,
            after={"status": "active"},
        )


def test_rejects_empty_entity_type(context):
    with pytest.raises(ValueError, match="tipo da entidade"):
        context["repository"].create(
            actor="Eduardo",
            action="update",
            entity_type=" ",
            entity_id=1,
            after={"status": "active"},
        )


def test_rejects_invalid_entity_id(context):
    with pytest.raises(ValueError, match="maior que zero"):
        context["repository"].create(
            actor="Eduardo",
            action="update",
            entity_type="debenture",
            entity_id=0,
            after={"status": "active"},
        )


def test_requires_before_or_after(context):
    with pytest.raises(ValueError, match="estado anterior ou posterior"):
        context["repository"].create(
            actor="Eduardo",
            action="update",
            entity_type="debenture",
            entity_id=1,
        )


def test_rejects_invalid_json(context):
    with pytest.raises(ValueError, match="JSON valido"):
        context["repository"].create(
            actor="Eduardo",
            action="update",
            entity_type="debenture",
            entity_id=1,
            after="{invalido}",
        )


def test_get_by_id(context):
    created = context["repository"].create(
        actor="system",
        action="create",
        entity_type="issuer",
        entity_id=5,
        after={"name": "Empresa"},
    )

    found = context["repository"].get_by_id(created.id)

    assert found is not None
    assert found.id == created.id


def test_list_by_entity(context):
    repository = context["repository"]
    repository.create(
        actor="Eduardo",
        action="create",
        entity_type="debenture",
        entity_id=10,
        after={"status": "active"},
    )
    repository.create(
        actor="Eduardo",
        action="update",
        entity_type="debenture",
        entity_id=10,
        before={"status": "active"},
        after={"status": "inactive"},
    )
    repository.create(
        actor="system",
        action="create",
        entity_type="issuer",
        entity_id=10,
        after={"name": "Empresa"},
    )

    records = repository.list_by_entity(
        "debenture",
        10,
    )

    assert len(records) == 2
    assert all(
        item.entity_type == "debenture"
        for item in records
    )


def test_list_by_actor(context):
    repository = context["repository"]
    repository.create(
        actor="Eduardo",
        action="create",
        entity_type="debenture",
        entity_id=20,
        after={"status": "active"},
    )
    repository.create(
        actor="system",
        action="create",
        entity_type="issuer",
        entity_id=21,
        after={"name": "Empresa"},
    )

    records = repository.list_by_actor("Eduardo")

    assert len(records) == 1
    assert records[0].actor == "Eduardo"


def test_count_with_filters(context):
    repository = context["repository"]
    repository.create(
        actor="Eduardo",
        action="create",
        entity_type="debenture",
        entity_id=30,
        after={"status": "active"},
    )
    repository.create(
        actor="system",
        action="create",
        entity_type="issuer",
        entity_id=31,
        after={"name": "Empresa"},
    )

    assert repository.count() == 2
    assert repository.count(actor="Eduardo") == 1
    assert repository.count(
        entity_type="debenture"
    ) == 1
    assert repository.count(entity_id=31) == 1


def test_database_integrity(context):
    context["repository"].create(
        actor="system",
        action="create",
        entity_type="debenture",
        entity_id=40,
        after={"status": "active"},
    )

    assert context["db"].integrity_check() == "ok"
    assert context["db"].foreign_key_check() == []
