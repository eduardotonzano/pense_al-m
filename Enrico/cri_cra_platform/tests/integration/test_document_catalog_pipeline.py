import json
from pathlib import Path
import runpy


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
    second = namespace["run"](
        offline=True,
        database_path=tmp_path / "catalog.db",
        config_path=config,
        output_path=tmp_path / "catalog.csv",
        report_path=tmp_path / "report.json",
    )
    assert first["after_documents"] == 4
    assert second["after_documents"] == first["after_documents"]
    assert (tmp_path / "catalog.csv").exists()
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["errors"] == 0
