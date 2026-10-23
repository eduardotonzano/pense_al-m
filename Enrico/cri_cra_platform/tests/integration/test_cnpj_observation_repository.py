from __future__ import annotations

import json
import sqlite3
from dataclasses import replace
from datetime import datetime

import pytest

from credit_assets.database.connection import connect, initialize_database
from credit_assets.database.migrations import read_applied_versions
from credit_assets.models.asset import Asset
from credit_assets.repositories.asset_repository import AssetRepository
from credit_assets.repositories.cnpj_observation_repository import (
    CnpjObservation,
    CnpjObservationRepository,
)

OPEA = "02773542000122"
ALMEIDA_DEVEDOR = "82120676000183"
ZIP_SHA = "ab" * 32


def make_database(tmp_path):
    connection = connect(tmp_path / "cri_cra.db")
    initialize_database(connection)
    asset_id = AssetRepository(connection).upsert(
        Asset("24G2100031", "CRI", "Opea Securitizadora S.A.", "", "301", "1",
              "Almeida Junior", "", "BRRBRACRIP13")
    )
    for run_id in ("run-1", "run-2", "run-3"):
        connection.execute(
            "INSERT INTO executions (run_id, started_at, status) "
            "VALUES (?, '2026-10-23T00:00:00+00:00', 'success')",
            (run_id,),
        )
    connection.commit()
    return connection, asset_id


def make_observation(asset_id: int, **overrides) -> CnpjObservation:
    values = dict(
        asset_id=asset_id,
        field="cnpj_securitizadora",
        cnpj=OPEA,
        decision="applied",
        source_id="cvm_inf_mensal_cri",
        matched_by="isin+codigo_cetip",
        reference_first="2025-01-01",
        reference_last="2026-08-01",
        filings=20,
        evidence={"files": [{
            "name": "inf_mensal_cri_2026.zip",
            "url": "https://dados.cvm.gov.br/dados/SECURIT/DOC/INF_MENSAL_CRI/DADOS/inf_mensal_cri_2026.zip",
            "sha256": ZIP_SHA,
            "rows": 8,
        }]},
        delivered_last="2026-09-10",
    )
    values.update(overrides)
    return CnpjObservation(**values)


def set_asset_cnpj(connection, asset_id: int, column: str, value: str | None) -> None:
    connection.execute(
        f"UPDATE assets SET {column} = ? WHERE asset_id = ?", (value, asset_id)
    )


def test_new_database_gets_the_observation_table_view_and_migration_002(tmp_path):
    connection, _ = make_database(tmp_path)

    names = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE name LIKE 'asset_cnpj_%'"
        )
    }

    assert read_applied_versions(connection) == {
        1: "document_catalog",
        2: "asset_cnpj_observations",
    }
    assert {"asset_cnpj_observations", "asset_cnpj_provenance"} <= names


def test_add_stores_the_cnpj_with_source_period_and_read_time(tmp_path):
    connection, asset_id = make_database(tmp_path)
    repository = CnpjObservationRepository(connection)

    assert repository.add(make_observation(asset_id), "run-1") is True

    row = repository.for_asset(asset_id)[0]
    assert (row["field"], row["cnpj"], row["decision"]) == (
        "cnpj_securitizadora", OPEA, "applied",
    )
    assert (row["source_id"], row["matched_by"]) == ("cvm_inf_mensal_cri", "isin+codigo_cetip")
    assert (row["reference_first"], row["reference_last"], row["filings"]) == (
        "2025-01-01", "2026-08-01", 20,
    )
    assert row["delivered_last"] == "2026-09-10"
    assert json.loads(row["evidence_json"])["files"][0]["sha256"] == ZIP_SHA
    assert datetime.fromisoformat(row["observed_at"]).tzinfo is not None
    assert row["run_id"] == "run-1"


def test_reading_the_same_evidence_again_does_not_add_a_row(tmp_path):
    connection, asset_id = make_database(tmp_path)
    repository = CnpjObservationRepository(connection)
    repository.add(make_observation(asset_id), "run-1")

    again = repository.add(make_observation(asset_id), "run-2")
    confirmed = repository.add(make_observation(asset_id, decision="confirmed"), "run-2")

    assert (again, confirmed) == (False, False)
    assert len(repository.for_asset(asset_id)) == 1


def test_a_new_snapshot_or_a_new_decision_is_a_new_row(tmp_path):
    connection, asset_id = make_database(tmp_path)
    repository = CnpjObservationRepository(connection)
    repository.add(make_observation(asset_id), "run-1")
    new_snapshot = make_observation(
        asset_id,
        evidence={"files": [{"name": "inf_mensal_cri_2026.zip", "sha256": "cd" * 32}]},
    )
    candidate = make_observation(
        asset_id, field="cnpj_devedor", cnpj=ALMEIDA_DEVEDOR, decision="candidate"
    )
    applied = replace(candidate, decision="applied")

    results = [
        repository.add(new_snapshot, "run-2"),
        repository.add(candidate, "run-2"),
        repository.add(applied, "run-3"),
    ]

    assert results == [True, True, True]
    assert [row["decision"] for row in repository.for_asset(asset_id)] == [
        "applied", "applied", "candidate", "applied",
    ]


