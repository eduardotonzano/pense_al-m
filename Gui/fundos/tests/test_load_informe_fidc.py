import hashlib
import importlib.util
import pathlib
import sqlite3

import pytest

from apoio import FAKE_CPF
from apoio_cadastro import fake_cnpj
from apoio_cadastro import masked
from apoio_cadastro import write_zip
from apoio_informe_fidc import ADMIN_NAME
from apoio_informe_fidc import SENIOR
from apoio_informe_fidc import ZIP_NAME
from apoio_informe_fidc import build_informe_zip
from apoio_informe_fidc import load_fictitious_cadastro
from apoio_informe_fidc import row
from apoio_informe_fidc import subject_name
from apoio_informe_fidc import subject_rows
from conftest import create_full_schema
from conftest import create_schema


PROJECT_DIR = pathlib.Path(__file__).resolve().parent.parent
SCRIPT_PATH = PROJECT_DIR / "scripts" / "load_informe_fidc.py"


def load_module():
    specification = importlib.util.spec_from_file_location("load_informe_fidc", SCRIPT_PATH)
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
    """Banco com as migrations e o cadastro ficticio da classe 1 carregado."""

    path = tmp_path / "fundos.db"
    load_fictitious_cadastro(create_full_schema(path), classes=(1,))
    return path


def run_with(script, database, zip_path, *extra):
    return script.main(["--database", str(database), "--zip", str(zip_path), *extra])


