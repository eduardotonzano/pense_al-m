from __future__ import annotations

import csv
import importlib.util
import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from credit_assets.collectors.cvm_informe_mensal import archive_url
from credit_assets.database.backup import file_sha256
from credit_assets.database.connection import connect, initialize_database
from credit_assets.models.asset import Asset
from credit_assets.repositories.asset_repository import AssetRepository
from credit_assets.repositories.cnpj_observation_repository import CnpjObservationRepository
from credit_assets.services import cnpj_resolution
from credit_assets.services.category_reclassification import open_read_only
from credit_assets.services.cnpj_resolution import ResolutionError
from tests.cvm_fixtures import (
    ALMEIDA_DEVEDOR,
    ALMEIDA_ISIN,
    CAFE_DEVEDOR_IN_CSV,
    ECO,
    FULL_SHARE,
    OPEA,
    almeida_rows,
    classe_row,
    geral_row,
    party_row,
    write_almeida_zips,
    write_cvm_zip,
    write_eco_zip,
)

PROJECT_DIR = Path(__file__).resolve().parents[2]
SCRIPT_PATH = PROJECT_DIR / "scripts" / "resolve_cnpj.py"
PILOT_CSV = PROJECT_DIR / "config" / "ativos_piloto.csv"
OTHER_ISSUER = "12.130.744/0001-00"
ALMEIDA_ROW = "24G2100031"
ECO_ROW = "CRA022009VM"


