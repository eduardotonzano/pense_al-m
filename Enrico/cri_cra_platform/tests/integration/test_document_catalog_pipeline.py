import json
import sqlite3
from pathlib import Path
import runpy
from types import SimpleNamespace

from credit_assets.collectors.fundosnet_collector import FundosNetCollector


def test_catalog_pipeline_fixture_is_idempotent(tmp_path, monkeypatch):
    project = Path(__file__).parents[2]
    namespace = runpy.run_path(str(project / "scripts" / "run_document_catalog.py"))
    config = tmp_path / "ativos.csv"
    config.write_text(
        (project / "config" / "ativos_piloto.csv").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    first = namespace["run"](
        offline=True,
        database_path=tmp_path / "catalog.db",
        config_path=config,
        output_path=tmp_path / "catalog.csv",
        report_path=tmp_path / "report.json",
    )
    connection = sqlite3.connect(tmp_path / "catalog.db")
    assert connection.execute(
        "SELECT COUNT(*) FROM documents WHERE run_id = ?",
        (first["run_id"],),
    ).fetchone()[0] == 4
    second = namespace["run"](
        offline=True,
        database_path=tmp_path / "catalog.db",
        config_path=config,
        output_path=tmp_path / "catalog.csv",
        report_path=tmp_path / "report.json",
    )
    assert first["after_documents"] == 4
    assert second["after_documents"] == first["after_documents"]
    assert first["run_id"] != second["run_id"]
    assert (tmp_path / "catalog.csv").exists()
    asset_ids = dict(
        connection.execute(
            "SELECT codigo_cetip, asset_id FROM assets"
        ).fetchall()
    )
    assert asset_ids["CRA022009VM"] == 1
    assert connection.execute(
        "SELECT COUNT(*) FROM documents WHERE asset_id = ?",
        (asset_ids["CRA022009VM"],),
    ).fetchone()[0] == 2
    assert connection.execute(
        "SELECT COUNT(*) FROM assets WHERE codigo_cetip = 'CRA022009VM'"
    ).fetchone()[0] == 1
    first_run_rows = connection.execute(
        "SELECT run_id FROM documents WHERE run_id = ?",
        (first["run_id"],),
    ).fetchall()
    second_run_rows = connection.execute(
        "SELECT run_id FROM documents WHERE run_id = ?",
        (second["run_id"],),
    ).fetchall()
    assert len(first_run_rows) == 0
    assert len(second_run_rows) == 4
    assert connection.execute(
        "SELECT COUNT(*) FROM executions WHERE run_id IN (?, ?)",
        (first["run_id"], second["run_id"]),
    ).fetchone()[0] == 2
    assert connection.execute(
        """SELECT COUNT(*) FROM documents d
           LEFT JOIN executions e ON e.run_id = d.run_id
           WHERE e.run_id IS NULL"""
    ).fetchone()[0] == 0
    connection.close()
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["errors"] == 0
    assert report["run_id"] == second["run_id"]


def test_catalog_partial_failure_keeps_run_id_and_processes_remaining_assets(
    tmp_path, monkeypatch
):
    project = Path(__file__).parents[2]
    namespace = runpy.run_path(str(project / "scripts" / "run_document_catalog.py"))
    config = tmp_path / "ativos.csv"
    config.write_text(
        (project / "config" / "ativos_piloto.csv").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    def collect_with_metrics(_self, asset, run_id):
        if asset.isin == "BRECOACRABX0":
            return SimpleNamespace(
                documents=[],
                administrator_id=None,
                id_fundo=None,
                total_reported=0,
                pages_queried=0,
                rejected=[],
                errors=["simulated collection failure"],
            )
        document = FundosNetCollector._to_document(
            asset,
            {
                "id": "almeida-fixture",
                "tipo": "Informe Mensal de CRI",
                "nome": "Informe",
                "url": "https://fnet.example/almeida/fixture",
            },
            run_id,
        )
        return SimpleNamespace(
            documents=[document],
            administrator_id=1338,
            id_fundo=13003,
            total_reported=1,
            pages_queried=1,
            rejected=[],
            errors=[],
        )

    monkeypatch.setattr(
        FundosNetCollector, "collect_with_metrics", collect_with_metrics
    )
    result = namespace["run"](
        database_path=tmp_path / "partial.db",
        config_path=config,
        output_path=tmp_path / "partial.csv",
        report_path=tmp_path / "partial.json",
    )

    assert result["errors"] == 1
    assert len(result["assets"]) == 2
    assert all(item["run_id"] == result["run_id"] for item in result["assets"])
    assert result["assets"][0]["erros"] == ["simulated collection failure"]
    report = json.loads(
        (tmp_path / "partial.json").read_text(encoding="utf-8")
    )
    assert report["run_id"] == result["run_id"]
    assert report["errors"] == 1
    assert report["assets"][0]["run_id"] == result["run_id"]
    connection = sqlite3.connect(tmp_path / "partial.db")
    execution = connection.execute(
        "SELECT status, error_count FROM executions WHERE run_id = ?",
        (result["run_id"],),
    ).fetchone()
    assert execution == ("partial", 1)
    document_run_ids = connection.execute(
        "SELECT DISTINCT run_id FROM documents"
    ).fetchall()
    assert document_run_ids == [(result["run_id"],)]
    assert connection.execute(
        "SELECT COUNT(*) FROM documents WHERE run_id = ?",
        (result["run_id"],),
    ).fetchone()[0] == 1
    connection.close()
