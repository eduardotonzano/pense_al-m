import hashlib
import importlib.util
import pathlib
import sqlite3

import pytest

from apoio import make_test_cnpj
from apoio_fic_fidc import FIAGRO
from apoio_fic_fidc import OCT
from apoio_fic_fidc import SEP
from apoio_fic_fidc import SyntheticFicFidc
from conftest import create_full_schema
from conftest import create_schema

from fundos import backup
from fundos.fic_fidc.cda_check import cda_vs_informe
from fundos.fic_fidc.classification import classify
from fundos.fic_fidc.report import format_check_report
from fundos.fic_fidc.report import format_cross_report


PROJECT_DIR = pathlib.Path(__file__).resolve().parent.parent
SCRIPT_PATH = PROJECT_DIR / "scripts" / "classify_fic_fidc.py"

NETWORK_DATABASE = "\\\\servidor\\pasta\\fundos.db"
NETWORK_BACKUP_DIR = "\\\\servidor\\pasta\\bk"

# Valores ficticios que nao podem aparecer na saida (so contagens).
COTAS = ("9601", "8123", "7001", "1003")
ATIVO = "10000"


def load_module():
    specification = importlib.util.spec_from_file_location("classify_fic_fidc", SCRIPT_PATH)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


@pytest.fixture
def script():
    return load_module()


def populate(path):
    """FIC-FIDC, 2 em revisao e 1 nao classificado; o primeiro com posicao no CDA."""

    connection = create_full_schema(path).connect()

    try:
        informe = SyntheticFicFidc(connection)
        subjects = [informe.typed_class(n) for n in (1, 2, 3, 4)]

        for subject, cotas in zip(subjects, COTAS):
            informe.put_ratio(subject, cotas, ATIVO)

        informe.holding(subjects[0], informe.investee(1), "9601")
    finally:
        connection.close()


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "fundos.db"
    populate(path)
    return path


def run_with(script, database, *extra, reference=SEP):
    return script.main(["--database", str(database), "--reference-date", reference, *extra])


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


def assert_no_secret(text):
    # As linhas do pacote e do backup (caminho, tamanho e hash) tem digitos
    # que variam a cada execucao; o resto da saida e so contagem.
    text = "\n".join(
        line
        for line in text.splitlines()
        if not line.startswith(("Pacote fundos:", "Backup:", "  tamanho:", "  sha256:"))
    )

    for n in (1, 2, 3, 4):
        assert make_test_cnpj(n) not in text

    assert make_test_cnpj(1, alphanumeric=True) not in text

    for value in COTAS:
        assert value not in text

    assert "servidor" not in text


def test_arguments_are_required(script):
    base = ["--database", "x.db", "--reference-date", SEP]

    for arguments in (
        base,
        base + ["--dry-run", "--commit"],
        base[:2] + ["--dry-run"],
        base[2:] + ["--dry-run"],
        ["--database", "x.db", "--reference-date", "2026-09-29", "--dry-run"],
        ["--database", "x.db", "--reference-date", "30/09/2026", "--dry-run"],
    ):
        with pytest.raises(SystemExit) as error:
            script.main(arguments)

        assert error.value.code == 2


def test_dry_run_reports_only_counts_and_changes_nothing(script, database, capsys):
    before = file_hash(database)

    code = run_with(script, database, "--dry-run")
    output = capsys.readouterr()

    assert code == 0
    assert file_hash(database) == before
    assert sorted(p.name for p in database.parent.iterdir()) == ["fundos.db"]
    assert "    FIC-FIDC: 1" in output.out
    assert "    em revisao manual: 2" in output.out
    assert "    nao classificado: 1" in output.out
    assert "    dentro_da_tolerancia: 1" in output.out
    assert "  Entrariam agora: 2" in output.out
    assert "Cruzamento faixa da classificacao x estado da conferencia (assuntos):" in output.out
    assert "Dry-run concluido: nenhum banco foi alterado." in output.out
    assert_no_secret(output.out + output.err)


def test_commit_enqueues_once_with_backup(script, database, tmp_path, capsys):
    backup_dir = tmp_path / "bk"

    first = run_with(script, database, "--commit", "--backup-dir", str(backup_dir))
    first_output = capsys.readouterr()
    after_first = file_hash(database)
    second = run_with(script, database, "--commit", "--backup-dir", str(backup_dir))
    second_output = capsys.readouterr()
    dry = run_with(script, database, "--dry-run")
    dry_output = capsys.readouterr()

    assert (first, second, dry) == (0, 0, 0)
    assert len(backups_in(backup_dir)) == 1
    assert "  Gravadas agora: 2" in first_output.out
    assert "  integrity_check: ok" in first_output.out
    assert "Fila gravada." in first_output.out
    assert query(database, "SELECT COUNT(*) FROM audit_log") == [(2,)]
    assert "Nada a enfileirar: nenhum assunto novo em revisao manual" in second_output.out
    assert file_hash(database) == after_first
    assert "  Entrariam agora: 0" in dry_output.out
    assert "  Ja na fila nesta competencia: 2 assunto(s)" in dry_output.out

    for output in (first_output, second_output, dry_output):
        assert_no_secret(output.out + output.err)


def test_competence_without_the_informe(script, database, tmp_path, capsys):
    backup_dir = tmp_path / "bk"
    before = file_hash(database)

    dry = run_with(script, database, "--dry-run", reference=OCT)
    dry_output = capsys.readouterr()
    commit = run_with(script, database, "--commit", "--backup-dir", str(backup_dir), reference=OCT)
    commit_output = capsys.readouterr()

    assert (dry, commit) == (0, 0)
    assert "sem dado nesta competencia" in dry_output.out
    assert "Nada a enfileirar: o informe de FIDC nao tem esta competencia" in commit_output.out
    assert not backup_dir.exists()
    assert file_hash(database) == before


