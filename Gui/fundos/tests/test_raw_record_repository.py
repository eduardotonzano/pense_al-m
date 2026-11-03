import pytest

from apoio import T0
from apoio import fake_sha256
from fundos.repositories.collection_repository import CollectionRunRepository
from fundos.repositories.raw_record_repository import RawRecordRepository
from fundos.repositories.source_repository import SourceRepository


@pytest.fixture
def ctx(connection):
    sources = SourceRepository(connection)
    runs = CollectionRunRepository(connection)
    cvm = sources.get_by_code("CVM_DADOS_ABERTOS").id
    manual = sources.get_by_code("MANUAL").id

    return {
        "raws": RawRecordRepository(connection),
        "cvm": cvm,
        "manual": manual,
        "cvm_run": runs.start(cvm, started_at=T0).id,
        "manual_run": runs.start(manual, started_at=T0).id,
    }


def register(ctx, **overrides):
    arguments = {
        "source_id": ctx["cvm"],
        "collection_run_id": ctx["cvm_run"],
        "file_name": "informe_ficticio.zip",
        "size_bytes": 1234,
        "sha256": fake_sha256("zip"),
        "request_url": "https://exemplo.invalid/informe_ficticio.zip",
        "http_status": 200,
        "collected_at": T0,
    }
    arguments.update(overrides)
    return ctx["raws"].register_file(**arguments)


def test_registers_the_manifest(ctx):
    record, created = register(ctx, line_count=None)

    assert created
    assert (record.file_name, record.size_bytes, record.sha256) == (
        "informe_ficticio.zip",
        1234,
        fake_sha256("zip"),
    )
    assert record.collected_at == T0
    assert record.processing_status == "pending"


def test_same_manifest_is_idempotent(ctx):
    first, _ = register(ctx)
    again, created = register(ctx, sha256=fake_sha256("zip").upper())

    assert not created
    assert again.id == first.id

    with pytest.raises(ValueError, match="outro tamanho"):
        register(ctx, size_bytes=99)


def test_new_hash_is_a_new_manifest(ctx):
    first, _ = register(ctx)
    second, created = register(ctx, sha256=fake_sha256("zip-atualizado"))

    assert created
    assert second.id != first.id


def test_member_belongs_to_a_top_level_file_of_the_same_source(ctx):
    zip_record, _ = register(ctx)
    member, _ = register(
        ctx,
        file_name="tabela_ficticia.csv",
        sha256=fake_sha256("csv"),
        size_bytes=500,
        line_count=10,
        parent_raw_record_id=zip_record.id,
    )

    assert ctx["raws"].list_members(zip_record.id) == [member]

    with pytest.raises(ValueError, match="primeiro nivel"):
        register(
            ctx,
            file_name="neto.csv",
            sha256=fake_sha256("neto"),
            parent_raw_record_id=member.id,
        )

    with pytest.raises(ValueError, match="outra fonte"):
        register(
            ctx,
            source_id=ctx["manual"],
            collection_run_id=ctx["manual_run"],
            file_name="evidencia.csv",
            sha256=fake_sha256("evidencia"),
            parent_raw_record_id=zip_record.id,
        )


def test_run_of_another_source_is_refused(ctx):
    with pytest.raises(ValueError, match="outra fonte"):
        register(ctx, collection_run_id=ctx["manual_run"])


@pytest.mark.parametrize(
    "file_name",
    ["pasta/arquivo.zip", "pasta\\arquivo.zip", "C:arquivo.zip", " arquivo.zip", ""],
)
def test_file_name_cannot_carry_a_path(ctx, file_name):
    with pytest.raises(ValueError, match="nome do arquivo"):
        register(ctx, file_name=file_name)


@pytest.mark.parametrize(
    "overrides",
    [
        {"sha256": "abc"},
        {"sha256": None},
        {"size_bytes": 0},
        {"size_bytes": True},
        {"line_count": -1},
        {"request_url": "http://exemplo.invalid/a.zip"},
        {"http_status": 99},
        {"collected_at": "2026-10-27T13:00:00"},
    ],
    ids=["hash-curto", "hash-ausente", "tamanho-zero", "tamanho-bool", "linhas-negativas", "http", "status-http", "sem-fuso"],
)
def test_invalid_manifest_values_are_refused(ctx, overrides):
    with pytest.raises(ValueError):
        register(ctx, **overrides)


def test_update_processing(ctx):
    record, _ = register(ctx)
    raws = ctx["raws"]

    with pytest.raises(ValueError, match="erro"):
        raws.update_processing(record.id, "failed")

    failed = raws.update_processing(record.id, "failed", processing_error="falha ficticia")
    processed = raws.update_processing(record.id, "processed", parser_version="0.1")

    assert (failed.processing_status, failed.processing_error) == ("failed", "falha ficticia")
    assert (processed.processing_status, processed.processing_error) == ("processed", None)
    assert processed.parser_version == "0.1"

    with pytest.raises(ValueError, match="nao encontrado"):
        raws.update_processing(999, "processed")


def test_manifest_table_has_no_content_column(connection):
    columns = {
        (row[1], row[2].upper())
        for row in connection.execute("PRAGMA table_info(raw_records)")
    }

    assert not any(kind == "BLOB" for _, kind in columns)
    assert not any(name in ("payload", "content", "data") for name, _ in columns)
