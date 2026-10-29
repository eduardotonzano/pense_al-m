import hashlib
import importlib.util
import pathlib
import sqlite3

import pytest

from apoio import FAKE_CPF
from apoio_cadastro import DIRECTOR_NAME
from apoio_cadastro import FUND_HEADER
from apoio_cadastro import PF_AUDITOR_NAME
from apoio_cadastro import PF_MANAGER_NAME
from apoio_cadastro import REFERENCE_DATE
from apoio_cadastro import build_zip
from apoio_cadastro import class_row
from apoio_cadastro import csv_bytes
from apoio_cadastro import fake_cnpj
from apoio_cadastro import fund_row
from apoio_cadastro import pf_manager_row
from apoio_cadastro import write_zip
from conftest import create_full_schema
from conftest import create_schema


PROJECT_DIR = pathlib.Path(__file__).resolve().parent.parent
SCRIPT_PATH = PROJECT_DIR / "scripts" / "load_cadastro.py"


def load_module():
    specification = importlib.util.spec_from_file_location("load_cadastro", SCRIPT_PATH)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


@pytest.fixture
def script():
    return load_module()


@pytest.fixture
def zip_path(tmp_path):
    data = build_zip(
        [
            fund_row(),
            pf_manager_row(ID_Registro_Fundo="2", CNPJ_Fundo=fake_cnpj(2)),
        ],
        [class_row(CNPJ_Auditor=FAKE_CPF, Auditor=PF_AUDITOR_NAME)],
    )
    return write_zip(tmp_path, data)


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "fundos.db"
    create_full_schema(path)
    return path


def run_with(script, database, zip_path, *extra, reference=REFERENCE_DATE):
    return script.main(
        [
            "--database",
            str(database),
            "--zip",
            str(zip_path),
            "--reference-date",
            reference,
            *extra,
        ]
    )


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


SECRETS = (
    FAKE_CPF,
    PF_MANAGER_NAME,
    PF_AUDITOR_NAME,
    DIRECTOR_NAME,
    fake_cnpj(1),
    fake_cnpj(2),
    fake_cnpj(801),
    fake_cnpj(901),
    "Ficticia",
    "Ficticio",
    "Exemplo Alfa",
)


def test_arguments_are_required(script, tmp_path):
    base = ["--database", "x.db", "--zip", "x.zip", "--reference-date", REFERENCE_DATE]

    for arguments in (
        base,
        base + ["--dry-run", "--commit"],
        base[2:] + ["--dry-run"],
        base[:2] + base[4:] + ["--dry-run"],
        base[:4] + ["--dry-run"],
    ):
        with pytest.raises(SystemExit) as error:
            script.main(arguments)

        assert error.value.code == 2


def test_dry_run_writes_nothing(script, database, zip_path, tmp_path, capsys):
    before = file_hash(database)

    code = run_with(script, database, zip_path, "--dry-run")
    output = capsys.readouterr().out

    assert code == 0
    assert file_hash(database) == before
    assert not (tmp_path / "backups").exists()
    assert query(database, "SELECT COUNT(*) FROM funds") == [(0,)]
    assert "registro_fundo.csv: 2 linha(s), 21 coluna(s)" in output
    assert "vigentes que entram: FIDC 2 (cancelados 0)" in output
    assert "Banco: migrations aplicadas; este ZIP ainda nao foi carregado." in output
    assert "Dry-run concluido: nenhum banco foi alterado." in output


def test_dry_run_without_a_database_creates_nothing(script, zip_path, tmp_path, capsys):
    path = tmp_path / "novo" / "fundos.db"

    code = run_with(script, path, zip_path, "--dry-run")
    output = capsys.readouterr().out

    assert code == 0
    assert not path.exists()
    assert not path.parent.exists()
    assert "Banco: nao encontrado; o --commit seria recusado" in output


def test_dry_run_reports_a_missing_migration(script, zip_path, tmp_path, capsys):
    path = tmp_path / "versao_1.db"
    create_schema(path)
    before = file_hash(path)

    code = run_with(script, path, zip_path, "--dry-run")
    output = capsys.readouterr().out

    assert code == 0
    assert file_hash(path) == before
    assert "o --commit seria recusado: faltam as migrations 002_party_observations" in output


def test_commit_makes_the_backup_before_loading(script, database, zip_path, tmp_path, capsys):
    backup_dir = tmp_path / "bk"

    code = run_with(script, database, zip_path, "--commit", "--backup-dir", str(backup_dir))
    output = capsys.readouterr().out
    backups = backups_in(backup_dir)

    assert code == 0
    assert len(backups) == 1
    assert query(backups[0], "SELECT COUNT(*) FROM funds") == [(0,)]
    assert query(database, "SELECT COUNT(*) FROM funds") == [(2,)]
    assert query(database, "SELECT COUNT(*) FROM fund_classes") == [(1,)]
    assert backups[0].name in output
    assert "Gravado (coleta 1, status success):" in output
    assert "funds: criados 2, existentes 0" in output
    assert "varredura de CPF (texto inteiro com 11 digitos ou mascara): observations 0, party_observations 0" in output
    assert "integrity_check: ok" in output
    assert "Carga concluida." in output