@pytest.mark.parametrize("mode", ["--dry-run", "--commit"])
def test_network_database_is_refused(script, tmp_path, monkeypatch, mode, capsys):
    monkeypatch.setattr(script, "open_read_only", None)

    code = run_with(script, NETWORK_DATABASE, mode, "--backup-dir", str(tmp_path / "bk"))
    captured = capsys.readouterr()

    assert code == 1
    assert "--database em caminho de rede (UNC)" in captured.err
    assert "servidor" not in captured.out + captured.err
    assert not (tmp_path / "bk").exists()


@pytest.mark.parametrize("mode", ["--dry-run", "--commit"])
def test_network_backup_dir_is_refused(script, database, mode, capsys):
    before = file_hash(database)

    code = run_with(script, database, mode, "--backup-dir", NETWORK_BACKUP_DIR)
    captured = capsys.readouterr()

    assert code == 1
    assert "--backup-dir em caminho de rede (UNC)" in captured.err
    assert "servidor" not in captured.out + captured.err
    assert file_hash(database) == before


def test_remote_drive_and_long_backup_are_refused_in_the_dry_run(
    script, database, tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(
        backup, "_drive_type", lambda drive: backup.REMOTE_DRIVE if drive.upper() == "L:" else 3
    )

    remote = run_with(script, "L:\\pasta\\fundos.db", "--dry-run")
    first = capsys.readouterr()
    long_backup = run_with(script, database, "--dry-run", "--backup-dir", str(tmp_path / ("b" * 255)))
    second = capsys.readouterr()

    assert remote == 1
    assert "--database em caminho de rede (unidade remota)" in first.err
    assert long_backup == 1
    assert "caminho longo" in second.err


def test_wal_database_is_refused(script, database, capsys):
    connection = sqlite3.connect(database)

    try:
        assert connection.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
    finally:
        connection.close()

    code = run_with(script, database, "--dry-run")
    captured = capsys.readouterr()

    assert code == 1
    assert "WAL recusado" in captured.err


def test_missing_database_creates_nothing(script, tmp_path, capsys):
    path = tmp_path / "novo" / "fundos.db"

    code = run_with(script, path, "--commit")
    captured = capsys.readouterr()

    assert code == 1
    assert "Banco nao encontrado; nada foi criado." in captured.err
    assert not path.parent.exists()


def test_database_without_the_informe_migrations(script, tmp_path, capsys):
    path = tmp_path / "fundos.db"
    create_schema(path)

    code = run_with(script, path, "--dry-run")
    captured = capsys.readouterr()

    assert code == 1
    assert "Banco sem as migrations: 002_party_observations, 003_party_observation_shares." in captured.err


def test_unexpected_error_prints_only_the_type(script, database, monkeypatch, capsys):
    def broken(*args, **kwargs):
        raise RuntimeError("valor de linha ficticio " + COTAS[0])

    monkeypatch.setattr(script, "classify", broken)

    code = run_with(script, database, "--dry-run")
    captured = capsys.readouterr()

    assert code == 1
    assert "Erro inesperado na classificacao de FIC-FIDC: RuntimeError" in captured.err
    assert "valor de linha" not in captured.err
    assert COTAS[0] not in captured.out + captured.err


def test_check_report_counts_holders_by_type_without_concluding(full_connection):
    informe = SyntheticFicFidc(full_connection)
    holder = informe.typed_class(1)
    informe.put_ratio(holder, "50", "100")
    informe.holding(holder, informe.investee(1), "50")

    lines = format_check_report(cda_vs_informe(full_connection, SEP), SEP, (SEP,))
    text = "\n".join(lines)

    assert "    FIDC: 1 detentor(es), 1 linha(s)" in text
    assert "    FIAGRO: 0 detentor(es), 0 linha(s)" in text
    assert "nao aparece" not in text
    assert "sem concluir a causa de um 0" in text


def test_cross_report_counts_band_against_state(full_connection):
    informe = SyntheticFicFidc(full_connection)
    fic = informe.typed_class(1)
    informe.put_ratio(fic, "96", "100")
    informe.holding(fic, informe.investee(1), "96")
    review = informe.typed_class(2)
    informe.put_ratio(review, "80", "100")
    informe.holding(review, informe.investee(2), "60")
    informe.put_ratio(informe.typed_class(3), "10", "100")
    fiagro = informe.typed_class(4, kind=FIAGRO, fund_kind=FIAGRO)
    informe.holding(fiagro, informe.investee(3), "5")

    lines = format_cross_report(classify(full_connection, SEP), cda_vs_informe(full_connection, SEP))

    assert lines == [
        "Cruzamento faixa da classificacao x estado da conferencia (assuntos):",
        "  FIC-FIDC: dentro_da_tolerancia 1; fora_da_tolerancia 0",
        "  em revisao manual: dentro_da_tolerancia 0; fora_da_tolerancia 1",
        "  nao classificado: dentro_da_tolerancia 0; fora_da_tolerancia 0; "
        "sem_dado/sem_posicao_em_cotas_no_cda 1",
        "  sem dado: dentro_da_tolerancia 0; fora_da_tolerancia 0",
        "  sem classificacao (assunto so no CDA): dentro_da_tolerancia 0; "
        "fora_da_tolerancia 0; sem_dado/sem_informe_na_competencia 1",
    ]
