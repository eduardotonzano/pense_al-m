import re
import sqlite3
from pathlib import Path

import pytest

from apoio import FAKE_CPF
from apoio import FAKE_CPF_MASKED
from apoio import insert_observation
from apoio import make_test_cnpj
from apoio import seed_base
from fundos.personal_data import FORBIDDEN_COLUMNS
from fundos.personal_data import PersonalDataError
from fundos.personal_data import check_observation
from fundos.personal_data import find_cpf_columns


SOURCE_DIR = Path(__file__).resolve().parent.parent / "src" / "fundos"
NUMERIC = make_test_cnpj(1)
ALPHANUMERIC = make_test_cnpj(1, alphanumeric=True)
IDENTIFICATION_FIELD = "tab_I.TAB_I2A12_CPF_CNPJ_CEDENTE_1"


def test_schema_has_no_cpf_column(connection):
    assert find_cpf_columns(connection) == []


def test_cpf_scanner_finds_columns_and_objects():
    connection = sqlite3.connect(":memory:")

    try:
        connection.execute("CREATE TABLE pessoas (id INTEGER, CPF_Gestor TEXT)")
        connection.execute("CREATE VIEW lista_cpf AS SELECT 1 AS x")
        found = find_cpf_columns(connection)
    finally:
        connection.close()

    assert found == ["lista_cpf", "pessoas.CPF_Gestor"]


def test_schema_has_nothing_about_house_funds(connection):
    words = ("casa", "house")
    objects = [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
        )
    ]
    tables = [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
        )
    ]
    columns = [
        column[1]
        for table in tables
        for column in connection.execute('PRAGMA table_info("' + table + '")')
    ]

    for name in objects + columns:
        assert not any(word in name.lower() for word in words), name


@pytest.mark.parametrize("column", sorted(FORBIDDEN_COLUMNS))
def test_forbidden_fields_are_refused_in_any_table_and_case(column):
    for field_name in (
        "registro_fundo." + column,
        "inf_mensal_fiagro." + column.upper(),
        "outra_tabela." + column.lower(),
    ):
        with pytest.raises(PersonalDataError, match="nao e carregado"):
            check_observation(field_name, "text", "texto generico")


@pytest.mark.parametrize("value", [FAKE_CPF, FAKE_CPF_MASKED], ids=["cpf", "cpf-mascara"])
def test_cpf_in_identification_field_is_refused(value):
    with pytest.raises(PersonalDataError, match="formato de CPF"):
        check_observation(IDENTIFICATION_FIELD, "text", value)


@pytest.mark.parametrize("value", [NUMERIC, ALPHANUMERIC], ids=["numerico", "alfanumerico"])
def test_valid_normalized_cnpj_in_identification_field_is_accepted(value):
    check_observation(IDENTIFICATION_FIELD, "text", value)
    check_observation("registro_fundo.CNPJ_Administrador", "text", value)


@pytest.mark.parametrize(
    "value",
    [
        "99.999.991/9999-" + NUMERIC[12:],
        NUMERIC[:13] + str((int(NUMERIC[13]) + 1) % 10),
        "12ABC34501DE36",
        ALPHANUMERIC.lower(),
        NUMERIC[1:],
        None,
    ],
    ids=["mascara", "dv-invalido", "dv-alfanumerico-invalido", "minuscula", "13-digitos", "ausente"],
)
def test_other_values_in_identification_field_are_refused(value):
    with pytest.raises(PersonalDataError, match="so aceita CNPJ"):
        check_observation(IDENTIFICATION_FIELD, "text", value)


def test_identification_field_needs_text_type():
    with pytest.raises(PersonalDataError):
        check_observation(IDENTIFICATION_FIELD, "numeric", NUMERIC)


def test_cpf_format_outside_identification_field_is_not_checked():
    # Fronteira documentada: a guarda olha so campos com cpf ou cnpj no nome.
    check_observation("tab_X_2.TAB_X_CLASSE_SERIE", "text", FAKE_CPF)


def test_error_message_never_contains_the_value():
    with pytest.raises(PersonalDataError) as error:
        check_observation(IDENTIFICATION_FIELD, "text", FAKE_CPF)

    assert FAKE_CPF not in str(error.value)


def insert_text(connection, base, field_name, value):
    return insert_observation(
        connection,
        subject=("class", base["fund_class"]),
        source=base["cvm"],
        run=base["cvm_run"],
        raw=base["cvm_raw"],
        field_name=field_name,
        value=value,
        value_type="text",
    )


@pytest.mark.parametrize("column", sorted(FORBIDDEN_COLUMNS))
def test_database_trigger_refuses_each_forbidden_column(connection, column):
    # Mantem a lista do trigger e a do Python em sincronia.
    base = seed_base(connection)

    with pytest.raises(sqlite3.IntegrityError, match="dado pessoal"):
        insert_text(connection, base, "registro_fundo." + column, "texto generico")


@pytest.mark.parametrize(
    "value",
    [FAKE_CPF_MASKED, FAKE_CPF, ALPHANUMERIC.lower(), ALPHANUMERIC[:12] + "3A"],
    ids=["cpf-mascara-14-caracteres", "cpf", "minuscula", "letra-no-dv"],
)
def test_database_trigger_refuses_values_outside_cnpj_format(connection, value):
    base = seed_base(connection)

    with pytest.raises(sqlite3.IntegrityError, match="formato de CNPJ"):
        insert_text(connection, base, IDENTIFICATION_FIELD, value)


@pytest.mark.parametrize("value", [NUMERIC, ALPHANUMERIC], ids=["numerico", "alfanumerico"])
def test_database_trigger_accepts_cnpj_format(connection, value):
    base = seed_base(connection)

    insert_text(connection, base, IDENTIFICATION_FIELD, value)

    assert connection.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 1


def test_module_does_not_import_network_libraries():
    pattern = re.compile(
        r"^\s*(import|from)\s+(requests|urllib|http|socket|ftplib|smtplib)\b",
        re.MULTILINE,
    )
    offenders = [
        str(path)
        for path in SOURCE_DIR.rglob("*.py")
        if pattern.search(path.read_text(encoding="utf-8"))
    ]

    assert offenders == []