def test_second_commit_has_nothing_to_load(script, database, zip_path, tmp_path, capsys):
    backup_dir = tmp_path / "bk"
    arguments = ["--commit", "--backup-dir", str(backup_dir)]

    first = run_with(script, database, zip_path, *arguments)
    capsys.readouterr()
    after_first = file_hash(database)
    second = run_with(script, database, zip_path, *arguments)
    output = capsys.readouterr().out

    assert (first, second) == (0, 0)
    assert "Nada a carregar: este ZIP ja foi carregado." in output
    assert file_hash(database) == after_first
    assert len(backups_in(backup_dir)) == 1


def test_same_zip_with_another_reference_date_is_refused(script, database, zip_path, tmp_path, capsys):
    backup_dir = tmp_path / "bk"
    run_with(script, database, zip_path, "--commit", "--backup-dir", str(backup_dir))
    capsys.readouterr()
    before = file_hash(database)

    dry = run_with(script, database, zip_path, "--dry-run", reference="2026-10-20")
    dry_output = capsys.readouterr().out
    code = run_with(script, database, zip_path, "--commit", "--backup-dir", str(backup_dir), reference="2026-10-20")
    error = capsys.readouterr().err

    assert dry == 0
    assert "ja foi carregado com outra competencia (" + REFERENCE_DATE + ")" in dry_output
    assert code == 1
    assert "ja foi carregado com outra competencia" in error
    assert file_hash(database) == before
    assert len(backups_in(backup_dir)) == 1


def test_database_without_migration_002_is_refused(script, zip_path, tmp_path, capsys):
    path = tmp_path / "versao_1.db"
    create_schema(path)
    before = file_hash(path)

    code = run_with(script, path, zip_path, "--commit")
    error = capsys.readouterr().err

    assert code == 1
    assert "faltam as migrations 002_party_observations" in error
    assert "O banco nao foi alterado." in error
    assert file_hash(path) == before
    assert not (tmp_path / "backups").exists()


def test_missing_database_is_refused_on_commit(script, zip_path, tmp_path, capsys):
    path = tmp_path / "inexistente.db"

    code = run_with(script, path, zip_path, "--commit")
    error = capsys.readouterr().err

    assert code == 1
    assert "Banco nao encontrado" in error
    assert not path.exists()


@pytest.mark.parametrize(
    "reference, message",
    [
        ("27/10/2026", "AAAA-MM-DD"),
        ("2999-01-01", "posterior a hoje"),
        ("2019-01-01", "anterior ao maior Data_Registro do arquivo (2020-01-02)"),
    ],
)
def test_invalid_reference_date_is_refused(script, database, zip_path, capsys, reference, message):
    before = file_hash(database)

    code = run_with(script, database, zip_path, "--commit", reference=reference)
    error = capsys.readouterr().err

    assert code == 1
    assert message in error
    assert file_hash(database) == before


def test_warns_when_the_member_date_differs(script, database, zip_path, capsys):
    code = run_with(script, database, zip_path, "--dry-run", reference="2026-10-26")
    error = capsys.readouterr().err

    assert code == 0
    assert "Aviso: a data dos membros do ZIP (2026-10-27)" in error


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


def test_bad_zip_fails_cleanly(script, database, tmp_path, capsys):
    content = csv_bytes(FUND_HEADER[:-1], [fund_row()])
    path = write_zip(tmp_path, build_zip(members={"registro_fundo.csv": content}))
    before = file_hash(database)

    code = run_with(script, database, path, "--commit")
    error = capsys.readouterr().err

    assert code == 1
    assert "Cabecalho de registro_fundo.csv diferente do esperado" in error
    assert file_hash(database) == before


def test_failure_after_the_backup_keeps_the_database(script, database, zip_path, tmp_path, monkeypatch, capsys):
    def failing(*arguments, **options):
        raise RuntimeError("falha simulada")

    monkeypatch.setattr(script, "load_cadastro", failing)
    backup_dir = tmp_path / "bk"
    before = file_hash(database)

    code = run_with(script, database, zip_path, "--commit", "--backup-dir", str(backup_dir))
    error = capsys.readouterr().err

    assert code == 1
    assert "Falha: o banco foi mantido como estava. Backup:" in error
    assert file_hash(database) == before
    assert len(backups_in(backup_dir)) == 1


def test_output_has_only_aggregates(script, database, zip_path, tmp_path, capsys):
    run_with(script, database, zip_path, "--dry-run")
    dry = capsys.readouterr()
    run_with(script, database, zip_path, "--commit", "--backup-dir", str(tmp_path / "bk"))
    committed = capsys.readouterr()
    text = dry.out + dry.err + committed.out + committed.err

    for secret in SECRETS:
        assert secret not in text
