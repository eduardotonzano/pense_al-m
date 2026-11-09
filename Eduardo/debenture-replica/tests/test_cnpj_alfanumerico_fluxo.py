"""CNPJ alfanumerico no codigo: repositorio, parser do SND, ingestao e lote.

So dados ficticios (tests/cnpj_amostras.py). Os bancos ficam em tmp_path:
os de 001 a 003 sao criados pelo scripts/apply_migration.py, como em
producao; o de 001 e 002 mostra por que a 003 tem de vir antes.

Opcao B do ADR-011 nas debentures: o parser devolve o CNPJ no formato
12 + 2 sem conferir o DV, e o IssuerRepository recusa o DV invalido. O
documento falha de forma visivel e os outros do lote seguem.
"""

import importlib.util
import pathlib
from types import SimpleNamespace

import pytest

from cnpj_amostras import (
    CNPJ_1,
    CNPJ_ALFA_1,
    com_mascara,
    dv_errado,
)
from debenture_search.database import Database
from debenture_search.parsers.snd_parser import SndParser
from debenture_search.parsers.snd_tabular_parser import SndTabularParser
from debenture_search.repositories.issuer_repository import IssuerRepository
from debenture_search.services.snd_batch_import_service import (
    SndBatchImportService,
)
from debenture_search.services.snd_import_service import SndImportService


PROJECT_DIR = pathlib.Path(__file__).resolve().parent.parent
SCRIPT_PATH = PROJECT_DIR / "scripts" / "apply_migration.py"
MIGRATIONS_DIR = PROJECT_DIR / "migrations"
FIXTURES_DIR = PROJECT_DIR / "tests" / "fixtures"
HTML_FIXTURE = FIXTURES_DIR / "snd_caracteristicas_exemplo.html"
TABULAR_FIXTURE = FIXTURES_DIR / "snd_caracteristicas_tabular_exemplo.txt"

# O CNPJ da fixture HTML (99.999.991/9999-04).
HTML_FIXTURE_CNPJ = com_mascara(CNPJ_1)


def load_apply_migration():
    specification = importlib.util.spec_from_file_location(
        "apply_migration",
        SCRIPT_PATH,
    )
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


@pytest.fixture
def db(tmp_path, capsys):
    """Banco novo com as migrations 001 a 003, pelo apply_migration.py."""

    path = tmp_path / "debentures.db"
    code = load_apply_migration().main(
        ["--database", str(path), "--create", "--commit"]
    )
    capsys.readouterr()

    assert code == 0

    database = Database(path)
    versions = database.fetch_all(
        "SELECT version FROM schema_migrations ORDER BY version"
    )
    assert [row["version"] for row in versions] == [1, 2, 3]

    return database


def count(db, table):
    return db.fetch_one("SELECT COUNT(*) AS total FROM " + table)["total"]


def html_with_cnpj(value):
    document = HTML_FIXTURE.read_text(encoding="utf-8")
    assert document.count(HTML_FIXTURE_CNPJ) == 1
    return document.replace(HTML_FIXTURE_CNPJ, value)


def tabular_with_cnpj(value):
    document = TABULAR_FIXTURE.read_text(encoding="utf-8")
    # O valor atual e lido do proprio arquivo: o teste nao repete CNPJ.
    rows = SndTabularParser.read_rows(document)
    assert len(rows) == 1
    current = SndTabularParser.map_record(rows[0])["issuer_cnpj"].strip()
    assert document.count(current) == 1
    return document.replace(current, value)


def other_asset(document):
    """O mesmo documento HTML para outro ativo (outro codigo e ISIN)."""

    assert document.count("EXMP12") == 1
    assert document.count("BREXMPDBS001") == 1
    return document.replace("EXMP12", "EXMP13").replace(
        "BREXMPDBS001",
        "BREXMPDBS002",
    )


# Repositorio.


