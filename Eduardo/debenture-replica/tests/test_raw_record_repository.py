import hashlib
import pathlib

import pytest

from debenture_search.database import Database
from debenture_search.repositories.raw_record_repository import (
    RawRecord,
    RawRecordRepository,
)


PROJECT_DIR = pathlib.Path(__file__).resolve().parent.parent
MIGRATION_PATH = (
    PROJECT_DIR
    / "migrations"
    / "001_initial_schema.sql"
)


@pytest.fixture
def context(tmp_path):
    db = Database(tmp_path / "raw_records.db")
    migration_sql = MIGRATION_PATH.read_text(encoding="utf-8")

    with db.connection() as connection:
        connection.executescript(migration_sql)
        connection.commit()

    source = db.fetch_one(
        "SELECT id FROM sources WHERE code = ?",
        ("SND",),
    )

    return {
        "db": db,
        "source_id": int(source["id"]),
        "repository": RawRecordRepository(db),
    }


def test_create_text_payload(context):
    repository = context["repository"]
    record, was_created = repository.create(
        source_id=context["source_id"],
        payload="<html>debenture</html>",
        request_url="https://example.test/ativo",
        request_parameters={"codigo": "TEST12"},
        content_type="text/html",
        http_status=200,
        parser_version="1.0.0",
    )

    assert was_created is True
    assert isinstance(record, RawRecord)
    assert record.text == "<html>debenture</html>"
    assert record.parameters == {"codigo": "TEST12"}
    assert record.processing_status == "pending"
    assert len(record.payload_sha256) == 64


def test_create_bytes_payload(context):
    record, was_created = context["repository"].create(
        source_id=context["source_id"],
        payload=b'{"asset":"TEST12"}',
        content_type="application/json",
        http_status=200,
    )

    assert was_created is True
    assert record.payload == b'{"asset":"TEST12"}'


def test_hash_matches_payload(context):
    payload = b"conteudo verificavel"
    record, _ = context["repository"].create(
        source_id=context["source_id"],
        payload=payload,
    )

    expected = hashlib.sha256(payload).hexdigest()
    assert record.payload_sha256 == expected


def test_same_payload_is_idempotent(context):
    repository = context["repository"]
    first, first_created = repository.create(
        source_id=context["source_id"],
        payload="mesmo conteudo",
    )
    second, second_created = repository.create(
        source_id=context["source_id"],
        payload="mesmo conteudo",
    )

    assert first_created is True
    assert second_created is False
    assert first.id == second.id
    assert repository.count() == 1


def test_rejects_unknown_source(context):
    with pytest.raises(
        ValueError,
        match="fonte informada nao existe",
    ):
        context["repository"].create(
            source_id=999999,
            payload="conteudo",
        )


def test_rejects_empty_payload(context):
    with pytest.raises(
        ValueError,
        match="payload nao pode ficar vazio",
    ):
        context["repository"].create(
            source_id=context["source_id"],
            payload=b"",
        )


def test_rejects_invalid_payload_type(context):
    with pytest.raises(
        ValueError,
        match="payload deve ser texto ou bytes",
    ):
        context["repository"].create(
            source_id=context["source_id"],
            payload={"nao": "permitido"},
        )


def test_rejects_invalid_http_status(context):
    with pytest.raises(
        ValueError,
        match="Status HTTP invalido",
    ):
        context["repository"].create(
            source_id=context["source_id"],
            payload="conteudo",
            http_status=999,
        )


def test_rejects_invalid_parameters_json(context):
    with pytest.raises(
        ValueError,
        match="JSON valido",
    ):
        context["repository"].create(
            source_id=context["source_id"],
            payload="conteudo",
            request_parameters="{invalido}",
        )


def test_get_by_id_and_hash(context):
    repository = context["repository"]
    created, _ = repository.create(
        source_id=context["source_id"],
        payload="localizar",
    )

    by_id = repository.get_by_id(created.id)
    by_hash = repository.get_by_hash(
        context["source_id"],
        created.payload_sha256,
    )

    assert by_id is not None
    assert by_hash is not None
    assert by_id.id == created.id
    assert by_hash.id == created.id


def test_update_processing_to_processed(context):
    repository = context["repository"]
    created, _ = repository.create(
        source_id=context["source_id"],
        payload="processar",
    )

    updated = repository.update_processing(
        created.id,
        "processed",
        parser_version="2.0.0",
    )

    assert updated.processing_status == "processed"
    assert updated.parser_version == "2.0.0"
    assert updated.processing_error is None


def test_failed_processing_requires_error(context):
    repository = context["repository"]
    created, _ = repository.create(
        source_id=context["source_id"],
        payload="falhar",
    )

    with pytest.raises(
        ValueError,
        match="precisa informar o erro",
    ):
        repository.update_processing(
            created.id,
            "failed",
        )


def test_update_processing_to_failed(context):
    repository = context["repository"]
    created, _ = repository.create(
        source_id=context["source_id"],
        payload="falha conhecida",
    )

    updated = repository.update_processing(
        created.id,
        "failed",
        parser_version="2.0.1",
        processing_error="Layout inesperado",
    )

    assert updated.processing_status == "failed"
    assert updated.processing_error == "Layout inesperado"


def test_list_by_source_and_status(context):
    repository = context["repository"]
    first, _ = repository.create(
        source_id=context["source_id"],
        payload="um",
    )
    repository.create(
        source_id=context["source_id"],
        payload="dois",
    )
    repository.update_processing(
        first.id,
        "processed",
    )

    all_records = repository.list_by_source(
        context["source_id"]
    )
    processed = repository.list_by_source(
        context["source_id"],
        status="processed",
    )

    assert len(all_records) == 2
    assert len(processed) == 1
    assert processed[0].id == first.id


def test_count_with_filters(context):
    repository = context["repository"]
    first, _ = repository.create(
        source_id=context["source_id"],
        payload="primeiro",
    )
    repository.create(
        source_id=context["source_id"],
        payload="segundo",
    )
    repository.update_processing(
        first.id,
        "processed",
    )

    assert repository.count() == 2
    assert repository.count(
        source_id=context["source_id"]
    ) == 2
    assert repository.count(status="processed") == 1
    assert repository.count(status="pending") == 1


def test_database_integrity_is_preserved(context):
    context["repository"].create(
        source_id=context["source_id"],
        payload="integridade",
        http_status=200,
    )

    assert context["db"].integrity_check() == "ok"
    assert context["db"].foreign_key_check() == []
