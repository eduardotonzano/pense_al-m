from __future__ import annotations

import io
import sqlite3
import zipfile

import pytest

from credit_assets.cvm_open_data import connect, create_views, load_zip, plan, zip_url

GERAL = (
    "CNPJ_Emissora;Codigo_Identificacao_Certificado;Data_Referencia;Versao;Data_Entrega;Numero_Emissao\r\n"
    "10.753.164/0001-43;CRA1;2026-01-01;1;2026-02-10;426\r\n"
    "10.753.164/0001-43;CRA1;2026-01-01;2;2026-02-20;426\r\n"
    "10.753.164/0001-43;CRA1;2026-02-01;1;2026-03-10;426\r\n"
)
CLASSE = (
    "CNPJ_Emissora;Codigo_Identificacao_Certificado;Data_Referencia;Versao;Numero_Serie;Codigo_ISIN;Data_Vencimento\r\n"
    "10.753.164/0001-43;CRA1;2026-01-01;1;1;BRECOACRALJ8;2029-07-16\r\n"
    "10.753.164/0001-43;CRA1;2026-01-01;2;1;BRECOACRALJ8;2030-12-18\r\n"
)


def _zip(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content.encode("latin-1"))
    return buffer.getvalue()


@pytest.fixture
def connection(tmp_path):
    return connect(tmp_path / "cvm.db")


def _payload(**overrides):
    files = {"inf_mensal_cra_geral_2026.csv": GERAL, "inf_mensal_cra_classe_2026.csv": CLASSE}
    files.update(overrides)
    return _zip(files)


def test_load_preserves_values_and_provenance(connection):
    result = load_zip(connection, "CRA", 2026, zip_url("CRA", 2026), _payload())
    assert result["status"] == "loaded" and result["rows"] == 5 and result["tables"] == 2
    row = connection.execute("SELECT * FROM cra_classe WHERE Versao = '1'").fetchone()
    assert row["Data_Vencimento"] == "2029-07-16" and row["Codigo_ISIN"] == "BRECOACRALJ8"
    source = connection.execute("SELECT * FROM source_files").fetchone()
    assert source["url"].endswith("inf_mensal_cra_2026.zip") and len(source["sha256"]) == 64


def test_reload_is_idempotent(connection):
    payload = _payload()
    load_zip(connection, "CRA", 2026, "u", payload)
    assert load_zip(connection, "CRA", 2026, "u", payload)["status"] == "skipped"
    assert connection.execute("SELECT COUNT(*) FROM cra_geral").fetchone()[0] == 3
    assert connection.execute("SELECT COUNT(*) FROM source_files").fetchone()[0] == 1


def test_new_file_supersedes_old_without_deleting_history(connection):
    load_zip(connection, "CRA", 2026, "u", _payload())
    newer = GERAL + "10.753.164/0001-43;CRA1;2026-03-01;1;2026-04-10;426\r\n"
    assert load_zip(connection, "CRA", 2026, "u", _payload(**{"inf_mensal_cra_geral_2026.csv": newer}))["status"] == "loaded"
    current = [r[0] for r in connection.execute("SELECT is_current FROM source_files ORDER BY file_id")]
    assert current == [0, 1]
    assert connection.execute("SELECT COUNT(*) FROM cra_geral").fetchone()[0] == 7  # histórico preservado
    create_views(connection)
    assert connection.execute("SELECT COUNT(*) FROM cra_geral_vigente").fetchone()[0] == 3  # só o arquivo vigente


def test_view_picks_highest_version(connection):
    load_zip(connection, "CRA", 2026, "u", _payload())
    create_views(connection)
    row = connection.execute(
        "SELECT Versao FROM cra_geral_vigente WHERE Data_Referencia = '2026-01-01'"
    ).fetchone()
    assert row["Versao"] == "2"
    vencimento = connection.execute("SELECT Data_Vencimento FROM cra_classe_vigente").fetchone()[0]
    assert vencimento == "2030-12-18"


def test_schema_drift_adds_columns_only(connection):
    load_zip(connection, "CRA", 2025, "u", _zip({"inf_mensal_cra_geral_2025.csv": GERAL}))
    wider = GERAL.replace("Numero_Emissao", "Numero_Emissao;Coluna_Nova").replace("426\r\n", "426;x\r\n")
    load_zip(connection, "CRA", 2026, "u", _zip({"inf_mensal_cra_geral_2026.csv": wider}))
    columns = [r[1] for r in connection.execute("PRAGMA table_info(cra_geral)")]
    assert "Coluna_Nova" in columns
    old = connection.execute("SELECT Coluna_Nova FROM cra_geral WHERE _file_id = 1 LIMIT 1").fetchone()[0]
    assert old is None


def test_failure_rolls_back_everything(connection):
    bad = _zip({"inf_mensal_cra_geral_2026.csv": GERAL, "inf_mensal_cra_classe_2026.csv": "col inválida;x\r\na;b\r\n"})
    with pytest.raises(ValueError):
        load_zip(connection, "CRA", 2026, "u", bad)
    assert connection.execute("SELECT COUNT(*) FROM source_files").fetchone()[0] == 0
    assert not connection.execute("SELECT name FROM sqlite_master WHERE name = 'cra_geral'").fetchone() or \
        connection.execute("SELECT COUNT(*) FROM cra_geral").fetchone()[0] == 0


def test_zip_without_expected_csv_is_refused(connection):
    with pytest.raises(ValueError, match="sem CSV"):
        load_zip(connection, "CRI", 2026, "u", _zip({"leiame.txt": "x"}))


def test_plan_builds_urls_for_each_kind_and_year():
    files = plan(["CRA", "CRI"], [2025, 2026], lambda url: 123)
    assert [(f.kind, f.year) for f in files] == [("CRA", 2025), ("CRA", 2026), ("CRI", 2025), ("CRI", 2026)]
    assert files[0].url.endswith("INF_MENSAL_CRA/DADOS/inf_mensal_cra_2025.zip")
