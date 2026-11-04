import hashlib
import importlib.util
import pathlib
import sqlite3

import pytest

from apoio_cadastro import masked
from apoio_cadastro import write_zip
from apoio_cda import CONFIDENTIAL_HOLDER
from apoio_cda import HOLDER
from apoio_cda import HOLDER_NAME
from apoio_cda import INVESTEES
from apoio_cda import ZIP_NAME
from apoio_cda import build_cda_zip
from apoio_cda import confid_row
from apoio_cda import fic_fidc_rows
from apoio_cda import fie_row
from apoio_cda import investee_name
from apoio_cda import load_fictitious_cadastro
from conftest import MIGRATION_001
from conftest import create_full_schema
from conftest import create_schema


PROJECT_DIR = pathlib.Path(__file__).resolve().parent.parent
SCRIPT_PATH = PROJECT_DIR / "scripts" / "load_cda.py"

LATER_DATE = (2026, 10, 30, 8, 0, 0)

SECRETS = (
    (HOLDER, CONFIDENTIAL_HOLDER, masked(HOLDER), masked(CONFIDENTIAL_HOLDER), HOLDER_NAME)
    + INVESTEES
    + (investee_name(1), investee_name(2), investee_name(3), "100.5", "200.5", "300.5", "4321.25")
)


def load_module():
    specification = importlib.util.spec_from_file_location("load_cda", SCRIPT_PATH)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


@pytest.fixture
def script():
    return load_module()


@pytest.fixture
def zip_path(tmp_path):
    return write_zip(tmp_path, build_cda_zip(), name=ZIP_NAME)


@pytest.fixture
def database(tmp_path):
    """Banco com as migrations e o cadastro ficticio carregado."""

    path = tmp_path / "fundos.db"
    load_fictitious_cadastro(create_full_schema(path))
    return path


def run_with(script, database, zip_path, *extra):
    return script.main(["--database", str(database), "--zip", str(zip_path), *extra])


