from __future__ import annotations

import sqlite3
from datetime import datetime

import pytest

from credit_assets.database.connection import connect, initialize_database
from credit_assets.repositories.informe_indicator_repository import (
    SOURCE,
    IndicatorConflictError,
    InformeIndicator,
    InformeIndicatorRepository,
)
from credit_assets.repositories.rating_repository import Rating, RatingRepository
from tests.document_fixtures import insert_version, make_origin

STAMP = "2026-10-23T12:00:00+00:00"


def make_database(tmp_path):
    connection = connect(tmp_path / "informe.db")
    initialize_database(connection)
    return connection, make_origin(connection)


def sample_indicators() -> list[InformeIndicator]:
    return [
        InformeIndicator("/Informe/A", "", "1.5", "number"),
        InformeIndicator("/Informe/B", "", "texto", "text"),
        InformeIndicator("/Informe/C", "", None, "empty"),
        InformeIndicator("/Informe/Classe/Valor", "3:2", "2026-01-31", "date", unit="UN"),
    ]


def add_sample(repository, origin, **overrides) -> int:
    arguments = dict(
        asset_id=origin.asset1,
        document_id=origin.doc1,
        version_id=origin.ver1,
        reference_period="2026-08-01",
        indicators=sample_indicators(),
        run_id="run-1",
        parser_version="informe_mensal_xml/1",
    )
    arguments.update(overrides)
    return repository.add_many(**arguments)


# ----------------------------------------------------------- indicadores

def test_add_many_stores_every_indicator_with_its_origin_and_audit_columns(tmp_path):
    connection, origin = make_database(tmp_path)
    repository = InformeIndicatorRepository(connection)

    added = add_sample(repository, origin, collected_at=STAMP)

    rows = repository.list_for_document(origin.doc1)
    assert added == 4 and len(rows) == 4
    assert [(row["field"], row["occurrence"], row["value"], row["value_kind"], row["unit"]) for row in rows] == [
        ("/Informe/A", "", "1.5", "number", None),
        ("/Informe/B", "", "texto", "text", None),
        ("/Informe/C", "", None, "empty", None),
        ("/Informe/Classe/Valor", "3:2", "2026-01-31", "date", "UN"),
    ]
    assert {(row["asset_id"], row["document_id"], row["version_id"]) for row in rows} == {
        (origin.asset1, origin.doc1, origin.ver1)
    }
    assert {row["reference_period"] for row in rows} == {"2026-08-01"}
    assert {(row["source"], row["collected_at"], row["parser_version"], row["run_id"]) for row in rows} == {
        (SOURCE, STAMP, "informe_mensal_xml/1", "run-1")
    }


def test_collected_at_defaults_to_the_utc_time_of_the_reading(tmp_path):
    connection, origin = make_database(tmp_path)
    repository = InformeIndicatorRepository(connection)

    add_sample(repository, origin)

    stamps = {row["collected_at"] for row in repository.list_for_document(origin.doc1)}
    assert len(stamps) == 1 and datetime.fromisoformat(stamps.pop()).utcoffset().total_seconds() == 0


def test_reading_the_same_file_again_stores_nothing_new(tmp_path):
    connection, origin = make_database(tmp_path)
    repository = InformeIndicatorRepository(connection)
    add_sample(repository, origin, collected_at=STAMP)

    again = add_sample(repository, origin, run_id="run-2", collected_at="2026-10-24T12:00:00+00:00")

    assert again == 0
    assert repository.count_for_version(origin.ver1) == 4
    assert {row["run_id"] for row in repository.list_for_document(origin.doc1)} == {"run-1"}


def test_a_different_value_for_the_same_field_is_a_conflict_and_nothing_is_written(tmp_path):
    connection, origin = make_database(tmp_path)
    repository = InformeIndicatorRepository(connection)
    add_sample(repository, origin)
    changed = sample_indicators()
    changed[1] = InformeIndicator("/Informe/B", "", "outro texto", "text")
    changed.append(InformeIndicator("/Informe/Novo", "", "7", "number"))

    with pytest.raises(IndicatorConflictError, match="/Informe/B"):
        add_sample(repository, origin, indicators=changed)

    assert repository.count_for_version(origin.ver1) == 4


def test_a_different_period_for_the_same_field_is_also_a_conflict(tmp_path):
    connection, origin = make_database(tmp_path)
    repository = InformeIndicatorRepository(connection)
    add_sample(repository, origin)

    with pytest.raises(IndicatorConflictError):
        add_sample(repository, origin, reference_period="2026-09-01")


def test_a_new_version_of_the_file_stores_its_own_rows_and_keeps_the_old_ones(tmp_path):
    connection, origin = make_database(tmp_path)
    repository = InformeIndicatorRepository(connection)
    add_sample(repository, origin)
    new_version = insert_version(connection, origin.doc1, "c" * 64)
    changed = sample_indicators()
    changed[0] = InformeIndicator("/Informe/A", "", "2.5", "number")

    added = add_sample(repository, origin, version_id=new_version, indicators=changed)

    assert added == 4
    assert repository.count_for_version(origin.ver1) == 4 and repository.count_for_version(new_version) == 4
    assert len(repository.list_for_document(origin.doc1)) == 8