def test_repository_creates_and_finds_alphanumeric_issuer(db):
    repository = IssuerRepository(db)

    created = repository.create(
        legal_name="Emissora Alfanumerica Ficticia S.A.",
        cnpj=com_mascara(CNPJ_ALFA_1).lower(),
    )

    assert created.cnpj == CNPJ_ALFA_1
    assert repository.get_by_cnpj(com_mascara(CNPJ_ALFA_1)).id == created.id

    found, was_created = repository.get_or_create(
        legal_name="Nome que nao deve substituir",
        cnpj=CNPJ_ALFA_1.lower(),
    )

    assert was_created is False
    assert found.id == created.id
    assert found.legal_name == "Emissora Alfanumerica Ficticia S.A."

    with pytest.raises(ValueError, match="Ja existe um emissor"):
        repository.create(legal_name="Duplicada", cnpj=CNPJ_ALFA_1)

    assert repository.count() == 1


@pytest.mark.parametrize(
    "cnpj",
    [CNPJ_1, CNPJ_ALFA_1],
    ids=["numerico", "alfanumerico"],
)
def test_repository_rejects_invalid_check_digit(db, cnpj):
    repository = IssuerRepository(db)
    wrong = dv_errado(cnpj)

    with pytest.raises(ValueError, match="digito verificador"):
        repository.create(legal_name="Emissora", cnpj=wrong)

    with pytest.raises(ValueError, match="digito verificador"):
        repository.get_or_create(legal_name="Emissora", cnpj=wrong)

    # Como no get_by_identifier da camada: buscar com DV invalido e erro.
    with pytest.raises(ValueError, match="digito verificador"):
        repository.get_by_cnpj(com_mascara(wrong))

    assert repository.count() == 0


# Parser do SND.


@pytest.mark.parametrize(
    "value, expected",
    [
        (com_mascara(CNPJ_ALFA_1), CNPJ_ALFA_1),
        (com_mascara(CNPJ_ALFA_1).lower(), CNPJ_ALFA_1),
        (CNPJ_ALFA_1, CNPJ_ALFA_1),
        (com_mascara(dv_errado(CNPJ_1)), dv_errado(CNPJ_1)),
        ("00.000.000/0000-00", "00000000000000"),
    ],
    ids=[
        "alfanumerico-mascara",
        "alfanumerico-minuscula",
        "alfanumerico-sem-mascara",
        "dv-errado-segue-para-o-repositorio",
        "caracteres-iguais-seguem-para-o-repositorio",
    ],
)
def test_html_parser_returns_the_canonical_format(value, expected):
    parsed = SndParser.parse(html_with_cnpj(value))

    assert parsed.issuer_cnpj == expected


@pytest.mark.parametrize(
    "value",
    [
        "Nao informado",
        com_mascara(CNPJ_1)[:-3],
        CNPJ_ALFA_1[:12] + "4A",
        com_mascara(CNPJ_ALFA_1) + " (matriz)",
    ],
    ids=["texto", "12-caracteres", "letra-no-dv", "texto-junto"],
)
def test_html_parser_returns_none_outside_the_format(value):
    parsed = SndParser.parse(html_with_cnpj(value))

    assert parsed.asset_code == "EXMP12"
    assert parsed.issuer_cnpj is None


def test_normalize_cnpj_without_value_is_none():
    assert SndParser.normalize_cnpj(None) is None
    assert SndParser.normalize_cnpj("") is None
    assert SndParser.normalize_cnpj("   ") is None


@pytest.mark.parametrize(
    "value",
    [CNPJ_ALFA_1, com_mascara(CNPJ_ALFA_1).lower()],
    ids=["sem-mascara", "minuscula-mascara"],
)
def test_tabular_parser_returns_alphanumeric_cnpj(value):
    parsed = SndTabularParser.parse(tabular_with_cnpj(value), "PETR27")

    assert parsed.issuer_cnpj == CNPJ_ALFA_1


# Ingestao.


def issuer_cnpj_observations(db, debenture_id):
    rows = db.fetch_all(
        """
        SELECT value_text
        FROM observations
        WHERE debenture_id = ? AND field_name = 'cnpj_emissor'
        """,
        (debenture_id,),
    )
    return [row["value_text"] for row in rows]


