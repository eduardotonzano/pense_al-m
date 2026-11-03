import hashlib
import importlib.util
import pathlib
import sqlite3

import pytest

from apoio_cadastro import fake_cnpj
from apoio_cadastro import write_zip
from apoio_informe_fiagro import ADMIN_CNPJ
from apoio_informe_fiagro import ADMIN_NAME
from apoio_informe_fiagro import CONTACTS
from apoio_informe_fiagro import FIRST_SUBCLASS
from apoio_informe_fiagro import MANAGER_CNPJ
from apoio_informe_fiagro import MANAGER_NAME
from apoio_informe_fiagro import ZIP_NAME
from apoio_informe_fiagro import build_informe_zip
from apoio_informe_fiagro import class_row
from apoio_informe_fiagro import fake_isin
from apoio_informe_fiagro import load_fictitious_cadastro
from apoio_informe_fiagro import subclass_row
from apoio_informe_fiagro import subject_name
from apoio_informe_fiagro import subject_rows
from conftest import MIGRATION_001
from conftest import create_full_schema
from conftest import create_schema
from fundos.informe_fiagro import columns


PROJECT_DIR = pathlib.Path(__file__).resolve().parent.parent
SCRIPT_PATH = PROJECT_DIR / "scripts" / "load_informe_fiagro.py"

CLASS = columns.CLASS_TABLE
SUBCLASS = columns.SUBCLASS_TABLE

FIAGRO_OBSERVATIONS = "SELECT COUNT(*) FROM observations WHERE field_name LIKE 'inf_mensal_fiagro%'"

SECRETS = (
    fake_cnpj(1),
    ADMIN_CNPJ,
    MANAGER_CNPJ,
    ADMIN_NAME,
    MANAGER_NAME,
    subject_name(1),
    fake_isin(1),
    FIRST_SUBCLASS,
    "Ficticia",
    "ficticio",
    *CONTACTS.values(),
)

SAME_COMPETENCE = (
    "Ja existe informe de FIAGRO carregado para a competencia 2026-09 (outro ZIP). A reapresentacao"
    " do informe de FIAGRO ainda nao existe (tarefa propria)"
)


def load_module():
    specification = importlib.util.spec_from_file_location("load_informe_fiagro", SCRIPT_PATH)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


@pytest.fixture
def script():
    return load_module()


@pytest.fixture
def zip_path(tmp_path):
    return write_zip(tmp_path, build_informe_zip(), name=ZIP_NAME)


@pytest.fixture
def database(tmp_path):
    """Banco com as migrations e o cadastro ficticio da classe FIAGRO 1 carregado."""

    path = tmp_path / "fundos.db"
    load_fictitious_cadastro(create_full_schema(path), classes=(1,))
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


def other_zip(tmp_path, tables=None):
    directory = tmp_path / "outro"
    directory.mkdir()
    return write_zip(directory, build_informe_zip(tables, date_time=(2026, 10, 31, 8, 0, 0)), name=ZIP_NAME)


