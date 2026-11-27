import hashlib
import importlib.util
import pathlib
import sqlite3

import pytest

from apoio import make_test_cnpj
from apoio_quota_classes import SyntheticSeries
from conftest import create_full_schema
from conftest import create_schema
from fundos import backup


PROJECT_DIR = pathlib.Path(__file__).resolve().parent.parent
REPORT_PATH = PROJECT_DIR / "scripts" / "report_quota_class_map.py"
REVIEW_PATH = PROJECT_DIR / "scripts" / "review_quota_class_map.py"

NETWORK_DATABASE = "\\\\servidor\\pasta\\fundos.db"
NETWORK_BACKUP_DIR = "\\\\servidor\\pasta\\bk"
NOTE = "conferido contra a secao 10.6 (nota ficticia)"
SECRET_NOTE = "nota secreta ficticia " + "9" * 11


def load(path, name):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


@pytest.fixture
def report_script():
    return load(REPORT_PATH, "report_quota_class_map")


@pytest.fixture
def review_script():
    return load(REVIEW_PATH, "review_quota_class_map")


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "fundos.db"
    connection = create_full_schema(path).connect()

    try:
        informe = SyntheticSeries(connection)
        _, first = informe.fund_and_class(1)
        informe.series(first, "Subclasse Senior S\u00e9rie 1")
        informe.series(first, "Subclasse Subordinada Subordinada 1 |")
        _, second = informe.fund_and_class(2)
        informe.series(second, "Cota Unica Ficticia")
    finally:
        connection.close()

    return path


