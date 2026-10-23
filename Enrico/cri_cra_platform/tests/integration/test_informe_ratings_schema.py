from __future__ import annotations

import sqlite3

import pytest

from credit_assets.database.connection import connect, initialize_database
from tests.document_fixtures import insert_document, insert_version, make_origin


def make_database(tmp_path):
    connection = connect(tmp_path / "informe.db")
    initialize_database(connection)
    return connection, make_origin(connection)


def indicator_row(origin, **overrides) -> dict:
    row = dict(
        asset_id=origin.asset1,
        document_id=origin.doc1,
        version_id=origin.ver1,
        reference_period="2026-08-01",
        field="/Informe/Valor",
        occurrence="",
        value="10.5",
        value_kind="number",
        unit=None,
        source="fundosnet_informe_mensal_xml",
        collected_at="2026-10-23T12:00:00+00:00",
        parser_version="informe_mensal_xml/1",
        run_id="run-1",
    )
    row.update(overrides)
    return row


def rating_row(origin, **overrides) -> dict:
    row = dict(
        asset_id=origin.asset1,
        agency="Agencia Teste",
        grade="NOTA-TESTE",
        rating_date="2026-07-15",
        document_id=origin.doc1,
        version_id=origin.ver1,
        page=3,
        source_ref=None,
        quoted_text="trecho inventado do relatorio",
        review_status="pending_review",
        reviewed_at=None,
        collected_at="2026-10-23T12:00:00+00:00",
        parser_version="rating/1",
        run_id="run-1",
    )
    row.update(overrides)
    return row


def insert(connection, table: str, row: dict) -> None:
    connection.execute(
        f"INSERT INTO {table} ({', '.join(row)}) VALUES ({', '.join('?' * len(row))})",
        tuple(row.values()),
    )


# ------------------------------------------------------- informe_indicators

def test_a_valid_indicator_is_stored_with_its_origin(tmp_path):
    connection, origin = make_database(tmp_path)

    insert(connection, "informe_indicators", indicator_row(origin))

    row = connection.execute("SELECT * FROM informe_indicators").fetchone()
    assert (row["document_id"], row["version_id"], row["asset_id"]) == (origin.doc1, origin.ver1, origin.asset1)
    assert (row["field"], row["occurrence"], row["value"], row["value_kind"]) == (
        "/Informe/Valor", "", "10.5", "number",
    )
    assert row["reference_period"] == "2026-08-01" and row["collected_at"].endswith("+00:00")


def test_an_empty_element_is_stored_as_empty_with_a_null_value(tmp_path):
    connection, origin = make_database(tmp_path)

    insert(connection, "informe_indicators", indicator_row(origin, value=None, value_kind="empty"))

    assert connection.execute("SELECT value, value_kind FROM informe_indicators").fetchone()[:] == (None, "empty")


def test_occurrence_defaults_to_empty_when_it_is_left_out(tmp_path):
    connection, origin = make_database(tmp_path)
    row = indicator_row(origin)
    del row["occurrence"]

    insert(connection, "informe_indicators", row)

    assert connection.execute("SELECT occurrence FROM informe_indicators").fetchone()[0] == ""


BAD_INDICATOR_VALUES = [
    ("asset_id", None), ("document_id", None), ("version_id", None),
    ("asset_id", 999), ("document_id", 999), ("version_id", 999),
    ("reference_period", None), ("reference_period", "2026-02-30"),
    ("reference_period", "ago/2026"), ("reference_period", "2026-08"),
    ("field", None), ("field", ""), ("field", "   "),
    ("occurrence", None),
    ("value_kind", None), ("value_kind", "decimal"),
    ("value", None), ("value", ""), ("value", "   "),
    ("value_kind", "empty"),
    ("unit", "  "),
    ("source", None), ("source", ""),
    ("collected_at", None), ("collected_at", "ontem"),
    ("parser_version", None), ("parser_version", ""),
    ("run_id", None), ("run_id", "run-que-nao-existe"),
]