BAD_VALUES = [
    ("source_id", None),
    ("source_id", "manual"),
    ("source_id", "nome_da_securitizadora"),
    ("matched_by", "nome"),
    ("reference_first", None),
    ("reference_first", "2026-02-30"),
    ("reference_first", "ago/2026"),
    ("reference_last", "2024-12-31"),
    ("reference_last", "set/2026"),
    ("delivered_last", "10/09/2026"),
    ("cnpj", "0277354200012"),
    ("cnpj", "02.773.542/0001-22"),
    ("cnpj", "0277354200012A"),
    ("decision", "guess"),
    ("field", "securitizadora"),
    ("filings", 0),
    ("evidence_json", None),
    ("observed_at", None),
    ("observed_at", "ontem"),
    ("run_id", "run-que-nao-existe"),
    ("asset_id", 999),
    ("checksum", "nao-e-um-hash"),
]


@pytest.mark.parametrize(("column", "value"), BAD_VALUES)
def test_schema_refuses_an_observation_without_source_dates_or_a_valid_cnpj(
    tmp_path, column, value
):
    connection, asset_id = make_database(tmp_path)
    good = {
        "asset_id": asset_id,
        "field": "cnpj_securitizadora",
        "cnpj": OPEA,
        "decision": "applied",
        "source_id": "cvm_inf_mensal_cri",
        "matched_by": "isin",
        "reference_first": "2025-01-01",
        "reference_last": "2026-08-01",
        "filings": 20,
        "delivered_last": "2026-09-10",
        "evidence_json": "{}",
        "observed_at": "2026-10-23T12:00:00+00:00",
        "run_id": "run-1",
        "checksum": "0" * 64,
    }
    connection.execute(
        f"INSERT INTO asset_cnpj_observations ({', '.join(good)}) "
        f"VALUES ({', '.join('?' * len(good))})",
        tuple(good.values()),
    )
    connection.execute("DELETE FROM asset_cnpj_observations")
    bad = {**good, column: value}

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            f"INSERT INTO asset_cnpj_observations ({', '.join(bad)}) "
            f"VALUES ({', '.join('?' * len(bad))})",
            tuple(bad.values()),
        )


def test_provenance_gives_source_and_date_of_the_cnpj_that_is_in_assets(tmp_path):
    connection, asset_id = make_database(tmp_path)
    repository = CnpjObservationRepository(connection)
    set_asset_cnpj(connection, asset_id, "cnpj_securitizadora", "02.773.542/0001-22")
    repository.add(make_observation(asset_id), "run-1", "2026-10-23T12:00:00+00:00")

    row = repository.provenance(asset_id, "cnpj_securitizadora")

    assert (row["cnpj"], row["source_id"], row["decision"]) == (
        OPEA, "cvm_inf_mensal_cri", "applied",
    )
    assert (row["reference_first"], row["reference_last"]) == ("2025-01-01", "2026-08-01")
    assert row["observed_at"] == "2026-10-23T12:00:00+00:00"
    assert repository.provenance(asset_id, "cnpj_devedor") is None


def test_provenance_is_empty_for_a_cnpj_typed_by_hand(tmp_path):
    connection, asset_id = make_database(tmp_path)
    set_asset_cnpj(connection, asset_id, "cnpj_securitizadora", "10.753.164/0001-43")

    assert CnpjObservationRepository(connection).provenance(
        asset_id, "cnpj_securitizadora"
    ) is None


def test_provenance_is_empty_once_assets_holds_another_cnpj(tmp_path):
    connection, asset_id = make_database(tmp_path)
    repository = CnpjObservationRepository(connection)
    set_asset_cnpj(connection, asset_id, "cnpj_securitizadora", "02.773.542/0001-22")
    repository.add(make_observation(asset_id), "run-1")
    set_asset_cnpj(connection, asset_id, "cnpj_securitizadora", "10.753.164/0001-43")

    assert repository.provenance(asset_id, "cnpj_securitizadora") is None


def test_provenance_ignores_candidates_and_conflicts(tmp_path):
    connection, asset_id = make_database(tmp_path)
    repository = CnpjObservationRepository(connection)
    candidate = make_observation(
        asset_id, field="cnpj_devedor", cnpj=ALMEIDA_DEVEDOR, decision="candidate"
    )
    repository.add(candidate, "run-1")
    set_asset_cnpj(connection, asset_id, "cnpj_devedor", "82.120.676/0001-83")

    assert repository.provenance(asset_id, "cnpj_devedor") is None


def test_provenance_picks_the_latest_applied_or_confirmed_observation(tmp_path):
    connection, asset_id = make_database(tmp_path)
    repository = CnpjObservationRepository(connection)
    set_asset_cnpj(connection, asset_id, "cnpj_securitizadora", "02.773.542/0001-22")
    repository.add(make_observation(asset_id), "run-1")
    newer = make_observation(
        asset_id,
        decision="confirmed",
        reference_last="2026-09-01",
        evidence={"files": [{"name": "inf_mensal_cri_2026.zip", "sha256": "cd" * 32}]},
    )
    repository.add(newer, "run-2")

    row = repository.provenance(asset_id, "cnpj_securitizadora")

    assert (row["decision"], row["reference_last"]) == ("confirmed", "2026-09-01")
