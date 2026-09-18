import pathlib

import pytest

from debenture_search.database import Database
from debenture_search.repositories.debenture_repository import (
    DebentureRepository,
)
from debenture_search.repositories.observation_repository import (
    ObservationRepository,
)


PROJECT_DIR = pathlib.Path(__file__).resolve().parent.parent
MIGRATION_PATH = (
    PROJECT_DIR
    / "migrations"
    / "001_initial_schema.sql"
)


@pytest.fixture
def context(tmp_path):
    db = Database(tmp_path / "observation_queries.db")
    sql = MIGRATION_PATH.read_text(encoding="utf-8")

    with db.connection() as connection:
        connection.executescript(sql)
        connection.commit()

    debentures = DebentureRepository(db)
    observations = ObservationRepository(db)
    debenture = debentures.create(asset_code="QUERY12")

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
        "observations": observations,
        "snd": int(snd["id"]),
        "manual": int(manual["id"]),
    }


def add_rating(context, source_id, value, observed_at):
    return context["observations"].create(
        debenture_id=context["debenture"].id,
        source_id=source_id,
        field_name="rating",
        value_type="text",
        value=value,
        observed_at=observed_at,
    )[0]


def test_history_is_newest_first(context):
    add_rating(
        context,
        context["snd"],
        "A+",
        "2026-09-01T12:00:00+00:00",
    )
    add_rating(
        context,
        context["snd"],
        "AA-",
        "2026-09-10T12:00:00+00:00",
    )

    history = context["observations"].list_history(
        context["debenture"].id,
        "rating",
    )

    assert [item.value for item in history] == ["AA-", "A+"]


def test_history_can_list_all_fields(context):
    repository = context["observations"]
    add_rating(
        context,
        context["snd"],
        "AA-",
        "2026-09-10T12:00:00+00:00",
    )
    repository.create(
        debenture_id=context["debenture"].id,
        source_id=context["snd"],
        field_name="spread",
        value_type="numeric",
        value="2.5",
        observed_at="2026-09-10T12:01:00+00:00",
    )

    history = repository.list_history(
        context["debenture"].id
    )

    assert len(history) == 2
    assert {item.field_name for item in history} == {
        "rating",
        "spread",
    }


def test_history_supports_pagination(context):
    repository = context["observations"]
    for minute, value in enumerate(["A", "A+", "AA-"]):
        add_rating(
            context,
            context["snd"],
            value,
            "2026-09-10T12:0" + str(minute) + ":00+00:00",
        )

    first = repository.list_history(
        context["debenture"].id,
        "rating",
        limit=2,
        offset=0,
    )
    second = repository.list_history(
        context["debenture"].id,
        "rating",
        limit=2,
        offset=2,
    )

    assert len(first) == 2
    assert len(second) == 1


def test_current_uses_source_priority(context):
    add_rating(
        context,
        context["snd"],
        "AAA",
        "2026-09-10T12:00:00+00:00",
    )
    manual = add_rating(
        context,
        context["manual"],
        "AA-",
        "2026-09-01T12:00:00+00:00",
    )

    current = context["observations"].get_current(
        context["debenture"].id,
        "rating",
    )

    assert current is not None
    assert current.id == manual.id
    assert current.value == "AA-"
    assert current.source_id == context["manual"]


def test_current_uses_newest_with_same_source(context):
    add_rating(
        context,
        context["snd"],
        "A+",
        "2026-09-01T12:00:00+00:00",
    )
    newest = add_rating(
        context,
        context["snd"],
        "AA-",
        "2026-09-10T12:00:00+00:00",
    )

    current = context["observations"].get_current(
        context["debenture"].id,
        "rating",
    )

    assert current is not None
    assert current.id == newest.id
    assert current.value == "AA-"


def test_current_returns_none_for_missing_field(context):
    current = context["observations"].get_current(
        context["debenture"].id,
        "rating",
    )

    assert current is None


def test_list_current_returns_one_per_field(context):
    repository = context["observations"]
    add_rating(
        context,
        context["snd"],
        "A+",
        "2026-09-01T12:00:00+00:00",
    )
    add_rating(
        context,
        context["snd"],
        "AA-",
        "2026-09-10T12:00:00+00:00",
    )
    repository.create(
        debenture_id=context["debenture"].id,
        source_id=context["snd"],
        field_name="indexador",
        value_type="text",
        value="CDI",
        observed_at="2026-09-10T12:00:00+00:00",
    )

    current = repository.list_current(
        context["debenture"].id
    )

    assert len(current) == 2
    assert {item.field_name for item in current} == {
        "rating",
        "indexador",
    }


def test_count_with_filters(context):
    repository = context["observations"]
    add_rating(
        context,
        context["snd"],
        "A+",
        "2026-09-01T12:00:00+00:00",
    )
    add_rating(
        context,
        context["snd"],
        "AA-",
        "2026-09-10T12:00:00+00:00",
    )
    repository.create(
        debenture_id=context["debenture"].id,
        source_id=context["snd"],
        field_name="indexador",
        value_type="text",
        value="CDI",
        observed_at="2026-09-10T12:00:00+00:00",
    )

    assert repository.count() == 3
    assert repository.count(
        context["debenture"].id
    ) == 3
    assert repository.count(
        context["debenture"].id,
        "rating",
    ) == 2


def test_queries_reject_unknown_debenture(context):
    repository = context["observations"]

    with pytest.raises(
        ValueError,
        match="debenture informada nao existe",
    ):
        repository.list_history(999999)

    with pytest.raises(
        ValueError,
        match="debenture informada nao existe",
    ):
        repository.get_current(999999, "rating")

    with pytest.raises(
        ValueError,
        match="debenture informada nao existe",
    ):
        repository.list_current(999999)


def test_database_integrity_after_queries(context):
    add_rating(
        context,
        context["snd"],
        "AA-",
        "2026-09-10T12:00:00+00:00",
    )
    context["observations"].list_history(
        context["debenture"].id
    )
    context["observations"].list_current(
        context["debenture"].id
    )

    assert context["db"].integrity_check() == "ok"
    assert context["db"].foreign_key_check() == []