@pytest.mark.parametrize(("column", "value"), BAD_INDICATOR_VALUES)
def test_schema_refuses_an_indicator_without_origin_period_or_valid_content(tmp_path, column, value):
    connection, origin = make_database(tmp_path)
    insert(connection, "informe_indicators", indicator_row(origin))
    connection.execute("DELETE FROM informe_indicators")

    with pytest.raises(sqlite3.IntegrityError):
        insert(connection, "informe_indicators", indicator_row(origin, **{column: value}))


def test_the_same_field_cannot_repeat_in_a_version_but_can_in_another_occurrence_or_version(tmp_path):
    connection, origin = make_database(tmp_path)
    insert(connection, "informe_indicators", indicator_row(origin))

    with pytest.raises(sqlite3.IntegrityError):
        insert(connection, "informe_indicators", indicator_row(origin, value="99"))

    insert(connection, "informe_indicators", indicator_row(origin, occurrence="3:2"))
    other_version = insert_version(connection, origin.doc1, "c" * 64)
    insert(connection, "informe_indicators", indicator_row(origin, version_id=other_version))

    assert connection.execute("SELECT COUNT(*) FROM informe_indicators").fetchone()[0] == 3


@pytest.mark.parametrize(
    "overrides",
    [
        {"version_id": "ver2"},
        {"asset_id": "asset2"},
        {"document_id": "doc2"},
    ],
)
def test_a_version_or_asset_that_is_not_of_the_document_is_refused(tmp_path, overrides):
    connection, origin = make_database(tmp_path)
    resolved = {key: getattr(origin, value) for key, value in overrides.items()}

    with pytest.raises(sqlite3.IntegrityError, match="nao sao do documento"):
        insert(connection, "informe_indicators", indicator_row(origin, **resolved))


def test_an_indicator_cannot_be_moved_to_another_document_but_its_value_can_be_corrected(tmp_path):
    connection, origin = make_database(tmp_path)
    insert(connection, "informe_indicators", indicator_row(origin))

    with pytest.raises(sqlite3.IntegrityError, match="nao sao do documento"):
        connection.execute("UPDATE informe_indicators SET document_id = ?", (origin.doc2,))

    connection.execute("UPDATE informe_indicators SET value = '11.5'")
    assert connection.execute("SELECT value FROM informe_indicators").fetchone()[0] == "11.5"


# ------------------------------------------------------------------ ratings

def test_a_rating_from_a_pdf_page_and_one_from_an_xml_path_are_both_stored(tmp_path):
    connection, origin = make_database(tmp_path)

    insert(connection, "ratings", rating_row(origin))
    insert(connection, "ratings", rating_row(
        origin, agency="Outra Agencia", page=None, source_ref="/Informe/Classe/Rating",
    ))

    rows = connection.execute("SELECT page, source_ref, review_status, reviewed_at FROM ratings ORDER BY rating_id").fetchall()
    assert [tuple(row) for row in rows] == [
        (3, None, "pending_review", None),
        (None, "/Informe/Classe/Rating", "pending_review", None),
    ]


BAD_RATING_VALUES = [
    ("asset_id", None), ("asset_id", 999),
    ("agency", None), ("agency", ""), ("agency", "  "),
    ("grade", None), ("grade", ""), ("grade", "  "),
    ("rating_date", None), ("rating_date", "2026-13-01"), ("rating_date", "jul/2026"),
    ("document_id", None), ("document_id", 999), ("version_id", None), ("version_id", 999),
    ("page", 0), ("page", -3),
    ("source_ref", "  "),
    ("quoted_text", None), ("quoted_text", ""), ("quoted_text", "  "),
    ("review_status", None), ("review_status", "approved"),
    ("reviewed_at", "ontem"),
    ("reviewed_at", "2026-10-23T12:00:00+00:00"),
    ("review_status", "verified"),
    ("collected_at", None), ("collected_at", "ontem"),
    ("parser_version", None), ("parser_version", ""),
    ("run_id", None), ("run_id", "run-que-nao-existe"),
]


