import hashlib
import importlib.util
import pathlib
import sqlite3

import pytest

from apoio import make_test_cnpj
from apoio_quota_classes import SEP
from apoio_quota_classes import SyntheticSeries
from conftest import create_full_schema
from conftest import create_schema
from fundos import backup
from fundos.indicators.subordinacao import PL
from fundos.indicators.subordinacao import subordinacao
from fundos.indicators.subordinacao_report import format_subordinacao_report


PROJECT_DIR = pathlib.Path(__file__).resolve().parent.parent
SCRIPT_PATH = PROJECT_DIR / "scripts" / "report_subordinacao.py"

NETWORK_DATABASE = "\\\\servidor\\pasta\\fundos.db"
# Valores ficticios que nao podem aparecer na saida (so contagens).
VALUES = ("7351", "2649", "6113")


def load_script():
    specification = importlib.util.spec_from_file_location("report_subordinacao", SCRIPT_PATH)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


@pytest.fixture
def script():
    return load_script()


def populate(connection):
    """Classe 1: senior e subordinada, fecha com o PL; classe 2: so senior, PL
    fora de 1%; classe 3: rotulo fora do molde; classe 4: tab_I sem tab_X_2."""

    informe = SyntheticSeries(connection)
    _, first = informe.fund_and_class(1)
    informe.series(first, "Subclasse Senior", quantity=VALUES[0], unit_value="1")
    informe.series(first, "Subclasse Subordinada Subordinada 1 |", quantity=VALUES[1], unit_value="1")
    informe.put(first, {PL: "10000"})
    _, second = informe.fund_and_class(2)
    informe.series(second, "Subclasse Senior", quantity=VALUES[2], unit_value="1")
    informe.put(second, {PL: "1"})
    _, third = informe.fund_and_class(3)
    informe.series(third, "Cota Unica Ficticia")
    _, fourth = informe.fund_and_class(4)
    informe.put(fourth, {"tab_I.TAB_I_VL_ATIVO": "100"})


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "fundos.db"
    connection = create_full_schema(path).connect()

    try:
        populate(connection)
    finally:
        connection.close()

    return path


def file_hash(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def assert_no_secret(text):
    text = "\n".join(line for line in text.splitlines() if not line.startswith("Pacote fundos:"))

    for n in range(1, 5):
        assert make_test_cnpj(n) not in text

    for value in VALUES:
        assert value not in text

    assert "servidor" not in text
    assert "Cota Unica Ficticia" not in text


def test_report_shows_only_counts_and_changes_nothing(script, database, capsys):
    before = file_hash(database)

    code = script.main(["--database", str(database), "--reference-date", SEP])
    captured = capsys.readouterr()

    assert code == 0
    assert file_hash(database) == before
    assert sorted(p.name for p in database.parent.iterdir()) == ["fundos.db"]
    assert "  Assuntos: 4" in captured.out
    assert "    calculado: 2" in captured.out
    assert "      sem_dado/rotulo_nao_mapeado: 1" in captured.out
    assert "      sem_dado/sem_tab_X_2_na_competencia: 1" in captured.out
    assert "    sem_serie_subordinada: 1" in captured.out
    assert "    soma_fora_de_1pct_do_pl: 1" in captured.out
    assert "dentro_de_1pct 1; fora_de_1pct 1; pl_ausente 0; pl_nao_positivo 0" in captured.out
    assert "  Assuntos calculados com uma so serie, senior: 1" in captured.out
    assert "Relatorio concluido: nenhum banco foi alterado." in captured.out
    assert_no_secret(captured.out + captured.err)


def test_bands_and_division_follow_the_closing_subjects(full_connection):
    populate(full_connection)

    text = "\n".join(format_subordinacao_report(subordinacao(full_connection, SEP), SEP))

    # So a classe 1 fecha com o PL, com 2 series: 26,49% em subordinada.
    assert "com 2 ou mais series; 1 assunto(s)): 0 0; abaixo de 5% 0; de 5% a 10% 0; de 10% a 20% 0; de 20% a 30% 1" in text
    assert (
        "1 assunto(s)): senior 73.5%; mezanino 0.0%; subordinada 26.5%; subtipo_ausente 0.0%;"
        " subordinada e subtipo ausente juntos 26.5%"
    ) in text


def test_arguments_are_required(script):
    for arguments in (
        ["--database", "x.db"],
        ["--database", "x.db", "--reference-date", "2026-09-29"],
        ["--reference-date", SEP],
    ):
        with pytest.raises(SystemExit) as error:
            script.main(arguments)

        assert error.value.code == 2


def test_refuses_network_remote_and_long_paths(script, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(script, "open_read_only", None)
    monkeypatch.setattr(
        backup, "_drive_type", lambda drive: backup.REMOTE_DRIVE if drive.upper() == "L:" else 3
    )

    network = script.main(["--database", NETWORK_DATABASE, "--reference-date", SEP])
    first = capsys.readouterr()
    remote = script.main(["--database", "L:\\pasta\\fundos.db", "--reference-date", SEP])
    second = capsys.readouterr()
    long_path = script.main(["--database", str(tmp_path / ("b" * 255) / "fundos.db"), "--reference-date", SEP])
    third = capsys.readouterr()

    assert (network, remote, long_path) == (1, 1, 1)
    assert "--database em caminho de rede (UNC)" in first.err
    assert "--database em caminho de rede (unidade remota)" in second.err
    assert "caminho longo" in third.err
    assert "servidor" not in first.out + first.err


def test_refuses_wal_missing_migration_and_missing_database(script, database, tmp_path, capsys):
    only_001 = tmp_path / "so_001.db"
    create_schema(only_001)
    missing = script.main(["--database", str(only_001), "--reference-date", SEP])
    first = capsys.readouterr()
    absent = script.main(["--database", str(tmp_path / "novo" / "fundos.db"), "--reference-date", SEP])
    second = capsys.readouterr()
    connection = sqlite3.connect(database)

    try:
        connection.execute("PRAGMA journal_mode=WAL")
    finally:
        connection.close()

    wal = script.main(["--database", str(database), "--reference-date", SEP])
    third = capsys.readouterr()

    assert (missing, absent, wal) == (1, 1, 1)
    assert "Banco sem as migrations: 006_quota_class_map." in first.err
    assert "Banco nao encontrado; nada foi criado." in second.err
    assert not (tmp_path / "novo").exists()
    assert "WAL recusado" in third.err


def test_unexpected_error_prints_only_the_type(script, database, monkeypatch, capsys):
    def broken(*args, **kwargs):
        raise RuntimeError("valor de linha ficticio " + VALUES[0])

    monkeypatch.setattr(script, "subordinacao", broken)

    code = script.main(["--database", str(database), "--reference-date", SEP])
    captured = capsys.readouterr()

    assert code == 1
    assert "Erro inesperado no relatorio da subordinacao: RuntimeError" in captured.err
    assert VALUES[0] not in captured.out + captured.err
