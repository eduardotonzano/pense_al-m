from __future__ import annotations

import csv
import runpy
import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest

from credit_assets.database.connection import connect, initialize_database
from credit_assets.models.asset import Asset
from credit_assets.repositories.asset_repository import AssetRepository


def make_asset(
    codigo_cetip: str,
    isin: str,
    *,
    serie: str = "1",
    emissao: str = "190",
) -> Asset:
    return Asset(
        codigo_cetip,
        "CRA",
        "Securitizadora",
        "10.753.164/0001-43",
        emissao,
        serie,
        "Devedor",
        "01.486.546/0001-67",
        isin,
    )


def without_cnpj(asset: Asset) -> Asset:
    return replace(asset, cnpj_securitizadora="", cnpj_devedor="")


def stored_cnpjs(connection, asset_id: int) -> tuple:
    row = connection.execute(
        "SELECT cnpj_securitizadora, cnpj_devedor FROM assets WHERE asset_id = ?",
        (asset_id,),
    ).fetchone()
    return tuple(row)


def test_pilot_config_keeps_cetip_and_isin_separate_with_canonical_series():
    config_path = Path(__file__).parents[2] / "config" / "ativos_piloto.csv"
    with config_path.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    cafe = next(row for row in rows if row["isin"] == "BRECOACRABX0")

    assert cafe["codigo_cetip"] == "CRA022009VM"
    assert cafe["isin"] == "BRECOACRABX0"
    assert cafe["emissao"] == "190"
    assert cafe["serie"] == "1"


def test_upsert_finds_existing_asset_by_isin_and_normalizes_identifiers(tmp_path):
    connection = connect(tmp_path / "assets.db")
    initialize_database(connection)
    repository = AssetRepository(connection)
    original_id = repository.upsert(make_asset("CRA022009VM", "BRECOACRABX0"))

    found_id = repository.upsert(
        make_asset(" cra022009vm ", " brecoacrabx0\u200b ", serie="única")
    )

    row = connection.execute(
        "SELECT codigo_cetip, isin, serie FROM assets WHERE asset_id = ?",
        (original_id,),
    ).fetchone()
    assert found_id == original_id
    assert tuple(row) == ("CRA022009VM", "BRECOACRABX0", "1")
    assert connection.execute("SELECT COUNT(*) FROM assets").fetchone()[0] == 1


def test_upsert_finds_existing_asset_by_cetip_without_isin(tmp_path):
    connection = connect(tmp_path / "assets.db")
    initialize_database(connection)
    repository = AssetRepository(connection)
    original_id = repository.upsert(make_asset("CRA022009VM", ""))

    found_id = repository.upsert(make_asset(" cra022009vm ", ""))

    assert found_id == original_id
    assert connection.execute("SELECT COUNT(*) FROM assets").fetchone()[0] == 1


def test_conflicting_isin_and_cetip_are_rejected(tmp_path):
    connection = connect(tmp_path / "assets.db")
    initialize_database(connection)
    repository = AssetRepository(connection)
    repository.upsert(make_asset("CRA022009VM", "BRECOACRABX0"))
    repository.upsert(make_asset("OTHER-CETIP", "BRRBRACRIP13", emissao="301"))

    with pytest.raises(ValueError, match="Conflito de identidade"):
        repository.upsert(make_asset("CRA022009VM", "BRRBRACRIP13"))

    assert connection.execute("SELECT COUNT(*) FROM assets").fetchone()[0] == 2


def test_empty_identifiers_do_not_match_each_other_or_create_duplicate_assets(tmp_path):
    connection = connect(tmp_path / "assets.db")
    initialize_database(connection)
    repository = AssetRepository(connection)

    first_id = repository.upsert(make_asset("", "BRECOACRABX0"))
    second_id = repository.upsert(make_asset("", "BRRBRACRIP13", emissao="301"))

    assert first_id != second_id
    assert connection.execute(
        "SELECT COUNT(*) FROM assets WHERE codigo_cetip IS NULL"
    ).fetchone()[0] == 2
    assert connection.execute("SELECT COUNT(*) FROM assets").fetchone()[0] == 2


def test_isin_cannot_be_used_as_codigo_cetip(tmp_path):
    connection = connect(tmp_path / "assets.db")
    initialize_database(connection)

    with pytest.raises(ValueError, match="não pode ser igual ao ISIN"):
        AssetRepository(connection).upsert(
            make_asset("BRECOACRABX0", "BRECOACRABX0")
        )

    assert connection.execute("SELECT COUNT(*) FROM assets").fetchone()[0] == 0