@pytest.mark.parametrize(("column", "value"), BAD_RATING_VALUES)
def test_schema_refuses_a_rating_without_origin_place_or_valid_content(tmp_path, column, value):
    connection, origin = make_database(tmp_path)
    insert(connection, "ratings", rating_row(origin))
    connection.execute("DELETE FROM ratings")

    with pytest.raises(sqlite3.IntegrityError):
        insert(connection, "ratings", rating_row(origin, **{column: value}))


def test_an_unknown_review_status_is_refused_even_with_a_review_date(tmp_path):
    # Com a data preenchida a regra que casa status e data passa; so a lista de status barra.
    connection, origin = make_database(tmp_path)

    with pytest.raises(sqlite3.IntegrityError):
        insert(connection, "ratings", rating_row(
            origin, review_status="approved", reviewed_at="2026-10-23T12:00:00+00:00",
        ))


def test_a_rating_must_point_to_a_page_or_to_a_path(tmp_path):
    connection, origin = make_database(tmp_path)

    with pytest.raises(sqlite3.IntegrityError):
        insert(connection, "ratings", rating_row(origin, page=None, source_ref=None))


def test_review_status_and_review_date_go_together(tmp_path):
    connection, origin = make_database(tmp_path)

    insert(connection, "ratings", rating_row(
        origin, grade="N1", review_status="verified", reviewed_at="2026-10-23T12:00:00+00:00",
    ))
    insert(connection, "ratings", rating_row(
        origin, grade="N2", review_status="rejected", reviewed_at="2026-10-23T12:00:00+00:00",
    ))

    assert connection.execute("SELECT COUNT(*) FROM ratings").fetchone()[0] == 2


def test_the_same_rating_of_the_same_file_cannot_repeat(tmp_path):
    connection, origin = make_database(tmp_path)
    insert(connection, "ratings", rating_row(origin))

    with pytest.raises(sqlite3.IntegrityError):
        insert(connection, "ratings", rating_row(origin, page=7))

    other_version = insert_version(connection, origin.doc1, "c" * 64)
    insert(connection, "ratings", rating_row(origin, version_id=other_version))


@pytest.mark.parametrize(
    "overrides",
    [{"version_id": "ver2"}, {"asset_id": "asset2"}, {"document_id": "doc2"}],
)
def test_a_rating_whose_version_or_asset_is_not_of_the_document_is_refused(tmp_path, overrides):
    connection, origin = make_database(tmp_path)
    resolved = {key: getattr(origin, value) for key, value in overrides.items()}

    with pytest.raises(sqlite3.IntegrityError, match="nao sao do documento"):
        insert(connection, "ratings", rating_row(origin, **resolved))


def test_a_rating_cannot_be_moved_to_another_document(tmp_path):
    connection, origin = make_database(tmp_path)
    insert(connection, "ratings", rating_row(origin))

    with pytest.raises(sqlite3.IntegrityError, match="nao sao do documento"):
        connection.execute("UPDATE ratings SET document_id = ?, version_id = ?", (origin.doc2, origin.ver1))


def test_the_view_for_the_ficha_only_shows_verified_ratings(tmp_path):
    connection, origin = make_database(tmp_path)
    stamp = "2026-10-23T12:00:00+00:00"
    insert(connection, "ratings", rating_row(origin, grade="PENDENTE"))
    insert(connection, "ratings", rating_row(origin, grade="VERIFICADA", review_status="verified", reviewed_at=stamp))
    insert(connection, "ratings", rating_row(origin, grade="REJEITADA", review_status="rejected", reviewed_at=stamp))

    assert [row[0] for row in connection.execute("SELECT grade FROM ratings_verified")] == ["VERIFICADA"]
    assert connection.execute("SELECT COUNT(*) FROM ratings").fetchone()[0] == 3
