import csv
import json
from pathlib import Path

import pytest

from debenture_search.database import Database
from debenture_search.services.debenture_export_service import (
    DebentureExportService,
)
from debenture_search.services.snd_import_service import SndImportService


PROJECT_DIR = Path(__file__).resolve().parent.parent
MIGRATION_PATH = PROJECT_DIR / "migrations" / "001_initial_schema.sql"
FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "snd_caracteristicas_exemplo.html"
)


@pytest.fixture
def context(tmp_path):
    db = Database(tmp_path / "export_identity.db")
    with db.connection() as connection:
        connection.executescript(MIGRATION_PATH.read_text(encoding="utf-8"))
        connection.commit()

    return {
        "db": db,
        "importer": SndImportService(db),
        "export": DebentureExportService(db),
        "html": FIXTURE_PATH.read_text(encoding="utf-8"),
    }


def test_csv_and_json_keep_default_columns(context, tmp_path):
    context["importer"].import_html(
        context["html"],
        observed_at="2026-09-10T12:00:00+00:00",
    )

    csv_result = context["export"].export("csv", tmp_path / "all.csv")
    json_result = context["export"].export("json", tmp_path / "all.json")

    with csv_result["path"].open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)
        header = reader.fieldnames
    data = json.loads(json_result["path"].read_text(encoding="utf-8"))

    assert header == DebentureExportService.DEFAULT_FIELDS
    assert list(data[0]) == DebentureExportService.DEFAULT_FIELDS
    # Campos de identificacao gravados como observacoes (D-08) nao viram coluna.
    for name in ("codigo_ativo", "emissor", "cnpj_emissor"):
        assert name not in header
    assert rows[0]["isin"] == "BREXMPDBS001"
