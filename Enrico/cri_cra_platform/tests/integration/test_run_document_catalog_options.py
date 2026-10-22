from __future__ import annotations

import json
import runpy
import sqlite3
from pathlib import Path
from types import SimpleNamespace

from credit_assets.collectors.fundosnet_collector import FundosNetCollector
from credit_assets.database.backup import file_sha256


PROJECT = Path(__file__).parents[2]
THIRD_ASSET = (
    "CRA0TEST001,BRTSTCRA0017,Outra Securitizadora S.A.,00.000.000/0001-00,"
    "12,1,CRA,Devedor Teste,,true\n"
)


def load_script():
    return runpy.run_path(str(PROJECT / "scripts" / "run_document_catalog.py"))


def write_config(tmp_path: Path, extra: str = "") -> Path:
    config = tmp_path / "ativos.csv"
    content = (PROJECT / "config" / "ativos_piloto.csv").read_text(encoding="utf-8")
    config.write_text(content.rstrip("\n") + "\n" + extra, encoding="utf-8")
    return config


def paths(tmp_path: Path, config: Path) -> dict:
    return {
        "database_path": tmp_path / "catalog.db",
        "config_path": config,
        "output_path": tmp_path / "catalog.csv",
        "report_path": tmp_path / "report.json",
    }


def test_load_assets_is_not_limited_to_two_isins(tmp_path):
    namespace = load_script()
    config = write_config(tmp_path, THIRD_ASSET)

    assets = namespace["load_assets"](config)

    assert [asset.isin for asset in assets] == [
        "BRECOACRABX0",
        "BRRBRACRIP13",
        "BRTSTCRA0017",
    ]


def test_load_assets_only_matches_cetip_or_isin_ignoring_case(tmp_path):
    namespace = load_script()
    config = write_config(tmp_path, THIRD_ASSET)

    by_cetip = namespace["load_assets"](config, "cra0test001")
    by_isin = namespace["load_assets"](config, " brtstcra0017 ")
    nothing = namespace["load_assets"](config, "NAO-EXISTE")

    assert [asset.codigo_cetip for asset in by_cetip] == ["CRA0TEST001"]
    assert [asset.codigo_cetip for asset in by_isin] == ["CRA0TEST001"]
    assert nothing == []


def test_real_run_keeps_the_raw_grid_row(tmp_path):
    namespace = load_script()
    config = write_config(tmp_path)

    namespace["run"](offline=True, **paths(tmp_path, config))

    connection = sqlite3.connect(tmp_path / "catalog.db")
    raw = connection.execute(
        "SELECT source_row_json FROM documents WHERE source_document_id = 'cafe-001'"
    ).fetchone()[0]
    connection.close()
    assert json.loads(raw)["tipo"] == "Informe Mensal de CRI"


def test_dry_run_without_a_database_creates_nothing(tmp_path):
    namespace = load_script()
    config = write_config(tmp_path)
    before = {item.name for item in tmp_path.iterdir()}

    result = namespace["run"](offline=True, dry_run=True, **paths(tmp_path, config))

    assert result["dry_run"] is True
    assert result["database_existe"] is False
    assert {item.name for item in tmp_path.iterdir()} == before
    assert [asset["documentos_novos"] for asset in result["assets"]] == [2, 2]
    assert result["errors"] == 0


def test_dry_run_leaves_an_existing_database_and_outputs_untouched(tmp_path):
    namespace = load_script()
    config = write_config(tmp_path)
    arguments = paths(tmp_path, config)
    namespace["run"](offline=True, **arguments)
    watched = [
        arguments["database_path"],
        arguments["output_path"],
        arguments["report_path"],
        tmp_path / "document_catalog_runs.json",
    ]
    assert all(item.is_file() for item in watched)
    before = [file_sha256(item) for item in watched]

    result = namespace["run"](offline=True, dry_run=True, **arguments)

    assert [file_sha256(item) for item in watched] == before
    assert result["database_existe"] is True
    assert [asset["documentos_novos"] for asset in result["assets"]] == [0, 0]
    assert [asset["documentos_existentes"] for asset in result["assets"]] == [2, 2]


def test_dry_run_reports_new_documents_keys_and_grid_fields(tmp_path, monkeypatch):
    namespace = load_script()
    config = write_config(tmp_path)
    arguments = paths(tmp_path, config)
    namespace["run"](offline=True, **arguments)

    def collect_with_metrics(_self, asset, run_id):
        rows = [
            {"id": "cafe-001", "tipoDocumento": "Informe Mensal de CRI", "url": "https://x/1"},
            {
                "id": "cafe-999",
                "tipoDocumento": "Informe Mensal de CRA",
                "categoriaDocumento": "Informes Periódicos",
                "especieDocumento": "",
                "versao": 2,
                "url": "https://x/999",
            },
        ]
        return SimpleNamespace(
            documents=[
                FundosNetCollector._to_document(asset, row, run_id) for row in rows
            ],
            administrator_id=1300,
            id_fundo=8795,
            total_reported=2,
            pages_queried=1,
            rejected=[],
            errors=[],
        )

    monkeypatch.setattr(FundosNetCollector, "collect_with_metrics", collect_with_metrics)

    result = namespace["run"](dry_run=True, only="BRECOACRABX0", **arguments)

    entry = result["assets"][0]
    assert entry["documentos_novos"] == 1
    assert entry["documentos_existentes"] == 1
    assert entry["chaves_json_vistas"]["tipoDocumento"] == 2
    assert entry["chaves_json_vistas"]["versao"] == 1
    assert entry["campos_da_grade_preenchidos"]["source_type"] == 2
    assert entry["campos_da_grade_preenchidos"]["source_category"] == 1
    assert entry["campos_da_grade_preenchidos"]["source_species"] == 0
    assert len(entry["exemplos"]) == 2
    assert len(result["assets"]) == 1


def test_main_returns_one_when_an_asset_fails_and_zero_otherwise(tmp_path, monkeypatch):
    namespace = load_script()
    config = write_config(tmp_path)

    def command(*extra: str) -> list[str]:
        return [
            "--database-path", str(tmp_path / "catalog.db"),
            "--config-path", str(config),
            "--output-path", str(tmp_path / "catalog.csv"),
            "--report-path", str(tmp_path / "report.json"),
            *extra,
        ]

    assert namespace["main"](command("--offline-fixtures")) == 0
    assert namespace["main"](command("--offline-fixtures", "--dry-run")) == 0

    def collect_with_metrics(_self, asset, run_id):
        return SimpleNamespace(
            documents=[],
            administrator_id=None,
            id_fundo=None,
            total_reported=0,
            pages_queried=0,
            rejected=[],
            errors=["falha simulada"],
        )

    monkeypatch.setattr(FundosNetCollector, "collect_with_metrics", collect_with_metrics)

    assert namespace["main"](command()) == 1
    assert namespace["main"](command("--dry-run")) == 1