def test_html_import_records_alphanumeric_cnpj(db):
    service = SndImportService(db)
    document = html_with_cnpj(com_mascara(CNPJ_ALFA_1).lower())

    first = service.import_html(document)
    second = service.import_html(document)

    issuer = db.fetch_one(
        "SELECT cnpj FROM issuers WHERE id = ?",
        (first.issuer_id,),
    )

    assert issuer["cnpj"] == CNPJ_ALFA_1
    assert issuer_cnpj_observations(db, first.debenture_id) == [CNPJ_ALFA_1]
    assert second.issuer_id == first.issuer_id
    assert count(db, "issuers") == 1
    assert db.foreign_key_check() == []


def test_tabular_import_records_alphanumeric_cnpj(db):
    result = SndImportService(db).import_document(
        tabular_with_cnpj(CNPJ_ALFA_1),
        asset_code="PETR27",
        content_type="text/plain",
    )

    issuer = db.fetch_one(
        "SELECT cnpj FROM issuers WHERE id = ?",
        (result.issuer_id,),
    )

    assert issuer["cnpj"] == CNPJ_ALFA_1
    assert issuer_cnpj_observations(db, result.debenture_id) == [CNPJ_ALFA_1]


@pytest.mark.parametrize(
    "value, message",
    [
        (com_mascara(dv_errado(CNPJ_1)), "digito verificador"),
        (com_mascara(dv_errado(CNPJ_ALFA_1)), "digito verificador"),
        ("00.000.000/0000-00", "iguais"),
    ],
    ids=["dv-errado-numerico", "dv-errado-alfanumerico", "caracteres-iguais"],
)
def test_document_with_invalid_cnpj_fails_visibly(db, value, message):
    with pytest.raises(ValueError, match=message):
        SndImportService(db).import_html(html_with_cnpj(value))

    # Nada financeiro nasce daquele documento...
    assert count(db, "issuers") == 0
    assert count(db, "debentures") == 0
    assert count(db, "observations") == 0

    # ...mas o payload fica guardado e a coleta registra a falha.
    assert count(db, "raw_records") == 1

    run = db.fetch_one("SELECT status, error_summary FROM collection_runs")

    assert run["status"] == "failed"
    assert message in run["error_summary"]
    assert value not in run["error_summary"]
    assert SndParser.normalize_cnpj(value) not in run["error_summary"]


def test_batch_keeps_going_after_document_with_invalid_check_digit(db):
    valid = html_with_cnpj(com_mascara(CNPJ_ALFA_1))
    wrong = dv_errado(CNPJ_1)
    invalid = other_asset(html_with_cnpj(com_mascara(wrong)))
    service = SndImportService(db)

    provider = SimpleNamespace(
        normalize_asset_code=SndParser.normalize_asset_code,
        collect=lambda code: service.import_html(
            {"EXMP12": valid, "EXMP13": invalid}[code]
        ),
    )
    backup = SimpleNamespace(
        create_backup=lambda: SimpleNamespace(path=None),
    )

    result = SndBatchImportService(db, provider, backup).run(
        ["EXMP12", "EXMP13"],
        commit=True,
    )

    assert result.successes == 1
    assert result.failures == 1
    assert [item.status for item in result.items] == ["success", "failed"]

    error = result.items[1].error

    assert error == "ValueError: CNPJ com digito verificador invalido."
    assert wrong not in error

    debentures = db.fetch_all("SELECT asset_code FROM debentures")
    issuers = db.fetch_all("SELECT cnpj FROM issuers")

    assert [row["asset_code"] for row in debentures] == ["EXMP12"]
    assert [row["cnpj"] for row in issuers] == [CNPJ_ALFA_1]


# Ordem de implantacao: sem a 003, o CHECK antigo recusa o alfanumerico.


def test_without_003_alphanumeric_document_fails(tmp_path):
    database = Database(tmp_path / "sem_003.db")

    with database.connection() as connection:
        for name in ("001_initial_schema.sql", "002_debenture_events.sql"):
            connection.executescript(
                (MIGRATIONS_DIR / name).read_text(encoding="utf-8")
            )
        connection.commit()

    with pytest.raises(ValueError, match="Nao foi possivel cadastrar"):
        SndImportService(database).import_html(
            html_with_cnpj(com_mascara(CNPJ_ALFA_1))
        )

    assert count(database, "issuers") == 0
    assert count(database, "debentures") == 0