def file_hash(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def query(path, sql, parameters=()):
    connection = sqlite3.connect(path)

    try:
        return connection.execute(sql, parameters).fetchall()
    finally:
        connection.close()


def backups_in(directory):
    return sorted(pathlib.Path(directory).glob("fundos_*.sqlite3"))


def other_zip(tmp_path, fie_rows):
    directory = tmp_path / "outro"
    directory.mkdir()
    return write_zip(directory, build_cda_zip(fie_rows, date_time=LATER_DATE), name=ZIP_NAME)


def test_arguments_are_required(script):
    base = ["--database", "x.db", "--zip", "x.zip"]

    for arguments in (
        base,
        base + ["--dry-run", "--commit"],
        base[2:] + ["--dry-run"],
        base[:2] + ["--dry-run"],
    ):
        with pytest.raises(SystemExit) as error:
            script.main(arguments)

        assert error.value.code == 2


def test_dry_run_without_a_database_creates_nothing(script, zip_path, tmp_path, capsys):
    path = tmp_path / "novo" / "fundos.db"

    code = run_with(script, path, zip_path, "--dry-run")
    output = capsys.readouterr().out

    assert code == 0
    assert not path.exists()
    assert not path.parent.exists()
    assert "Cotas identificadas (cda_fie, TP_APLIC Cotas de Fundos): 3 linha(s)" in output
    assert "Banco: nao encontrado; o --commit seria recusado" in output
    assert "Dry-run concluido: nenhum banco foi alterado." in output


def test_dry_run_with_database_does_not_change_the_file(script, database, zip_path, tmp_path, capsys):
    before = file_hash(database)

    code = run_with(script, database, zip_path, "--dry-run")
    output = capsys.readouterr().out

    assert code == 0
    assert file_hash(database) == before
    assert not (tmp_path / "backups").exists()
    assert "  posicoes identificadas: classe 3, fundo 0; fora 0" in output
    assert "  linhas: FIDC 1, FIAGRO 1, misto 0, fora do cadastro carregado 1" in output
    assert "  identificadas: novas 3, iguais 0, valor diferente 0" in output
    assert "Banco: migrations aplicadas e cadastro carregado; o --commit seria aceito." in output


def test_dry_run_reports_a_database_without_cadastro(script, zip_path, tmp_path, capsys):
    path = tmp_path / "vazio.db"
    create_full_schema(path)
    before = file_hash(path)

    code = run_with(script, path, zip_path, "--dry-run")
    output = capsys.readouterr().out

    assert code == 0
    assert file_hash(path) == before
    assert "o --commit seria recusado: O cadastro nao foi carregado" in output
    assert "Comparacao com o banco" not in output


def test_dry_run_shows_the_repeated_key_only_as_information(script, database, tmp_path, capsys):
    path = write_zip(tmp_path, build_cda_zip([fie_row(), fie_row(VL_MERC_POS_FINAL="1")]), name=ZIP_NAME)
    before = file_hash(database)

    code = run_with(script, database, path, "--dry-run")
    output = capsys.readouterr().out

    assert code == 0
    assert file_hash(database) == before
    assert "so informativo (cada linha e uma posicao, com a ordem na chave): 2 linha(s) em 1 chave(s)" in output
    assert "  identificadas: novas 2, iguais 0, valor diferente 0" in output
    assert "seria recusado" not in output
    assert "o --commit seria aceito" in output


def test_repeated_identified_lines_are_committed(script, database, tmp_path, capsys):
    path = write_zip(tmp_path, build_cda_zip([fie_row(), fie_row(VL_MERC_POS_FINAL="1")]), name=ZIP_NAME)

    code = run_with(script, database, path, "--commit", "--backup-dir", str(tmp_path / "bk"))
    output = capsys.readouterr().out

    assert code == 0
    assert "  holdings: criadas 2, existentes 0, conflitos abertos 0" in output
    assert query(database, "SELECT line_order FROM holdings ORDER BY line_order") == [(1,), (2,)]


def test_commit_makes_the_backup_before_loading(script, database, zip_path, tmp_path, capsys):
    backup_dir = tmp_path / "bk"

    code = run_with(
        script, database, zip_path, "--commit", "--backup-dir", str(backup_dir),
        "--last-modified", "Thu, 29 Oct 2026 03:58:52 GMT",
    )
    output = capsys.readouterr().out
    backups = backups_in(backup_dir)

    assert code == 0
    assert len(backups) == 1
    assert query(backups[0], "SELECT COUNT(*) FROM holdings") == [(0,)]
    assert query(database, "SELECT COUNT(*) FROM holdings") == [(3,)]
    assert query(database, "SELECT COUNT(*) FROM confidential_holdings") == [(1,)]
    assert backups[0].name in output
    assert "Last-Modified do ZIP a gravar (UTC): 2026-10-29T03:58:52.000000+00:00" in output
    assert "  holdings: criadas 3, existentes 0, conflitos abertos 0" in output
    assert "integrity_check: ok" in output
    assert "foreign_key_check: 0 problema(s)" in output
    assert "Carga concluida." in output


def test_second_commit_has_nothing_to_load(script, database, zip_path, tmp_path, capsys):
    arguments = ["--commit", "--backup-dir", str(tmp_path / "bk")]

    first = run_with(script, database, zip_path, *arguments)
    capsys.readouterr()
    after_first = file_hash(database)
    dry = run_with(script, database, zip_path, "--dry-run")
    dry_output = capsys.readouterr().out
    second = run_with(script, database, zip_path, *arguments)
    output = capsys.readouterr().out

    assert (first, dry, second) == (0, 0, 0)
    assert "  identificadas: novas 0, iguais 3, valor diferente 0" in dry_output
    assert "Banco: este ZIP ja foi carregado; o --commit nao faria nada." in dry_output
    assert "Nada a carregar: este ZIP ja foi carregado." in output
    assert file_hash(database) == after_first
    assert len(backups_in(tmp_path / "bk")) == 1


def test_reapresentation_needs_last_modified(script, database, zip_path, tmp_path, capsys):
    run_with(
        script, database, zip_path, "--commit", "--backup-dir", str(tmp_path / "bk"),
        "--last-modified", "2026-10-29T03:58:52Z",
    )
    capsys.readouterr()
    fie = fic_fidc_rows()
    fie[0] = dict(fie[0], VL_MERC_POS_FINAL="999.5")
    other = other_zip(tmp_path, fie)
    before = file_hash(database)

    refused = run_with(script, database, other, "--commit", "--backup-dir", str(tmp_path / "bk"))
    error = capsys.readouterr().err
    unchanged = file_hash(database)
    dry = run_with(script, database, other, "--dry-run", "--last-modified", "2026-10-30T08:00:00Z")
    dry_output = capsys.readouterr().out
    loaded = run_with(
        script, database, other, "--commit", "--backup-dir", str(tmp_path / "bk"),
        "--last-modified", "2026-10-30T08:00:00Z",
    )
    output = capsys.readouterr().out

    assert refused == 1
    assert "informe --last-modified" in error
    assert unchanged == before
    assert dry == 0
    assert "  identificadas: novas 0, iguais 2, valor diferente 1" in dry_output
    assert "o --commit carregaria este como reapresentacao" in dry_output
    assert loaded == 0
    assert "  holdings: criadas 1, existentes 2, conflitos abertos 1" in output
    assert query(database, "SELECT COUNT(*) FROM holding_conflicts WHERE status = 'open'") == [(1,)]
    assert len(backups_in(tmp_path / "bk")) == 2


def test_repeated_confidential_holder_refuses_the_commit_before_the_backup(script, database, tmp_path, capsys):
    path = write_zip(tmp_path, build_cda_zip(None, [confid_row(), confid_row()]), name=ZIP_NAME)
    before = file_hash(database)

    code = run_with(script, database, path, "--commit", "--backup-dir", str(tmp_path / "bk"))
    error = capsys.readouterr().err

    assert code == 1
    assert "Arquivo recusado: O arquivo tem chave repetida nas confidenciais: 1 detentor(es)" in error
    assert file_hash(database) == before
    assert backups_in(tmp_path / "bk") == []


def test_database_without_migration_004_is_refused(script, zip_path, tmp_path, capsys):
    path = tmp_path / "so_001.db"
    create_schema(path, (MIGRATION_001,))
    before = file_hash(path)

    dry = run_with(script, path, zip_path, "--dry-run")
    dry_output = capsys.readouterr().out
    code = run_with(script, path, zip_path, "--commit", "--backup-dir", str(tmp_path / "bk"))
    error = capsys.readouterr().err

    assert dry == 0
    assert "o --commit seria recusado: Faltam as migrations 002_party_observations" in dry_output
    assert "004_holdings" in dry_output
    assert code == 1
    assert "Banco recusado: Faltam as migrations" in error
    assert file_hash(path) == before
    assert backups_in(tmp_path / "bk") == []


def test_missing_database_is_refused_on_commit(script, zip_path, tmp_path, capsys):
    path = tmp_path / "nao_existe.db"

    code = run_with(script, path, zip_path, "--commit")
    error = capsys.readouterr().err

    assert code == 1
    assert "Banco nao encontrado" in error
    assert not path.exists()


def test_bad_zip_fails_cleanly(script, database, tmp_path, capsys):
    path = write_zip(tmp_path, build_cda_zip(drop=("cda_fi_PL",)), name=ZIP_NAME)
    before = file_hash(database)

    code = run_with(script, database, path, "--commit", "--backup-dir", str(tmp_path / "bk"))
    error = capsys.readouterr().err

    assert code == 1
    assert "Erro ao carregar o CDA: O ZIP nao tem exatamente os 12 arquivos do CDA" in error
    assert file_hash(database) == before
    assert backups_in(tmp_path / "bk") == []


def test_invalid_last_modified_is_refused(script, database, zip_path, tmp_path, capsys):
    before = file_hash(database)

    code = run_with(
        script, database, zip_path, "--commit", "--backup-dir", str(tmp_path / "bk"),
        "--last-modified", "2026-10-29T03:58:52",
    )
    error = capsys.readouterr().err

    assert code == 1
    assert "precisa ter fuso" in error
    assert file_hash(database) == before
    assert backups_in(tmp_path / "bk") == []


def test_output_has_only_aggregates(script, database, zip_path, tmp_path, capsys):
    run_with(script, database, zip_path, "--dry-run")
    run_with(script, database, zip_path, "--commit", "--backup-dir", str(tmp_path / "bk"))
    captured = capsys.readouterr()
    text = captured.out + captured.err

    for secret in SECRETS:
        assert secret not in text