def test_arguments_are_required(script):
    base = ["--database", "x.db", "--zip", "x.zip"]

    for arguments in (
        base,
        base + ["--dry-run", "--commit"],
        base[2:] + ["--dry-run"],
        base[:2] + ["--dry-run"],
        base + ["--dry-run", "--reference-date", "2026-09-30"],
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
    assert "Banco: nao encontrado; o --commit seria recusado" in output
    assert "Dry-run concluido: nenhum banco foi alterado." in output


def test_dry_run_reports_a_database_without_cadastro(script, zip_path, tmp_path, capsys):
    path = tmp_path / "vazio.db"
    create_full_schema(path)
    before = file_hash(path)

    code = run_with(script, path, zip_path, "--dry-run")
    output = capsys.readouterr().out

    assert code == 0
    assert file_hash(path) == before
    assert "o --commit seria recusado: o cadastro nao foi carregado" in output


def test_dry_run_with_cadastro_shows_the_match_and_writes_nothing(script, database, zip_path, tmp_path, capsys):
    before = file_hash(database)

    code = run_with(script, database, zip_path, "--dry-run")
    output = capsys.readouterr().out

    assert code == 0
    assert file_hash(database) == before
    assert not (tmp_path / "backups").exists()
    assert "  lido inf_mensal_fiagro: 1 linha(s)" in output
    assert "  lido inf_mensal_fiagro_subclasse: 2 linha(s)" in output
    assert "Linhas lidas (2 arquivos, 139 campos, 3 linhas):" in output
    assert "gravada como 2026-09-30 (ultimo dia do mes" in output
    assert "  inf_mensal_fiagro: entram 1; fora 0" in output
    assert "  inf_mensal_fiagro_subclasse: entram 2; fora 0" in output
    assert "Classes (CNPJ_Classe distintos do arquivo de classe): entram 1; fora 0" in output
    assert "  observations total: 128 (das quais com valor zero: " in output
    assert "  series (classe e rotulo da subclasse): 2" in output
    assert "  party_observations: administrador 1, gestor 1" in output
    assert "Last-Modified do ZIP: nao informado" in output
    assert "esta competencia ainda nao foi carregada" in output


def test_commit_makes_the_backup_before_loading(script, database, zip_path, tmp_path, capsys):
    backup_dir = tmp_path / "bk"

    code = run_with(script, database, zip_path, "--commit", "--backup-dir", str(backup_dir))
    output = capsys.readouterr().out
    backups = backups_in(backup_dir)

    assert code == 0
    assert len(backups) == 1
    assert query(backups[0], FIAGRO_OBSERVATIONS) == [(0,)]
    assert query(database, FIAGRO_OBSERVATIONS) == [(128,)]
    assert backups[0].name in output
    assert "  gravado inf_mensal_fiagro: 122 observacao(oes)" in output
    assert "  gravado inf_mensal_fiagro_subclasse: 6 observacao(oes)" in output
    assert "  series: criadas 2, existentes 0" in output
    assert "  party_observations gestor: criados 1, existentes 0" in output
    assert "varredura de CPF (texto inteiro com 11 digitos ou mascara): observations 0, party_observations 0" in output
    assert "integrity_check: ok" in output
    assert "Carga concluida." in output
    # Sem --last-modified, o manifesto fica sem a data.
    assert "Last-Modified do ZIP: nao informado" in output
    assert query(database, "SELECT last_modified FROM raw_records WHERE file_name = ?", (ZIP_NAME,)) == [(None,)]


def test_last_modified_is_recorded_in_utc(script, database, zip_path, tmp_path, capsys):
    code = run_with(
        script, database, zip_path, "--commit", "--backup-dir", str(tmp_path / "bk"),
        "--last-modified", "Sat, 24 Oct 2026 11:46:15 GMT",
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "Last-Modified do ZIP a gravar (UTC): 2026-10-24T11:46:15.000000+00:00" in output
    assert query(database, "SELECT last_modified FROM raw_records WHERE file_name = ?", (ZIP_NAME,)) == [
        ("2026-10-24T11:46:15.000000+00:00",)
    ]


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
    assert "Banco: este ZIP ja foi carregado; o --commit nao faria nada." in dry_output
    assert "Nada a carregar: este ZIP ja foi carregado." in output
    assert file_hash(database) == after_first
    assert len(backups_in(tmp_path / "bk")) == 1


def test_other_zip_of_the_same_competence_is_refused(script, database, zip_path, tmp_path, capsys):
    run_with(script, database, zip_path, "--commit", "--backup-dir", str(tmp_path / "bk"))
    capsys.readouterr()
    before = file_hash(database)
    other = other_zip(tmp_path, subject_rows(Patrimonio_Liquido="2000"))

    dry = run_with(script, database, other, "--dry-run", "--last-modified", "2026-10-31T09:00:00Z")
    dry_output = capsys.readouterr().out
    code = run_with(
        script, database, other, "--commit", "--backup-dir", str(tmp_path / "bk"),
        "--last-modified", "2026-10-31T09:00:00Z",
    )
    error = capsys.readouterr().err

    assert dry == 0
    assert "Banco: o --commit seria recusado: " + SAME_COMPETENCE + "." in dry_output
    assert code == 1
    assert SAME_COMPETENCE + ". O banco nao foi alterado." in error
    assert file_hash(database) == before
    assert len(backups_in(tmp_path / "bk")) == 1


@pytest.mark.parametrize(
    ("value", "message"),
    (
        ("2026-10-24T11:46:15", "precisa ter fuso"),
        ("24/10/2026", "invalida"),
        ("Sat, 99 Oct 2026 11:46:15 GMT", "invalida"),
        ("2099-01-01T00:00:00Z", "posterior a agora"),
    ),
)
def test_invalid_last_modified_is_refused(script, database, zip_path, tmp_path, capsys, value, message):
    before = file_hash(database)

    code = run_with(script, database, zip_path, "--commit", "--backup-dir", str(tmp_path / "bk"), "--last-modified", value)
    error = capsys.readouterr().err

    assert code == 1
    assert "Erro ao carregar o informe de FIAGRO: " in error
    assert message in error
    assert file_hash(database) == before
    assert backups_in(tmp_path / "bk") == []


def test_member_dates_after_last_modified_only_warn(script, database, zip_path, capsys):
    code = run_with(script, database, zip_path, "--dry-run", "--last-modified", "2026-10-20T00:00:00Z")
    captured = capsys.readouterr()

    assert code == 0
    assert "Aviso: a data dos membros do ZIP (2026-10-24) e posterior a do --last-modified (2026-10-20)" in captured.err
    assert "Dry-run concluido" in captured.out


def test_competence_that_does_not_match_data_referencia_fails_cleanly(script, database, tmp_path, capsys):
    tables = {
        CLASS: [class_row(Data_Referencia="2026-08-01")],
        SUBCLASS: [subclass_row(Data_Referencia="2026-08-01")],
    }
    path = write_zip(tmp_path, build_informe_zip(tables), name=ZIP_NAME)
    before = file_hash(database)

    code = run_with(script, database, path, "--commit", "--backup-dir", str(tmp_path / "bk"))
    error = capsys.readouterr().err

    assert code == 1
    assert (
        "Erro ao carregar o informe de FIAGRO: Data_Referencia 2026-08-01 nao e o dia 1 do AAAAMM dos membros (202609)"
        in error
    )
    assert file_hash(database) == before
    assert backups_in(tmp_path / "bk") == []


def test_database_without_migration_002_is_refused(script, zip_path, tmp_path, capsys):
    path = tmp_path / "so_001.db"
    create_schema(path, (MIGRATION_001,))
    before = file_hash(path)

    dry = run_with(script, path, zip_path, "--dry-run")
    dry_output = capsys.readouterr().out
    code = run_with(script, path, zip_path, "--commit", "--backup-dir", str(tmp_path / "bk"))
    error = capsys.readouterr().err

    assert dry == 0
    assert "o --commit seria recusado: faltam as migrations 002_party_observations" in dry_output
    assert code == 1
    assert "Banco recusado: faltam as migrations 002_party_observations" in error
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
    path = write_zip(tmp_path, build_informe_zip(drop=(SUBCLASS,)), name=ZIP_NAME)
    before = file_hash(database)

    code = run_with(script, database, path, "--commit", "--backup-dir", str(tmp_path / "bk"))
    error = capsys.readouterr().err

    assert code == 1
    assert "Erro ao carregar o informe de FIAGRO: O ZIP nao tem exatamente os 2 arquivos" in error
    assert file_hash(database) == before
    assert backups_in(tmp_path / "bk") == []


def test_output_has_only_aggregates(script, database, zip_path, tmp_path, capsys):
    run_with(script, database, zip_path, "--dry-run")
    run_with(script, database, zip_path, "--commit", "--backup-dir", str(tmp_path / "bk"))
    captured = capsys.readouterr()
    text = captured.out + captured.err

    for secret in SECRETS:
        assert secret not in text