def test_the_same_field_twice_in_one_reading_is_refused(tmp_path):
    connection, origin = make_database(tmp_path)
    repository = InformeIndicatorRepository(connection)
    twice = [InformeIndicator("/Informe/A", "", "1", "number"), InformeIndicator("/Informe/A", "", "2", "number")]

    with pytest.raises(ValueError, match="repetido"):
        add_sample(repository, origin, indicators=twice)

    assert repository.count_for_version(origin.ver1) == 0


def test_schema_errors_propagate_and_the_caller_can_roll_back(tmp_path):
    connection, origin = make_database(tmp_path)
    repository = InformeIndicatorRepository(connection)
    broken = sample_indicators() + [InformeIndicator("/Informe/Z", "", "1", "decimal")]

    with pytest.raises(sqlite3.IntegrityError):
        add_sample(repository, origin, indicators=broken)

    connection.rollback()
    assert repository.count_for_version(origin.ver1) == 0


def test_an_indicator_of_another_document_is_refused_by_the_database(tmp_path):
    connection, origin = make_database(tmp_path)

    with pytest.raises(sqlite3.IntegrityError, match="nao sao do documento"):
        add_sample(InformeIndicatorRepository(connection), origin, version_id=origin.ver2)


# --------------------------------------------------------------- ratings

def sample_rating(origin, **overrides) -> Rating:
    values = dict(
        asset_id=origin.asset1,
        agency=" Agencia Teste ",
        grade=" NOTA-TESTE ",
        rating_date="2026-07-15",
        document_id=origin.doc1,
        version_id=origin.ver1,
        quoted_text=" trecho inventado ",
        page=3,
    )
    values.update(overrides)
    return Rating(**values)


def add_rating(repository, rating, **overrides) -> bool:
    arguments = dict(run_id="run-1", parser_version="rating/1", collected_at=STAMP)
    arguments.update(overrides)
    return repository.add(rating, **arguments)


def test_a_rating_is_stored_as_pending_review_with_page_quote_and_origin(tmp_path):
    connection, origin = make_database(tmp_path)
    repository = RatingRepository(connection)

    assert add_rating(repository, sample_rating(origin)) is True

    row = repository.list_for_asset(origin.asset1)[0]
    assert (row["agency"], row["grade"], row["rating_date"]) == ("Agencia Teste", "NOTA-TESTE", "2026-07-15")
    assert (row["document_id"], row["version_id"], row["page"], row["source_ref"]) == (
        origin.doc1, origin.ver1, 3, None,
    )
    assert (row["quoted_text"], row["review_status"], row["reviewed_at"]) == ("trecho inventado", "pending_review", None)
    assert (row["collected_at"], row["parser_version"], row["run_id"]) == (STAMP, "rating/1", "run-1")


def test_a_rating_read_from_an_xml_field_points_to_its_path(tmp_path):
    connection, origin = make_database(tmp_path)
    repository = RatingRepository(connection)

    add_rating(repository, sample_rating(origin, page=None, source_ref="/Informe/Classe/Rating"))

    row = repository.list_for_asset(origin.asset1)[0]
    assert (row["page"], row["source_ref"]) == (None, "/Informe/Classe/Rating")


def test_the_same_rating_of_the_same_file_is_not_stored_twice(tmp_path):
    connection, origin = make_database(tmp_path)
    repository = RatingRepository(connection)
    add_rating(repository, sample_rating(origin))

    again = add_rating(repository, sample_rating(origin, agency="Agencia Teste", grade="NOTA-TESTE", page=9))

    assert again is False
    assert len(repository.list_for_asset(origin.asset1)) == 1


def test_only_verified_ratings_reach_the_ficha_and_review_can_be_undone(tmp_path):
    connection, origin = make_database(tmp_path)
    repository = RatingRepository(connection)
    add_rating(repository, sample_rating(origin, grade="A"))
    add_rating(repository, sample_rating(origin, grade="B"))
    first, second = [row["rating_id"] for row in repository.list_for_asset(origin.asset1)]

    repository.review(first, "verified", reviewed_at=STAMP)
    repository.review(second, "rejected")

    verified = repository.list_for_asset(origin.asset1, verified_only=True)
    assert [(row["grade"], row["reviewed_at"]) for row in verified] == [("A", STAMP)]
    assert repository.list_for_asset(origin.asset1)[1]["reviewed_at"] is not None

    repository.review(first, "pending_review")

    assert repository.list_for_asset(origin.asset1, verified_only=True) == []
    assert repository.list_for_asset(origin.asset1)[0]["reviewed_at"] is None


def test_review_refuses_an_unknown_status_and_an_unknown_rating(tmp_path):
    connection, origin = make_database(tmp_path)
    repository = RatingRepository(connection)
    add_rating(repository, sample_rating(origin))

    with pytest.raises(ValueError, match="invalido"):
        repository.review(1, "approved")

    with pytest.raises(ValueError, match="inexistente"):
        repository.review(999, "verified")


def test_a_rating_without_a_valid_place_or_of_another_document_is_refused(tmp_path):
    connection, origin = make_database(tmp_path)
    repository = RatingRepository(connection)

    with pytest.raises(sqlite3.IntegrityError):
        add_rating(repository, sample_rating(origin, page=0))

    with pytest.raises(sqlite3.IntegrityError):
        add_rating(repository, sample_rating(origin, page=None))

    with pytest.raises(sqlite3.IntegrityError, match="nao sao do documento"):
        add_rating(repository, sample_rating(origin, version_id=origin.ver2))

    assert repository.list_for_asset(origin.asset1) == []