def file_hash(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def query(path, sql):
    connection = sqlite3.connect(path)

    try:
        return connection.execute(sql).fetchall()
    finally:
        connection.close()


def review_args(database, *extra, note=NOTE, reviewer="papel:revisor_fundos", rule="1", status="revisado"):
    return [
        "--database", str(database), "--rule-id", rule, "--status", status,
        "--reviewer", reviewer, "--note", note, *extra,
    ]


def assert_no_secret(text):
    for n in (1, 2):
        assert make_test_cnpj(n) not in text

    assert "servidor" not in text
    assert "Cota Unica Ficticia" not in text


def test_report_shows_counts_and_changes_nothing(report_script, database, capsys):
    before = file_hash(database)

    code = report_script.main(["--database", str(database)])
    captured = capsys.readouterr()

    assert code == 0
    assert file_hash(database) == before
    assert sorted(p.name for p in database.parent.iterdir()) == ["fundos.db"]
    assert "Competencia 2026-09-30:" in captured.out
    assert "  Series de FIDC com tab_X_2: 3 (rotulos normalizados distintos: 3)" in captured.out
    assert "    cota unica ficticia: 1 serie(s), 1 variante(s) original(is), rotulo_nao_mapeado" in captured.out
    assert "Relatorio concluido: nenhum banco foi alterado." in captured.out
    assert_no_secret(captured.out + captured.err)


def test_report_for_one_competence(report_script, database, capsys):
    code = report_script.main(["--database", str(database), "--reference-date", "2026-10-31"])
    captured = capsys.readouterr()

    assert code == 0
    assert "  Series de FIDC com tab_X_2: 0" in captured.out


def test_report_refuses_network_and_long_paths(report_script, database, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(report_script, "open_read_only", None)
    monkeypatch.setattr(
        backup, "_drive_type", lambda drive: backup.REMOTE_DRIVE if drive.upper() == "L:" else 3
    )

    network = report_script.main(["--database", NETWORK_DATABASE])
    first = capsys.readouterr()
    remote = report_script.main(["--database", "L:\\pasta\\fundos.db"])
    second = capsys.readouterr()
    long_path = report_script.main(["--database", str(tmp_path / ("b" * 255) / "fundos.db")])
    third = capsys.readouterr()

    assert (network, remote, long_path) == (1, 1, 1)
    assert "--database em caminho de rede (UNC)" in first.err
    assert "--database em caminho de rede (unidade remota)" in second.err
    assert "caminho longo" in third.err
    assert "servidor" not in first.out + first.err


def test_report_refuses_wal_and_missing_migration(report_script, database, tmp_path, capsys):
    only_001 = tmp_path / "so_001.db"
    create_schema(only_001)
    missing = report_script.main(["--database", str(only_001)])
    first = capsys.readouterr()
    connection = sqlite3.connect(database)

    try:
        connection.execute("PRAGMA journal_mode=WAL")
    finally:
        connection.close()

    wal = report_script.main(["--database", str(database)])
    second = capsys.readouterr()

    assert (missing, wal) == (1, 1)
    assert "Banco sem as migrations: 006_quota_class_map." in first.err
    assert "WAL recusado" in second.err


def test_report_unexpected_error_prints_only_the_type(report_script, database, monkeypatch, capsys):
    def broken(*args, **kwargs):
        raise RuntimeError("valor de linha ficticio")

    monkeypatch.setattr(report_script, "review_report", broken)

    code = report_script.main(["--database", str(database)])
    captured = capsys.readouterr()

    assert code == 1
    assert "Erro inesperado no relatorio do quota_class_map: RuntimeError" in captured.err
    assert "valor de linha" not in captured.err


def test_review_dry_run_then_commit_then_nothing(review_script, database, tmp_path, capsys):
    backup_dir = tmp_path / "bk"
    before = file_hash(database)

    dry = review_script.main(review_args(database, "--dry-run", "--backup-dir", str(backup_dir)))
    dry_output = capsys.readouterr()
    after_dry = file_hash(database)
    no_backup_after_dry_run = not backup_dir.exists()
    committed = review_script.main(review_args(database, "--commit", "--backup-dir", str(backup_dir)))
    commit_output = capsys.readouterr()
    after_commit = file_hash(database)
    again = review_script.main(review_args(database, "--commit", "--backup-dir", str(backup_dir)))
    again_output = capsys.readouterr()

    assert (dry, committed, again) == (0, 0, 0)
    assert after_dry == before
    assert "Regra #1: subclasse senior" in dry_output.out
    assert "  situacao: proposto -> revisado" in dry_output.out
    assert "Dry-run concluido: nenhum banco foi alterado." in dry_output.out
    assert no_backup_after_dry_run
    assert "Revisao gravada: regra #1 proposto -> revisado; audit_log #1" in commit_output.out
    assert "  integrity_check: ok" in commit_output.out
    assert len(list(backup_dir.glob("fundos_*.sqlite3"))) == 1
    assert "Nada a revisar: a regra ja esta revisado." in again_output.out
    assert file_hash(database) == after_commit
    assert len(list(backup_dir.glob("fundos_*.sqlite3"))) == 1
    assert query(database, "SELECT review_status, reviewer FROM quota_class_map WHERE id = 1") == [
        ("revisado", "papel:revisor_fundos")
    ]
    assert query(database, "SELECT action, actor FROM audit_log") == [
        ("quota_class_map_revisao", "papel:revisor_fundos")
    ]

    for output in (dry_output, commit_output, again_output):
        assert NOTE not in output.out + output.err
        assert "nota: " + str(len(NOTE)) + " caractere(s)" in output.out


@pytest.mark.parametrize(
    "note, reason",
    [
        ("linha um\nlinha dois", "quebra de linha"),
        ("nota com acentua\u00e7\u00e3o", "ASCII imprimivel"),
        ("x" * 201, "ate 200 caracteres"),
        (SECRET_NOTE, "11 digitos"),
        ("cpf " + ".".join(["123", "456", "789"]) + "-09", "mascara"),
        ("cnpj " + ".".join(["12", "345", "678"]) + "/" + "0001-95", "mascara"),
    ],
)
def test_review_validates_the_note_before_anything(review_script, database, monkeypatch, capsys, note, reason):
    # A nota e conferida antes de olhar o caminho e o banco.
    monkeypatch.setattr(review_script, "check_local_paths", None)
    before = file_hash(database)

    code = review_script.main(review_args(NETWORK_DATABASE, "--commit", note=note))
    captured = capsys.readouterr()

    assert code == 1
    assert "Nota recusada" in captured.err
    assert reason in captured.err
    assert note not in captured.out + captured.err
    assert "Pacote fundos" not in captured.out
    assert file_hash(database) == before


def test_review_refuses_a_reviewer_outside_the_list(review_script, database, capsys):
    code = review_script.main(review_args(database, "--dry-run", reviewer="Pessoa Ficticia"))
    captured = capsys.readouterr()

    assert code == 1
    assert "Revisor recusado" in captured.err
    assert "Pessoa Ficticia" not in captured.out + captured.err


@pytest.mark.parametrize("mode", ["--dry-run", "--commit"])
def test_review_refuses_network_paths(review_script, database, mode, capsys):
    before = file_hash(database)

    first = review_script.main(review_args(NETWORK_DATABASE, mode))
    first_output = capsys.readouterr()
    second = review_script.main(review_args(database, mode, "--backup-dir", NETWORK_BACKUP_DIR))
    second_output = capsys.readouterr()

    assert (first, second) == (1, 1)
    assert "--database em caminho de rede (UNC)" in first_output.err
    assert "--backup-dir em caminho de rede (UNC)" in second_output.err
    assert "servidor" not in first_output.out + first_output.err + second_output.out + second_output.err
    assert file_hash(database) == before


def test_review_refuses_invalid_transition_and_unknown_rule(review_script, database, tmp_path, capsys):
    backup_dir = tmp_path / "bk"
    rejected = review_script.main(
        review_args(database, "--commit", "--backup-dir", str(backup_dir), status="rejeitado")
    )
    capsys.readouterr()
    back = review_script.main(review_args(database, "--commit", "--backup-dir", str(backup_dir)))
    back_output = capsys.readouterr()
    unknown = review_script.main(review_args(database, "--dry-run", rule="99"))
    unknown_output = capsys.readouterr()

    assert (rejected, back, unknown) == (0, 1, 1)
    assert "nao pode ir para revisado" in back_output.err
    assert "Regra nao encontrada" in unknown_output.err
    assert len(list(backup_dir.glob("fundos_*.sqlite3"))) == 1


def test_review_arguments_are_required(review_script):
    for arguments in (
        ["--database", "x.db", "--rule-id", "1", "--status", "revisado", "--reviewer", "papel:revisor_fundos", "--note", NOTE],
        review_args("x.db", "--dry-run", status="proposto"),
        review_args("x.db", "--dry-run", rule="0"),
        review_args("x.db", "--dry-run", "--commit"),
    ):
        with pytest.raises(SystemExit) as error:
            review_script.main(arguments)

        assert error.value.code == 2