def test_partial_indexes_reject_normalized_duplicate_identifiers(tmp_path):
    connection = connect(tmp_path / "assets.db")
    initialize_database(connection)
    repository = AssetRepository(connection)
    repository.upsert(make_asset("CRA022009VM", "BRECOACRABX0"))

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """INSERT INTO assets (
                codigo_cetip, tipo_ativo, securitizadora, cnpj_securitizadora,
                emissao, serie, isin, created_at, updated_at
            ) VALUES (?, 'CRA', 'S', '1', '190', '1', ?, 'now', 'now')""",
            (" cra022009vm ", "BRRBRACRIP13"),
        )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """INSERT INTO assets (
                codigo_cetip, tipo_ativo, securitizadora, cnpj_securitizadora,
                emissao, serie, isin, created_at, updated_at
            ) VALUES (?, 'CRA', 'S', '1', '190', '1', ?, 'now', 'now')""",
            ("OTHER-CETIP", " brecoacrabx0 "),
        )


def test_upsert_with_blank_cnpj_keeps_the_stored_cnpj(tmp_path):
    connection = connect(tmp_path / "assets.db")
    initialize_database(connection)
    repository = AssetRepository(connection)
    asset = make_asset("CRA022009VM", "BRECOACRABX0")
    asset_id = repository.upsert(asset)

    found_id = repository.upsert(without_cnpj(asset))

    assert found_id == asset_id
    assert stored_cnpjs(connection, asset_id) == (
        "10.753.164/0001-43",
        "01.486.546/0001-67",
    )


def test_upsert_with_a_different_cnpj_still_replaces_the_stored_one(tmp_path):
    connection = connect(tmp_path / "assets.db")
    initialize_database(connection)
    repository = AssetRepository(connection)
    asset = make_asset("CRA022009VM", "BRECOACRABX0")
    asset_id = repository.upsert(asset)

    repository.upsert(
        replace(
            asset,
            cnpj_securitizadora="02.773.542/0001-22",
            cnpj_devedor="82.120.676/0001-83",
        )
    )

    assert stored_cnpjs(connection, asset_id) == (
        "02.773.542/0001-22",
        "82.120.676/0001-83",
    )


def test_upsert_of_a_new_asset_without_cnpj_keeps_the_absence(tmp_path):
    connection = connect(tmp_path / "assets.db")
    initialize_database(connection)
    asset = without_cnpj(make_asset("24G2100031", "BRRBRACRIP13", emissao="301"))

    asset_id = AssetRepository(connection).upsert(asset)

    assert stored_cnpjs(connection, asset_id) == ("", None)


def prepare_foundation(tmp_path):
    project = Path(__file__).parents[2]
    root = tmp_path / "project"
    (root / "config").mkdir(parents=True)
    (root / "reports").mkdir()
    (root / "config" / "ativos_piloto.csv").write_text(
        (project / "config" / "ativos_piloto.csv").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    namespace = {
        "__name__": "test_run_foundation",
        "__file__": str(project / "scripts" / "run_foundation.py"),
    }
    script = (project / "scripts" / "run_foundation.py").read_text(
        encoding="utf-8"
    )
    exec(compile(script, namespace["__file__"], "exec"), namespace)
    namespace["ROOT"] = root
    return namespace, root


def test_foundation_rerun_keeps_a_cnpj_written_after_the_first_run(tmp_path):
    namespace, root = prepare_foundation(tmp_path)
    namespace["main"]()
    # O CSV do piloto traz o Almeida Junior sem CNPJ; este valor entra depois,
    # como o resolvedor da CVM o grava.
    connection = sqlite3.connect(root / "data" / "cri_cra.db")
    connection.execute(
        "UPDATE assets SET cnpj_securitizadora = '02.773.542/0001-22' "
        "WHERE codigo_cetip = '24G2100031'"
    )
    connection.commit()
    connection.close()

    namespace["main"]()

    connection = sqlite3.connect(root / "data" / "cri_cra.db")
    rows = connection.execute(
        "SELECT codigo_cetip, cnpj_securitizadora, cnpj_devedor "
        "FROM assets ORDER BY codigo_cetip"
    ).fetchall()
    connection.close()
    assert rows == [
        ("24G2100031", "02.773.542/0001-22", None),
        ("CRA022009VM", "10.753.164/0001-43", "01.486.546/0001-67"),
    ]


def test_foundation_runs_reuse_assets_without_duplicates(tmp_path):
    namespace, root = prepare_foundation(tmp_path)

    namespace["main"]()
    namespace["main"]()

    connection = sqlite3.connect(root / "data" / "cri_cra.db")
    rows = connection.execute(
        "SELECT codigo_cetip, isin, serie FROM assets ORDER BY codigo_cetip"
    ).fetchall()
    connection.close()
    assert rows == [
        ("24G2100031", "BRRBRACRIP13", "1"),
        ("CRA022009VM", "BRECOACRABX0", "1"),
    ]
