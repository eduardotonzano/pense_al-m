import pathlib

import pytest

from debenture_search.database import Database
from debenture_search.repositories.conflict_repository import (
    ConflictRecord,
    ConflictRepository,
)
from debenture_search.repositories.debenture_repository import (
    DebentureRepository,
)
from debenture_search.repositories.observation_repository import (
    ObservationRepository,
)


PROJECT_DIR = pathlib.Path(__file__).resolve().parent.parent
MIGRATION_PATH = PROJECT_DIR / "migrations" / "001_initial_schema.sql"


@pytest.fixture
def context(tmp_path):
    db = Database(tmp_path / "conflicts.db")
    sql = MIGRATION_PATH.read_text(encoding="utf-8")

    with db.connection() as connection:
        connection.executescript(sql)
        connection.commit()

    debenture = DebentureRepository(db).create(
        asset_code="CONF12"
    )
    other_debenture = DebentureRepository(db).create(
        asset_code="CONF13"
    )
    observations = ObservationRepository(db)
    conflicts = ConflictRepository(db)

    snd = db.fetch_one(
        "SELECT id FROM sources WHERE code = ?",
        ("SND",),
    )
    manual = db.fetch_one(
        "SELECT id FROM sources WHERE code = ?",
        ("MANUAL",),
    )

    return {
        "db": db,
        "debenture": debenture,
        "other_debenture": other_debenture,
        "observations": observations,
        "conflicts": conflicts,
        "snd": int(snd["id"]),
        "manual": int(manual["id"]),
    }


def create_observation(context, source_id, value, field="rating", other=False):
    target = (
        context["other_debenture"]
        if other
        else context["debenture"]
    )
    return context["observations"].create(
        debenture_id=target.id,
        source_id=source_id,
        field_name=field,
        value_type="text",
        value=value,
        observed_at="2026-09-10T12:00:00+00:00",
    )[0]


def create_conflict(context):
    first = create_observation(
        context,
        context["snd"],
        "AAA",
    )
    second = create_observation(
        context,
        context["manual"],
        "AA-",
    )
    return context["conflicts"].create(
        context["debenture"].id,
        "rating",
        first.id,
        second.id,
    )[0]


def test_create_conflict(context):
    conflict = create_conflict(context)

    assert isinstance(conflict, ConflictRecord)
    assert conflict.debenture_id == context["debenture"].id
    assert conflict.field_name == "rating"
    assert conflict.status == "open"
    assert conflict.resolved_at is None


def test_create_is_idempotent_even_with_reversed_pair(context):
    first = create_observation(context, context["snd"], "AAA")
    second = create_observation(context, context["manual"], "AA-")

    original, original_created = context["conflicts"].create(
        context["debenture"].id,
        "rating",
        first.id,
        second.id,
    )
    repeated, repeated_created = context["conflicts"].create(
        context["debenture"].id,
        "rating",
        second.id,
        first.id,
    )

    assert original_created is True
    assert repeated_created is False
    assert original.id == repeated.id
    assert context["conflicts"].count() == 1


def test_rejects_same_observation(context):
    observation = create_observation(
        context,
        context["snd"],
        "AAA",
    )

    with pytest.raises(ValueError, match="ela mesma"):
        context["conflicts"].create(
            context["debenture"].id,
            "rating",
            observation.id,
            observation.id,
        )


def test_rejects_unknown_observation(context):
    observation = create_observation(
        context,
        context["snd"],
        "AAA",
    )

    with pytest.raises(ValueError, match="nao existe"):
        context["conflicts"].create(
            context["debenture"].id,
            "rating",
            observation.id,
            999999,
        )


def test_rejects_observation_from_other_debenture(context):
    first = create_observation(context, context["snd"], "AAA")
    second = create_observation(
        context,
        context["manual"],
        "AA-",
        other=True,
    )

    with pytest.raises(ValueError, match="debenture informada"):
        context["conflicts"].create(
            context["debenture"].id,
            "rating",
            first.id,
            second.id,
        )


