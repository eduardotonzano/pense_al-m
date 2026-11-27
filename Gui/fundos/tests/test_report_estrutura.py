import hashlib
import importlib.util
import pathlib
import re
import sqlite3
from decimal import Decimal

import pytest

from apoio import make_test_cnpj
from apoio_indicadores import SyntheticInforme
from conftest import create_full_schema
from fundos import backup
from fundos.indicators.estrutura_report import HHI_INTERVALS
from fundos.indicators.estrutura_report import LARGEST_INTERVALS
from fundos.indicators.estrutura_report import format_estrutura_report
from fundos.indicators.estrutura_report import interval
from fundos.indicators.garantias import PERCENT
from fundos.indicators.garantias import VALUE
from fundos.indicators.garantias import garantias
from fundos.indicators.segmentos import SEGMENTS
from fundos.indicators.segmentos import TOTAL
from fundos.indicators.segmentos import carteira_por_segmento
from fundos.indicators.segmentos import fields


PROJECT_DIR = pathlib.Path(__file__).resolve().parent.parent
SCRIPT_PATH = PROJECT_DIR / "scripts" / "report_estrutura.py"

SEP = "2026-09-30"
AUG = "2026-08-31"
NETWORK_DATABASE = "\\\\servidor\\pasta\\fundos.db"
# Valores ficticios que nao podem aparecer na saida (so contagens).
VALUES = ("7351", "2649", "6113")
FIELD = {item: name for item, _, name, _ in SEGMENTS}
F8 = "tab_II.TAB_II_F8_VL_OUTRO"
CORRESPONDENCE = "(Suplemento G, correspondencia pelo nome do campo)"


def load_script():
    specification = importlib.util.spec_from_file_location("report_estrutura", SCRIPT_PATH)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


@pytest.fixture
def script():
    return load_script()


def tab_ii(segments, total=None, extra=None):
    """Linha da tab_II com os segmentos dados e o resto 0 (valores ficticios)."""

    values = {name: "0" for name in fields()}
    values.update({FIELD[item]: value for item, value in segments.items()})
    values.update(extra or {})
    values[TOTAL] = total or str(sum(Decimal(value) for value in segments.values()))
    return values


def populate(connection):
    """Classe 1: dois segmentos (um deles com "Outros") e garantia com valor;
    classe 2: total 0 e garantia 0 e 0; classe 3: segmento negativo e
    percentual acima de 100; classe 4: so a tab_I."""

    informe = SyntheticInforme(connection)
    _, first = informe.fund_and_class(1)
    informe.put(first, tab_ii({"II.a": VALUES[0], "II.f": VALUES[1]}, extra={F8: VALUES[1]}))
    informe.put(first, {VALUE: VALUES[2], PERCENT: "40"})
    _, second = informe.fund_and_class(2)
    informe.put(second, tab_ii({}))
    informe.put(second, {VALUE: "0", PERCENT: "0"})
    _, third = informe.fund_and_class(3)
    informe.put(third, tab_ii({"II.b": "150", "II.k": "-50"}))
    informe.put(third, {VALUE: "10", PERCENT: "120"})
    _, fourth = informe.fund_and_class(4)
    informe.put(fourth, {"tab_I.TAB_I2_VL_CARTEIRA": "100"})


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
    assert re.search(r"\balt[oa]s?\b|\bbaix[oa]s?\b", text, re.IGNORECASE) is None


def test_report_shows_only_counts_and_changes_nothing(script, database, capsys):
    before = file_hash(database)

    code = script.main(["--database", str(database), "--reference-date", SEP])
    captured = capsys.readouterr()
    out = captured.out

    assert code == 0
    assert file_hash(database) == before
    assert sorted(p.name for p in database.parent.iterdir()) == ["fundos.db"]
    assert "  Assuntos: 3" in out
    assert "    calculado: 2" in out
    assert "      sem_dado/denominador_zero: 1" in out
    assert "    segmento_negativo: 1" in out
    assert "    com_outros: 1" in out
    assert "(calculados; 2 assunto(s)): 0 0; 1 0; 2 2; 3 0; 4 0; 5 ou mais 0" in out
    assert "sem limiar (calculados sem segmento negativo; 1 assunto(s)): 100% ou mais 0; de 90% a menos de 100% 0" in out
    assert "; de 50% a menos de 90% 1; menos de 50% 0" in out
    assert "10.000 ou mais 0; de 5.000 a menos de 10.000 1; de 2.500 a menos de 5.000 0; menos de 2.500 0" in out
    assert "    II.a Industrial: 1" in out
    assert "    II.k Propriedade Intelectual e Marcas & Patentes: 0" in out
    assert "  Assuntos com a linha: 3" in out
    assert "  Valor (7.1): maior que 0 2; igual a 0 1; negativo 0; sem_dado 0" in out
    assert "  Percentual (7.2): igual a 0 1; maior que 0 e ate 100 1; acima de 100 1; negativo 0; sem_dado 0" in out
    assert "    garantia_informada_zero: 1" in out
    assert "    percentual_acima_de_100: 1" in out
    assert "  7.1 tab_X_7.TAB_X_VL_GARANTIA_DIRCRED: Valor total das garantias vinculadas aos direitos creditorios " + CORRESPONDENCE in out
    assert "  7.2 tab_X_7.TAB_X_PR_GARANTIA_DIRCRED: Percentual dos direitos creditorios com garantias vinculadas " + CORRESPONDENCE in out
    assert "  O percentual e informado; nao e calculado a partir do valor." in out
    assert "Subordinacao (D4): veja scripts/report_subordinacao.py." in out
    assert "Relatorio concluido: nenhum banco foi alterado." in out
    assert_no_secret(captured.out + captured.err)


def test_intervals_are_only_for_counting():
    assert interval(Decimal(10000), HHI_INTERVALS) == "10.000 ou mais"
    assert interval(Decimal("9999.99"), HHI_INTERVALS) == "de 5.000 a menos de 10.000"
    assert interval(Decimal(2500), HHI_INTERVALS) == "de 2.500 a menos de 5.000"
    assert interval(Decimal(0), HHI_INTERVALS) == "menos de 2.500"
    assert interval(Decimal(100), LARGEST_INTERVALS) == "100% ou mais"
    assert interval(Decimal("49.99"), LARGEST_INTERVALS) == "menos de 50%"


def test_empty_competence_reports_zero_subjects(full_connection):
    populate(full_connection)

    lines = format_estrutura_report(
        carteira_por_segmento(full_connection, AUG), garantias(full_connection, AUG), AUG
    )
    text = "\n".join(lines)

    assert "  Assuntos: 0" in text
    assert "  Assuntos com a linha: 0" in text
    assert "    II.a Industrial: 0" in text
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

    monkeypatch.setattr(script, "garantias", broken)

    code = script.main(["--database", str(database), "--reference-date", SEP])
    captured = capsys.readouterr()

    assert code == 1
    assert "Erro inesperado no relatorio de estrutura: RuntimeError" in captured.err
    assert VALUES[0] not in captured.out + captured.err
