import hashlib
import importlib.util
import pathlib
import re
import sqlite3
from decimal import Decimal

import pytest

from apoio import make_test_cnpj
from apoio_quota_classes import SyntheticSeries
from conftest import create_full_schema
from fundos import backup
from fundos.indicators.desempenho import EXPECTED
from fundos.indicators.desempenho import REALIZED
from fundos.indicators.desempenho import RETURN
from fundos.indicators.desempenho import desempenho
from fundos.indicators.desempenho_report import INTERVALS
from fundos.indicators.desempenho_report import format_desempenho_report
from fundos.indicators.desempenho_report import interval
from fundos.indicators.liquidez import fields as liquidity_fields
from fundos.indicators.liquidez import liquidez
from fundos.indicators.rentabilidade import rentabilidade


PROJECT_DIR = pathlib.Path(__file__).resolve().parent.parent
SCRIPT_PATH = PROJECT_DIR / "scripts" / "report_desempenho.py"

SEP = "2026-09-30"
AUG = "2026-08-31"
NETWORK_DATABASE = "\\\\servidor\\pasta\\fundos.db"
# Valores ficticios que nao podem aparecer na saida (so contagens).
VALUES = ("7351", "2649", "6113")
LABEL = "Serie Ficticia Unica"


def load_script():
    specification = importlib.util.spec_from_file_location("report_desempenho", SCRIPT_PATH)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


@pytest.fixture
def script():
    return load_script()


def populate(connection):
    """Classe 1: liquidez com valor e serie com o realizado igual a tab_X_3;
    classe 2: liquidez toda 0, esperado 0 e realizado diferente da tab_X_3;
    classe 3: so a tab_I."""

    informe = SyntheticSeries(connection)
    _, first = informe.fund_and_class(1)
    informe.put(first, dict(zip(liquidity_fields(), (VALUES[0], "0", "0", "0", "0", "0", VALUES[1]))))
    first_series = informe.series(first, LABEL, quantity=None, unit_value=None)

    for field_name, value in ((EXPECTED, "1.1"), (REALIZED, "1.5"), (RETURN, "1.5")):
        informe.series_field(first_series, field_name, value)

    _, second = informe.fund_and_class(2)
    informe.put(second, dict(zip(liquidity_fields(), ["0"] * 7)))
    second_series = informe.series(second, "Subclasse Senior Serie 1", quantity=None, unit_value=None)

    for field_name, value in ((EXPECTED, "0"), (REALIZED, "-12"), (RETURN, VALUES[2])):
        informe.series_field(second_series, field_name, value)

    _, third = informe.fund_and_class(3)
    informe.put(third, {"tab_I.TAB_I_VL_ATIVO": "100"})


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

    for n in range(1, 4):
        assert make_test_cnpj(n) not in text

    for value in VALUES:
        assert value not in text

    assert "servidor" not in text
    assert LABEL not in text and LABEL.lower() not in text
    assert "%" not in text
    assert re.search(r"\balt[oa]s?\b|\bbaix[oa]s?\b|\bbo[am]\b|\bruim\b", text, re.IGNORECASE) is None


def test_report_shows_only_counts_and_changes_nothing(script, database, capsys):
    before = file_hash(database)

    code = script.main(["--database", str(database), "--reference-date", SEP])
    captured = capsys.readouterr()
    out = captured.out

    assert code == 0
    assert file_hash(database) == before
    assert sorted(p.name for p in database.parent.iterdir()) == ["fundos.db"]
    assert "  Nota: Suplemento G, item X.5: preenchimento compulsorio apenas para os fundos abertos" in out
    assert "    Ativos com liquidez imediata: maior que 0 1; igual a 0 1; menor que 0 0; sem_dado 0" in out
    assert "    todas_as_faixas_zero: 1" in out
    assert "  Assuntos: 2; series: 2" in out
    assert "  Unidade: unidade nao confirmada; o valor e mostrado como informado" in out
    assert "  Intervalos de contagem do valor, sem limiar: menos de -10 0; de -10 a menos de 0 0; igual a 0 0; mais de 0 ate 1 0; mais de 1 ate 2 1; mais de 2 ate 10 0; mais de 10 1" in out
    assert "  Esperado: maior que 0 1; igual a 0 1; menor que 0 0; sem_dado 0" in out
    assert "  Intervalos de contagem do realizado, sem limiar: menos de -10 1; " in out
    assert "da mesma serie: igual 1; diferente 1; sem tab_X_3 0; algum sem dado 0" in out
    assert "    esperado_informado_zero: 1" in out
    assert "    realizado_difere_da_rentabilidade: 1" in out
    assert "(Suplemento G, correspondencia pelo nome do campo)" in out
    assert "  Nada e calculado entre o esperado e o realizado." in out
    assert "Relatorio concluido: nenhum banco foi alterado." in out
    assert_no_secret(captured.out + captured.err)


def test_intervals_are_only_for_counting():
    assert [interval(Decimal(value)) for value in ("-10.01", "-10", "-0.01", "0", "1", "1.01", "2", "10", "10.01")] == [
        INTERVALS[0], INTERVALS[1], INTERVALS[1], INTERVALS[2], INTERVALS[3], INTERVALS[4], INTERVALS[4], INTERVALS[5], INTERVALS[6]
    ]


def test_empty_competence_reports_zero(full_connection):
    populate(full_connection)

    text = "\n".join(
        format_desempenho_report(
            liquidez(full_connection, AUG), rentabilidade(full_connection, AUG), desempenho(full_connection, AUG), AUG
        )
    )

    assert "  Assuntos: 0" in text
    assert "  Assuntos: 0; series: 0" in text
    assert_no_secret(text)


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
    without = tmp_path / "sem_migration.db"
    plain = sqlite3.connect(without)

    try:
        plain.execute("CREATE TABLE vazia (id INTEGER)")
        plain.commit()
    finally:
        plain.close()

    missing = script.main(["--database", str(without), "--reference-date", SEP])
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
    assert "Banco sem as migrations: 001_initial_schema." in first.err
    assert "Banco nao encontrado; nada foi criado." in second.err
    assert not (tmp_path / "novo").exists()
    assert "WAL recusado" in third.err


def test_unexpected_error_prints_only_the_type(script, database, monkeypatch, capsys):
    def broken(*args, **kwargs):
        raise RuntimeError("valor de linha ficticio " + VALUES[0])

    monkeypatch.setattr(script, "desempenho", broken)

    code = script.main(["--database", str(database), "--reference-date", SEP])
    captured = capsys.readouterr()

    assert code == 1
    assert "Erro inesperado no relatorio de desempenho: RuntimeError" in captured.err
    assert VALUES[0] not in captured.out + captured.err