def load_script():
    specification = importlib.util.spec_from_file_location("resolve_cnpj_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


@pytest.fixture
def script():
    return load_script()


def pilot_assets() -> list[Asset]:
    """Os dois ativos do ativos_piloto.csv como o run_foundation.py os carrega."""

    with PILOT_CSV.open(encoding="utf-8-sig", newline="") as source:
        return [
            Asset(
                codigo_cetip=row["codigo_cetip"],
                tipo_ativo=row["tipo_ativo"],
                securitizadora=row["securitizadora"],
                cnpj_securitizadora=row["cnpj_securitizadora"],
                emissao=row["emissao"],
                serie=row["serie"],
                devedor=row.get("devedor", ""),
                cnpj_devedor=row.get("cnpj_devedor", ""),
                isin=row.get("isin", ""),
            )
            for row in csv.DictReader(source)
            if row["ativo"].lower() == "true"
        ]


def make_database(tmp_path: Path, *, with_migration_002: bool = True) -> Path:
    path = tmp_path / "cri_cra.db"
    connection = connect(path)

    if with_migration_002:
        initialize_database(connection)
    else:
        empty = tmp_path / "empty_migrations"
        empty.mkdir()
        initialize_database(connection, migrations_dir=empty)

    repository = AssetRepository(connection)

    for asset in pilot_assets():
        repository.upsert(asset)

    connection.commit()
    connection.close()
    return path


def make_cvm_dir(tmp_path: Path) -> Path:
    folder = tmp_path / "cvm"
    write_almeida_zips(folder)
    write_eco_zip(folder)
    return folder


def query(path: Path, sql: str):
    with closing(sqlite3.connect(path)) as connection:
        return connection.execute(sql).fetchall()


def cnpjs(path: Path) -> dict[str, tuple]:
    return {
        row[0]: (row[1], row[2])
        for row in query(
            path,
            "SELECT codigo_cetip, cnpj_securitizadora, cnpj_devedor FROM assets",
        )
    }


def observations(path: Path) -> dict[tuple, tuple]:
    return {
        (row[0], row[1]): row[2:]
        for row in query(
            path,
            """SELECT a.codigo_cetip, o.field, o.decision, o.cnpj, o.reference_first,
                      o.reference_last, o.filings, o.delivered_last, o.matched_by, o.source_id
               FROM asset_cnpj_observations o JOIN assets a USING (asset_id)
               ORDER BY o.observation_id""",
        )
    }


def counts(path: Path) -> dict[str, int]:
    return {
        table: query(path, f"SELECT COUNT(*) FROM {table}")[0][0]
        for table in ("assets", "asset_cnpj_observations", "executions")
    }


def run(script, capsys, path: Path, cvm: Path, mode: str, *extra: str, fetch=None):
    code = script.main(
        ["--database", str(path), mode, "--cvm-dir", str(cvm), *extra], fetch=fetch
    )
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def commit(script, capsys, path, cvm, tmp_path, *extra):
    return run(script, capsys, path, cvm, "--commit", "--backup-dir", str(tmp_path / "b"), *extra)


# ---------------------------------------------------------- nome nunca decide

@pytest.mark.parametrize("issuer", [OPEA, OTHER_ISSUER])
def test_a_cvm_informe_with_the_same_names_but_other_identifiers_gives_no_cnpj(
    script, capsys, tmp_path, issuer
):
    """Outro certificado cuja securitizadora tem o nome do ativo nao empresta CNPJ."""

    path = make_database(tmp_path)
    cvm = tmp_path / "cvm"
    other = "BRZZZZZZZZ19"
    write_cvm_zip(
        cvm / "inf_mensal_cri_2026.zip", "cri", 2026,
        classe=[classe_row(issuer, other, "2026-08-01", cetip="ZZZ9999999", isin=other)],
        geral=[geral_row(
            issuer, other, "2026-08-01", delivered="2026-09-28", emissao="301",
            name="Opea Securitizadora S.A.",
        )],
        parties=[party_row(issuer, other, "2026-08-01", "Devedor", ALMEIDA_DEVEDOR, FULL_SHARE)],
    )
    before = cnpjs(path)

    code, out, _ = commit(script, capsys, path, cvm, tmp_path, "--apply-devedor")

    assert code == 0
    assert cnpjs(path) == before
    assert cnpjs(path)[ALMEIDA_ROW] == ("", None)
    assert query(path, "SELECT COUNT(*) FROM asset_cnpj_observations") == [(0,)]
    assert "sem_fonte" in out
    assert "Nada a gravar" in out
    assert not (tmp_path / "b").exists()


def test_the_identifiers_decide_even_when_every_name_is_different(script, capsys, tmp_path):
    path = make_database(tmp_path)
    cvm = tmp_path / "cvm"

    for year in (2025, 2026):
        classe, geral, parties = almeida_rows(year)
        geral = [{**row, "Companhia_Emissora": "Banco Qualquer S.A."} for row in geral]
        write_cvm_zip(
            cvm / f"inf_mensal_cri_{year}.zip", "cri", year,
            classe=classe, geral=geral, parties=parties,
        )

    code, _, _ = commit(script, capsys, path, cvm, tmp_path, "--only", ALMEIDA_ISIN)

    assert code == 0
    assert cnpjs(path)[ALMEIDA_ROW][0] == OPEA


def test_scrambling_every_name_in_the_cvm_files_changes_nothing_in_the_result(
    script, capsys, tmp_path
):
    results = []

    for label, name in (("real", "Opea Securtizadora"), ("scrambled", "Zyx Qwv 123")):
        folder = tmp_path / label
        folder.mkdir()
        path = make_database(folder)
        cvm = folder / "cvm"

        for year in (2025, 2026):
            classe, geral, parties = almeida_rows(year)
            geral = [{**row, "Companhia_Emissora": name} for row in geral]
            write_cvm_zip(
                cvm / f"inf_mensal_cri_{year}.zip", "cri", year,
                classe=classe, geral=geral, parties=parties,
            )

        report = folder / "report.json"
        code, _, _ = run(
            script, capsys, path, cvm, "--dry-run", "--only", ALMEIDA_ISIN,
            "--report-path", str(report),
        )
        fields = json.loads(report.read_text(encoding="utf-8"))["assets"][0]["fields"]
        results.append({
            field: {
                key: entry["resolution"][key]
                for key in ("status", "cnpj", "reference_first", "reference_last", "filings")
            } | {"decision": entry["decision"]}
            for field, entry in fields.items()
        })
        assert code == 0

    assert results[0] == results[1]
    assert results[0]["cnpj_securitizadora"]["cnpj"] == "02773542000122"


# ------------------------------------------------- sem fonte, ambiguo, invalido

def test_asset_without_a_cvm_file_of_its_type_stays_absent(script, capsys, tmp_path):
    path = make_database(tmp_path)
    cvm = tmp_path / "cvm"
    write_eco_zip(cvm)

    code, out, _ = commit(script, capsys, path, cvm, tmp_path)

    assert code == 0
    assert cnpjs(path)[ALMEIDA_ROW] == ("", None)
    assert "sem_arquivo_da_cvm" in out
    assert (ALMEIDA_ROW, "cnpj_securitizadora") not in observations(path)


def test_isin_with_two_issuers_writes_nothing_and_lists_both(script, capsys, tmp_path):
    path = make_database(tmp_path)
    cvm = tmp_path / "cvm"
    write_cvm_zip(
        cvm / "inf_mensal_cri_2026.zip", "cri", 2026,
        classe=[
            classe_row(OTHER_ISSUER, ALMEIDA_ISIN, "2026-01-01", cetip="24G2100031", isin=ALMEIDA_ISIN),
            classe_row(OPEA, ALMEIDA_ISIN, "2026-02-01", cetip="24G2100031", isin=ALMEIDA_ISIN),
        ],
    )

    code, out, _ = commit(script, capsys, path, cvm, tmp_path)

    assert code == 0
    assert cnpjs(path)[ALMEIDA_ROW] == ("", None)
    assert observations(path) == {}
    assert "conflito" in out and OPEA in out and OTHER_ISSUER in out


def test_invalid_cnpjs_in_the_cvm_file_are_never_written(script, capsys, tmp_path):
    path = make_database(tmp_path)
    cvm = tmp_path / "cvm"
    wrong_digit = "02.773.542/0001-23"
    write_cvm_zip(
        cvm / "inf_mensal_cri_2026.zip", "cri", 2026,
        classe=[classe_row(wrong_digit, ALMEIDA_ISIN, "2026-08-01", cetip="24G2100031", isin=ALMEIDA_ISIN)],
        parties=[party_row(wrong_digit, ALMEIDA_ISIN, "2026-08-01", "Devedor", "011.615.038-62", FULL_SHARE)],
    )

    code, out, _ = commit(script, capsys, path, cvm, tmp_path, "--apply-devedor")

    assert code == 0
    assert cnpjs(path)[ALMEIDA_ROW] == ("", None)
    assert observations(path) == {}
    assert out.count("cnpj_invalido_na_fonte") >= 2


# ------------------------------------------------------------- linhas reais

def test_commit_with_the_real_rows_applies_the_securitizadora_and_keeps_the_devedor_a_candidate(
    script, capsys, tmp_path
):
    path = make_database(tmp_path)
    cvm = make_cvm_dir(tmp_path)

    code, out, _ = commit(script, capsys, path, cvm, tmp_path)
    found = observations(path)

    assert code == 0
    assert cnpjs(path) == {
        ALMEIDA_ROW: (OPEA, None),
        ECO_ROW: (ECO, CAFE_DEVEDOR_IN_CSV),
    }
    assert found[(ALMEIDA_ROW, "cnpj_securitizadora")] == (
        "applied", "02773542000122", "2025-01-01", "2026-08-01", 20, "2026-09-28",
        "isin+codigo_cetip", "cvm_inf_mensal_cri",
    )
    assert found[(ALMEIDA_ROW, "cnpj_devedor")] == (
        "candidate", "82120676000183", "2026-07-01", "2026-08-01", 2, "2026-09-28",
        "isin+codigo_cetip", "cvm_inf_mensal_cri",
    )
    assert found[(ECO_ROW, "cnpj_securitizadora")] == (
        "confirmed", "10753164000143", "2026-01-01", "2026-08-01", 8, "2026-09-25",
        "isin+codigo_cetip", "cvm_inf_mensal_cra",
    )
    assert found[(ECO_ROW, "cnpj_devedor")][:2] == ("conflict", "31943818000171")
    assert len(found) == 4
    assert "Backup:" in out and "Campos gravados em assets: 1" in out


def test_the_conflict_keeps_the_value_that_was_there_and_records_it_as_evidence(
    script, capsys, tmp_path
):
    path = make_database(tmp_path)
    commit(script, capsys, path, make_cvm_dir(tmp_path), tmp_path, "--apply-devedor")

    evidence = query(
        path,
        """SELECT o.evidence_json FROM asset_cnpj_observations o JOIN assets a USING (asset_id)
           WHERE a.codigo_cetip = 'CRA022009VM' AND o.field = 'cnpj_devedor'""",
    )

    assert cnpjs(path)[ECO_ROW][1] == CAFE_DEVEDOR_IN_CSV
    assert json.loads(evidence[0][0])["stored"] == CAFE_DEVEDOR_IN_CSV


def test_apply_devedor_writes_the_devedor_but_still_never_overwrites_an_existing_value(
    script, capsys, tmp_path
):
    path = make_database(tmp_path)
    cvm = make_cvm_dir(tmp_path)
    commit(script, capsys, path, cvm, tmp_path)

    code, out, _ = commit(script, capsys, path, cvm, tmp_path, "--apply-devedor")
    found = observations(path)

    assert code == 0
    assert cnpjs(path) == {
        ALMEIDA_ROW: (OPEA, "82.120.676/0001-83"),
        ECO_ROW: (ECO, CAFE_DEVEDOR_IN_CSV),
    }
    assert found[(ALMEIDA_ROW, "cnpj_devedor")][0] == "applied"
    assert query(
        path,
        """SELECT COUNT(*) FROM asset_cnpj_observations o JOIN assets a USING (asset_id)
           WHERE a.codigo_cetip = '24G2100031' AND o.field = 'cnpj_devedor'""",
    ) == [(2,)]
    assert "Campos gravados em assets: 1" in out and "Observacoes registradas: 1" in out


def test_second_commit_has_nothing_to_write_and_makes_no_backup(script, capsys, tmp_path):
    path = make_database(tmp_path)
    cvm = make_cvm_dir(tmp_path)
    commit(script, capsys, path, cvm, tmp_path)
    before = counts(path)
    backups = sorted((tmp_path / "b").glob("*.sqlite3"))

    code, out, _ = commit(script, capsys, path, cvm, tmp_path)

    assert code == 0
    assert counts(path) == before
    assert sorted((tmp_path / "b").glob("*.sqlite3")) == backups and len(backups) == 1
    assert "Nada a gravar" in out
    assert "(observacao ja registrada)" in out


def test_provenance_view_and_a_catalog_reseed_after_the_commit(script, capsys, tmp_path):
    path = make_database(tmp_path)
    commit(script, capsys, path, make_cvm_dir(tmp_path), tmp_path)

    with closing(connect(path)) as connection:
        for asset in pilot_assets():
            AssetRepository(connection).upsert(asset)

        connection.commit()
        repository = CnpjObservationRepository(connection)
        almeida_id = connection.execute(
            "SELECT asset_id FROM assets WHERE codigo_cetip = '24G2100031'"
        ).fetchone()[0]
        securitizadora = repository.provenance(almeida_id, "cnpj_securitizadora")

        assert cnpjs(path)[ALMEIDA_ROW][0] == OPEA
        assert (securitizadora["source_id"], securitizadora["decision"]) == (
            "cvm_inf_mensal_cri", "applied",
        )
        assert (securitizadora["reference_first"], securitizadora["reference_last"]) == (
            "2025-01-01", "2026-08-01",
        )
        assert securitizadora["observed_at"].endswith("+00:00")
        assert repository.provenance(almeida_id, "cnpj_devedor") is None

    handwritten = query(
        path,
        """SELECT COUNT(*) FROM asset_cnpj_provenance p JOIN assets a USING (asset_id)
           WHERE a.codigo_cetip = 'CRA022009VM' AND p.field = 'cnpj_devedor'""",
    )
    assert handwritten == [(0,)]


def test_every_value_written_by_the_resolver_has_source_period_and_read_time(
    script, capsys, tmp_path
):
    path = make_database(tmp_path)
    commit(script, capsys, path, make_cvm_dir(tmp_path), tmp_path, "--apply-devedor")

    unsourced = query(
        path,
        """SELECT a.codigo_cetip, f.field FROM assets a
           CROSS JOIN (SELECT 'cnpj_securitizadora' AS field UNION SELECT 'cnpj_devedor') f
           WHERE TRIM(COALESCE(CASE f.field WHEN 'cnpj_securitizadora' THEN a.cnpj_securitizadora
                                            ELSE a.cnpj_devedor END, '')) <> ''
             AND NOT EXISTS (SELECT 1 FROM asset_cnpj_provenance p
                             WHERE p.asset_id = a.asset_id AND p.field = f.field)""",
    )
    sourced = query(
        path,
        "SELECT source_id, reference_first, reference_last, observed_at FROM asset_cnpj_provenance",
    )

    # Sem fonte registrada: so o devedor digitado a mao do Cafe (a CVM discorda dele).
    assert unsourced == [(ECO_ROW, "cnpj_devedor")]
    assert len(sourced) == 3 and all(all(value for value in row) for row in sourced)


# ----------------------------------------------------------------- dry-run

def test_dry_run_leaves_the_database_untouched_and_shows_what_would_happen(
    script, capsys, tmp_path
):
    path = make_database(tmp_path)
    cvm = make_cvm_dir(tmp_path)
    before = file_sha256(path)
    report = tmp_path / "previa.json"

    code, out, _ = run(script, capsys, path, cvm, "--dry-run", "--report-path", str(report))

    assert code == 0
    assert file_sha256(path) == before
    assert sorted(item.name for item in tmp_path.glob("cri_cra.db*")) == ["cri_cra.db"]
    assert not (tmp_path / "b").exists() and not (tmp_path / "backups").exists()
    assert "Dry-run concluido: nada foi gravado." in out
    assert "gravaria no campo" in out
    assert "registra como candidato; o campo continua vazio" in out
    assert "CONFLITO com o valor atual" in out
    assert "confirma o valor atual" in out
    assert "Devedor: so candidato" in out
    assert "02.773.542/0001-22" in out and "82.120.676/0001-83" in out
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["summary"]["applied"] == 1 and data["summary"]["candidate"] == 1
    assert data["summary"]["conflict"] == 1 and data["summary"]["confirmed"] == 1
    assert {item["kind"] for item in data["archives"]} == {"cri", "cra"}


def test_dry_run_on_a_database_without_migration_002_says_so_and_commit_refuses(
    script, capsys, tmp_path
):
    path = make_database(tmp_path, with_migration_002=False)
    cvm = make_cvm_dir(tmp_path)
    before = file_sha256(path)

    code, out, _ = run(script, capsys, path, cvm, "--dry-run")
    refused, _, error = commit(script, capsys, path, cvm, tmp_path)

    assert code == 0 and "PENDENTE" in out
    assert refused == 1
    assert "migration 002" in error and "apply_migration.py" in error
    assert file_sha256(path) == before


def test_only_limits_the_run_to_one_asset_and_refuses_what_is_not_an_identifier(
    script, capsys, tmp_path
):
    path = make_database(tmp_path)
    cvm = make_cvm_dir(tmp_path)

    refused, _, error = commit(script, capsys, path, cvm, tmp_path, "--only", "!!")

    assert refused == 1 and "--only precisa de um ISIN ou CETIP validos" in error
    assert observations(path) == {}

    code, _, _ = commit(script, capsys, path, cvm, tmp_path, "--only", ECO_ROW.lower())

    assert code == 0
    assert {key[0] for key in observations(path)} == {ECO_ROW}
    assert cnpjs(path)[ALMEIDA_ROW] == ("", None)


# ---------------------------------------------------------------- seguranca

def test_commit_backs_up_the_database_as_it_was_before_writing(script, capsys, tmp_path):
    path = make_database(tmp_path)
    original = cnpjs(path)

    code, out, _ = commit(script, capsys, path, make_cvm_dir(tmp_path), tmp_path)
    backups = sorted((tmp_path / "b").glob("*.sqlite3"))

    assert code == 0 and len(backups) == 1
    assert cnpjs(backups[0]) == original
    assert query(backups[0], "SELECT COUNT(*) FROM asset_cnpj_observations") == [(0,)]
    assert backups[0].name in out and file_sha256(backups[0]) in out


def test_commit_rolls_everything_back_when_a_write_fails(script, capsys, tmp_path, monkeypatch):
    path = make_database(tmp_path)
    cvm = make_cvm_dir(tmp_path)
    before = (cnpjs(path), counts(path))
    original = CnpjObservationRepository.add
    calls = []

    def failing(self, observation, run_id, observed_at=None):
        calls.append(observation.field)

        if len(calls) == 3:
            raise sqlite3.OperationalError("disco cheio")

        return original(self, observation, run_id, observed_at)

    monkeypatch.setattr(CnpjObservationRepository, "add", failing)

    code, _, error = commit(script, capsys, path, cvm, tmp_path)

    assert code == 1 and "disco cheio" in error
    assert (cnpjs(path), counts(path)) == before
    assert len(calls) == 3


def test_a_value_filled_between_the_preview_and_the_write_is_not_overwritten(tmp_path):
    path = make_database(tmp_path)
    archives, ignored = cnpj_resolution.load_archives(make_cvm_dir(tmp_path))

    with closing(open_read_only(path)) as reader:
        _, decisions = cnpj_resolution.build_preview(reader, archives, ignored)

    with closing(connect(path)) as connection:
        connection.execute(
            "UPDATE assets SET cnpj_securitizadora = '99.999.999/0001-99' "
            "WHERE codigo_cetip = '24G2100031'"
        )
        connection.commit()
        before = counts(path)

        with pytest.raises(ResolutionError, match="mudou durante a gravacao"):
            cnpj_resolution.apply_decisions(connection, decisions, "run-x", 2)

    assert cnpjs(path)[ALMEIDA_ROW][0] == "99.999.999/0001-99"
    assert counts(path) == before
    assert query(path, "SELECT COUNT(*) FROM executions WHERE run_id = 'run-x'") == [(0,)]


# ------------------------------------------------------ arquivos e download

def test_files_that_are_not_cvm_informes_or_are_copies_are_reported_and_ignored(
    script, capsys, tmp_path
):
    path = make_database(tmp_path)
    cvm = make_cvm_dir(tmp_path)
    (cvm / "lixo.zip").write_bytes(b"nao e zip")
    (cvm / "copia_cri_2026.zip").write_bytes((cvm / "inf_mensal_cri_2026.zip").read_bytes())

    code, out, _ = run(script, capsys, path, cvm, "--dry-run")

    assert code == 0
    assert "Arquivo ignorado: lixo.zip" in out
    assert "Arquivo ignorado: copia_cri_2026.zip (copia de inf_mensal_cri_2026.zip)" in out


def test_two_different_files_for_the_same_year_are_refused(script, capsys, tmp_path):
    path = make_database(tmp_path)
    cvm = make_cvm_dir(tmp_path)
    write_cvm_zip(cvm / "a_outra_versao.zip", "cri", 2026)

    code, _, error = run(script, capsys, path, cvm, "--dry-run")

    assert code == 1 and "Dois arquivos diferentes para CRI 2026" in error


def test_missing_database_or_cvm_folder_is_a_clean_error(script, capsys, tmp_path):
    cvm = make_cvm_dir(tmp_path)
    missing_db, _, error_db = run(script, capsys, tmp_path / "nao_existe.db", cvm, "--dry-run")
    path = make_database(tmp_path)
    missing_dir, _, error_dir = run(script, capsys, path, tmp_path / "sem_pasta", "--dry-run")

    assert (missing_db, missing_dir) == (1, 1)
    assert "Banco nao encontrado" in error_db
    assert "Pasta dos dados da CVM nao encontrada" in error_dir
    assert "Traceback" not in error_db + error_dir


def test_download_saves_the_official_zip_and_the_dry_run_reads_it(script, capsys, tmp_path):
    path = make_database(tmp_path)
    seed = tmp_path / "seed"
    write_almeida_zips(seed)
    requested = []

    def fetch(url):
        requested.append(url)
        return (seed / url.rsplit("/", 1)[1]).read_bytes()

    cvm = tmp_path / "cvm"
    arguments = ("--only", ALMEIDA_ISIN, "--download", "--years", "2026")

    code, out, _ = run(script, capsys, path, cvm, "--dry-run", *arguments, fetch=fetch)
    again, out_again, _ = run(script, capsys, path, cvm, "--dry-run", *arguments, fetch=fetch)

    assert code == again == 0
    assert requested == [archive_url("cri", 2026)]
    assert (cvm / "inf_mensal_cri_2026.zip").is_file()
    assert "Baixado:" in out and "Ja existe, mantido:" in out_again
    assert "02.773.542/0001-22" in out
    assert "8 informe(s), ref. 2026-01-01 a 2026-08-01" in out


def test_a_failed_download_stops_before_reading_anything_and_leaves_no_partial_file(
    script, capsys, tmp_path
):
    path = make_database(tmp_path)
    cvm = tmp_path / "cvm"

    def fetch(url):
        raise OSError("sem rede")

    code, out, error = run(
        script, capsys, path, cvm, "--dry-run", "--download", "--years", "2026", fetch=fetch
    )

    assert code == 1 and "sem rede" in error
    assert "Dry-run concluido" not in out
    assert not list(cvm.glob("*"))