def file_hash(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def query(path, sql):
    connection = sqlite3.connect(path)

    try:
        return connection.execute(sql).fetchall()
    finally:
        connection.close()


def backups_in(directory):
    return sorted(pathlib.Path(directory).glob("fundos_*.sqlite3"))


INFORME_OBSERVATIONS = "SELECT COUNT(*) FROM observations WHERE field_name LIKE 'tab%'"

SECRETS = (
    FAKE_CPF,
    fake_cnpj(1),
    masked(fake_cnpj(1)),
    fake_cnpj(555),
    fake_cnpj(901),
    ADMIN_NAME,
    subject_name(1),
    SENIOR,
    "SUBFICTICIA",
    "Ficticia",
    "ficticio",
)


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
    assert "Casamento com o cadastro nao calculado" in output


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
    assert "  lido tab_I: 1 linha(s)" in output
    assert "Linhas lidas (18 tabelas, 461 campos," in output
    assert "  tab_I: classe 1, fundo 0; fora 0" in output
    assert "Assuntos (TP_FUNDO_CLASSE e CNPJ): classe 1, fundo 0; fora 0" in output
    assert "  series (assunto e rotulo): 2" in output
    assert "  party_observations administrador: 1" in output
    assert "Dry-run concluido: nenhum banco foi alterado." in output


def test_commit_makes_the_backup_before_loading(script, database, zip_path, tmp_path, capsys):
    backup_dir = tmp_path / "bk"

    code = run_with(script, database, zip_path, "--commit", "--backup-dir", str(backup_dir))
    output = capsys.readouterr().out
    backups = backups_in(backup_dir)

    assert code == 0
    assert len(backups) == 1
    assert query(backups[0], INFORME_OBSERVATIONS) == [(0,)]
    assert query(database, INFORME_OBSERVATIONS)[0][0] > 0
    assert backups[0].name in output
    assert "  gravado tab_IX: 72 observacao(oes)" in output
    assert "  gravado tab_X_4: 0 observacao(oes)" in output
    assert "Gravado (coleta" in output
    assert "varredura de CPF (texto inteiro com 11 digitos ou mascara): observations 0, party_observations 0" in output
    assert "integrity_check: ok" in output
    assert "Carga concluida." in output


def test_second_commit_has_nothing_to_load(script, database, zip_path, tmp_path, capsys):
    arguments = ["--commit", "--backup-dir", str(tmp_path / "bk")]

    first = run_with(script, database, zip_path, *arguments)
    capsys.readouterr()
    after_first = file_hash(database)
    second = run_with(script, database, zip_path, *arguments)
    output = capsys.readouterr().out

    assert (first, second) == (0, 0)
    assert "Nada a carregar: este ZIP ja foi carregado." in output
    assert file_hash(database) == after_first
    assert len(backups_in(tmp_path / "bk")) == 1


def test_other_zip_of_the_same_competence_is_refused(script, database, zip_path, tmp_path, capsys):
    run_with(script, database, zip_path, "--commit", "--backup-dir", str(tmp_path / "bk"))
    capsys.readouterr()
    before = file_hash(database)
    tables = subject_rows()
    tables["tab_IV"] = [row("tab_IV", TAB_IV_A_VL_PL="1200.00")]
    other_dir = tmp_path / "outro"
    other_dir.mkdir()
    other = write_zip(other_dir, build_informe_zip(tables), name=ZIP_NAME)

    dry = run_with(script, database, other, "--dry-run")
    dry_output = capsys.readouterr().out
    code = run_with(script, database, other, "--commit", "--backup-dir", str(tmp_path / "bk"))
    error = capsys.readouterr().err

    assert dry == 0
    assert "reapresentacao e a FU4.2" in dry_output
    assert code == 1
    assert "reapresentacao e a FU4.2" in error
    assert file_hash(database) == before
    assert len(backups_in(tmp_path / "bk")) == 1


def test_database_without_migration_002_is_refused(script, zip_path, tmp_path, capsys):
    path = tmp_path / "versao_1.db"
    create_schema(path)
    before = file_hash(path)

    code = run_with(script, path, zip_path, "--commit")
    error = capsys.readouterr().err

    assert code == 1
    assert "faltam as migrations 002_party_observations" in error
    assert file_hash(path) == before
    assert not (tmp_path / "backups").exists()


def test_database_without_cadastro_is_refused_on_commit(script, zip_path, tmp_path, capsys):
    path = tmp_path / "vazio.db"
    create_full_schema(path)
    before = file_hash(path)

    code = run_with(script, path, zip_path, "--commit")
    error = capsys.readouterr().err

    assert code == 1
    assert "o cadastro nao foi carregado" in error
    assert file_hash(path) == before


def test_missing_database_is_refused_on_commit(script, zip_path, tmp_path, capsys):
    path = tmp_path / "inexistente.db"

    code = run_with(script, path, zip_path, "--commit")
    error = capsys.readouterr().err

    assert code == 1
    assert "Banco nao encontrado" in error
    assert not path.exists()


def test_bad_zip_fails_cleanly(script, database, tmp_path, capsys):
    other_dir = tmp_path / "ruim"
    other_dir.mkdir()
    path = write_zip(other_dir, build_informe_zip(drop=("tab_X_7",)), name=ZIP_NAME)
    before = file_hash(database)

    code = run_with(script, database, path, "--commit")
    error = capsys.readouterr().err

    assert code == 1
    assert "faltam tab_X_7" in error
    assert file_hash(database) == before


def test_network_path_detection(script):
    assert script.is_network_path("\\\\servidor\\pasta\\fundos.db")
    assert script.is_network_path("//servidor/pasta/fundos.db")
    assert not script.is_network_path("C:\\bk\\fundos.db")


def test_warns_but_does_not_refuse_a_network_database(script, database, zip_path, monkeypatch, capsys):
    monkeypatch.setattr(script, "is_network_path", lambda path: True)

    code = run_with(script, database, zip_path, "--dry-run")
    captured = capsys.readouterr()

    assert code == 0
    assert "caminho de rede" in captured.err
    assert "Dry-run concluido" in captured.out


def test_failure_after_the_backup_keeps_the_database(script, database, zip_path, tmp_path, monkeypatch, capsys):
    def failing(*arguments, **options):
        raise RuntimeError("falha simulada")

    monkeypatch.setattr(script, "load_informe", failing)
    before = file_hash(database)

    code = run_with(script, database, zip_path, "--commit", "--backup-dir", str(tmp_path / "bk"))
    error = capsys.readouterr().err

    assert code == 1
    assert "Falha: o banco foi mantido como estava. Backup:" in error
    assert file_hash(database) == before
    assert len(backups_in(tmp_path / "bk")) == 1


def test_output_has_only_aggregates(script, database, zip_path, tmp_path, capsys):
    run_with(script, database, zip_path, "--dry-run")
    dry = capsys.readouterr()
    run_with(script, database, zip_path, "--commit", "--backup-dir", str(tmp_path / "bk"))
    committed = capsys.readouterr()
    text = dry.out + dry.err + committed.out + committed.err

    for secret in SECRETS:
        assert secret not in text