def test_rejects_different_fields(context):
    first = create_observation(context, context["snd"], "AAA")
    second = create_observation(
        context,
        context["manual"],
        "CDI",
        field="indexador",
    )

    with pytest.raises(ValueError, match="mesmo campo"):
        context["conflicts"].create(
            context["debenture"].id,
            "rating",
            first.id,
            second.id,
        )


def test_rejects_same_source(context):
    first = context["observations"].create(
        debenture_id=context["debenture"].id,
        source_id=context["snd"],
        field_name="rating",
        value_type="text",
        value="AAA",
        observed_at="2026-09-01T12:00:00+00:00",
    )[0]
    second = context["observations"].create(
        debenture_id=context["debenture"].id,
        source_id=context["snd"],
        field_name="rating",
        value_type="text",
        value="AA-",
        observed_at="2026-09-10T12:00:00+00:00",
    )[0]

    with pytest.raises(ValueError, match="fontes diferentes"):
        context["conflicts"].create(
            context["debenture"].id,
            "rating",
            first.id,
            second.id,
        )


def test_resolve_conflict(context):
    conflict = create_conflict(context)
    resolved = context["conflicts"].resolve(
        conflict.id,
        "Valor manual confirmado pela agencia.",
    )

    assert resolved.status == "resolved"
    assert resolved.resolution_note == (
        "Valor manual confirmado pela agencia."
    )
    assert resolved.resolved_at is not None
    assert "+00:00" in resolved.resolved_at


def test_resolve_requires_note(context):
    conflict = create_conflict(context)

    with pytest.raises(ValueError, match="justificativa"):
        context["conflicts"].resolve(conflict.id, "   ")


def test_ignore_conflict(context):
    conflict = create_conflict(context)
    ignored = context["conflicts"].ignore(
        conflict.id,
        "Diferenca de data-base.",
    )

    assert ignored.status == "ignored"
    assert ignored.resolution_note == "Diferenca de data-base."
    assert ignored.resolved_at is None


def test_cannot_close_twice(context):
    conflict = create_conflict(context)
    context["conflicts"].resolve(conflict.id, "Confirmado")

    with pytest.raises(ValueError, match="ja foi encerrado"):
        context["conflicts"].ignore(conflict.id)


def test_list_by_debenture_and_status(context):
    repository = context["conflicts"]
    first = create_conflict(context)
    repository.resolve(first.id, "Confirmado")

    third = context["observations"].create(
        debenture_id=context["debenture"].id,
        source_id=context["snd"],
        field_name="garantia",
        value_type="text",
        value="Real",
        observed_at="2026-09-10T12:01:00+00:00",
    )[0]
    fourth = context["observations"].create(
        debenture_id=context["debenture"].id,
        source_id=context["manual"],
        field_name="garantia",
        value_type="text",
        value="Quirografaria",
        observed_at="2026-09-10T12:01:00+00:00",
    )[0]
    repository.create(
        context["debenture"].id,
        "garantia",
        third.id,
        fourth.id,
    )

    all_conflicts = repository.list_by_debenture(
        context["debenture"].id
    )
    open_conflicts = repository.list_by_debenture(
        context["debenture"].id,
        status="open",
    )

    assert len(all_conflicts) == 2
    assert len(open_conflicts) == 1
    assert open_conflicts[0].field_name == "garantia"


def test_count_with_filters(context):
    conflict = create_conflict(context)
    context["conflicts"].resolve(conflict.id, "Confirmado")

    assert context["conflicts"].count() == 1
    assert context["conflicts"].count(
        context["debenture"].id
    ) == 1
    assert context["conflicts"].count(status="resolved") == 1
    assert context["conflicts"].count(status="open") == 0


def test_database_integrity(context):
    create_conflict(context)

    assert context["db"].integrity_check() == "ok"
    assert context["db"].foreign_key_check() == []
