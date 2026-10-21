from pathlib import Path

import pytest

from debenture_search.database import Database
from debenture_search.repositories.debenture_repository import (
    DebentureRepository,
)
from debenture_search.repositories.observation_repository import (
    ObservationRepository,
)
from debenture_search.services.debenture_query_service import (
    DebentureQueryService,
)


MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent
    / "migrations"
    / "001_initial_schema.sql"
)


@pytest.fixture
def context(tmp_path):
    db = Database(tmp_path / "current_values.db")
    with db.connection() as connection:
        connection.executescript(MIGRATION_PATH.read_text(encoding="utf-8"))
        connection.commit()

    debenture = DebentureRepository(db).create(asset_code="CURR12")
    sources = {
        row["code"]: int(row["id"])
        for row in db.fetch_all("SELECT id, code FROM sources")
    }
    return {
        "db": db,
        "debenture": debenture,
        "observations": ObservationRepository(db),
        "sources": sources,
        "service": DebentureQueryService(db),
    }


def add_text(context, source, field_name, value, observed_at):
    return context["observations"].create(
        debenture_id=context["debenture"].id,
        source_id=context["sources"][source],
        field_name=field_name,
        value_type="text",
        value=value,
        observed_at=observed_at,
    )[0]


def test_higher_priority_source_wins_over_newer_lower_priority(context):
    add_text(context, "MANUAL", "rating", "AA", "2026-09-01T12:00:00+00:00")
    add_text(context, "SND", "rating", "A", "2026-09-10T12:00:00+00:00")

    current = context["service"].current_values(context["debenture"].id)

    assert current["rating"].value == "AA"
    assert current["rating"].source_code == "MANUAL"


def test_newest_wins_within_same_source(context):
    add_text(context, "SND", "rating", "A", "2026-09-01T12:00:00+00:00")
    add_text(context, "SND", "rating", "A+", "2026-09-10T12:00:00+00:00")

    current = context["service"].current_values(context["debenture"].id)

    assert current["rating"].value == "A+"


def test_inactive_source_is_ignored(context):
    # ANBIMA_API (prioridade 300) esta inativa no seed.
    add_text(context, "ANBIMA_API", "rating", "AAA", "2026-09-10T12:00:00+00:00")
    add_text(context, "SND", "rating", "A", "2026-09-01T12:00:00+00:00")

    current = context["service"].current_values(context["debenture"].id)

    assert current["rating"].value == "A"
    assert current["rating"].source_code == "SND"


def test_matches_observation_repository_current(context):
    add_text(context, "MANUAL", "rating", "AA", "2026-09-01T12:00:00+00:00")
    add_text(context, "SND", "rating", "A", "2026-09-10T12:00:00+00:00")
    add_text(context, "SND", "garantia", "Real", "2026-09-10T12:00:00+00:00")

    current = context["service"].current_values(context["debenture"].id)
    listed = context["observations"].list_current(context["debenture"].id)

    assert {item.field_name: item.value for item in listed} == {
        name: value.value for name, value in current.items()
    }
