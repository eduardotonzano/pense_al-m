import json

import pytest

from apoio import FAKE_CPF
from apoio import FAKE_CPF_MASKED
from apoio_cadastro import fake_cnpj
from apoio_cadastro import masked
from apoio_informe_fiagro import ADMIN_CNPJ
from apoio_informe_fiagro import ADMIN_NAME
from apoio_informe_fiagro import COMPETENCE
from apoio_informe_fiagro import CONTACTS
from apoio_informe_fiagro import FIRST_SUBCLASS
from apoio_informe_fiagro import FIRST_SUBCLASS_NO_SPACE
from apoio_informe_fiagro import LATER_MEMBER_DATE
from apoio_informe_fiagro import MANAGER_CNPJ
from apoio_informe_fiagro import MANAGER_NAME
from apoio_informe_fiagro import SECOND_SUBCLASS
from apoio_informe_fiagro import ZIP_NAME
from apoio_informe_fiagro import build_informe_zip
from apoio_informe_fiagro import changed
from apoio_informe_fiagro import class_row
from apoio_informe_fiagro import fake_isin
from apoio_informe_fiagro import later_zip
from apoio_informe_fiagro import load_fictitious_cadastro
from apoio_informe_fiagro import merge
from apoio_informe_fiagro import subclass_row
from apoio_informe_fiagro import subject_name
from apoio_informe_fiagro import subject_rows
from conftest import MIGRATION_001
from conftest import MIGRATIONS_DIR
from conftest import create_schema
from fundos.cadastro.loader import LoadError
from fundos.database import utc_now
from fundos.informe_fiagro import columns
from fundos.informe_fiagro.loader import ALREADY_LOADED
from fundos.informe_fiagro.loader import EMPTY_LABEL
from fundos.informe_fiagro.loader import INVALID_CNPJ
from fundos.informe_fiagro.loader import LOADED
from fundos.informe_fiagro.loader import LOWER_VERSION
from fundos.informe_fiagro.loader import NO_CLASS_ROW
from fundos.informe_fiagro.loader import NOT_FOUND
from fundos.informe_fiagro.loader import ONLY_FUND
from fundos.informe_fiagro.loader import PARSER_VERSION
from fundos.informe_fiagro.loader import REPEATED_KEY
from fundos.informe_fiagro.loader import REPEATED_SERIES
from fundos.informe_fiagro.loader import SAME_COMPETENCE
from fundos.informe_fiagro.loader import SUPERSEDED
from fundos.informe_fiagro.loader import UNKNOWN_VERSION
from fundos.informe_fiagro.loader import VERSIONED_SUBCLASS
from fundos.informe_fiagro.loader import ClassResolver
from fundos.informe_fiagro.loader import find_loaded_informe
from fundos.informe_fiagro.loader import load_informe
from fundos.informe_fiagro.loader import match_counts
from fundos.informe_fiagro.loader import reapresentation_counts
from fundos.informe_fiagro.reader import read_informe_bytes
from fundos.informe_fiagro.report import format_candidates_report
from fundos.informe_fiagro.report import format_load_report
from fundos.informe_fiagro.report import format_match_report
from fundos.informe_fiagro.report import format_reapresentation_report
from fundos.repositories.observation_repository import ObservationRepository
from fundos.repositories.party_observation_repository import PartyObservationRepository
from fundos.repositories.quota_series_repository import QuotaSeriesRepository


CLASS = columns.CLASS_TABLE
SUBCLASS = columns.SUBCLASS_TABLE

INFORME_TABLES = (
    "observations", "party_observations", "quota_series", "raw_records",
    "collection_runs", "data_conflicts", "party_conflicts",
)

# A classe tambem tem observacoes do cadastro (registro_classe.*).
FIAGRO_CLASS_ROWS = "fund_class_id = ? AND field_name LIKE 'inf_mensal_fiagro.%'"


@pytest.fixture
def loaded_db(full_db):
    """Cadastro ficticio de FIAGRO: classes 1, 2 e 3 (cada uma do seu fundo) e o fundo 9 sem classe."""

    load_fictitious_cadastro(full_db, classes=(1, 2, 3), funds_without_class=(9,))
    return full_db


def read(data=None, name=ZIP_NAME):
    return read_informe_bytes(build_informe_zip() if data is None else data, name)


def read_tables(tables):
    return read(build_informe_zip(tables))


def load(db, informe=None, progress=None, last_modified=None):
    informe = read() if informe is None else informe

    with db.transaction() as connection:
        return load_informe(connection, informe, progress=progress, last_modified=last_modified)


def rows(db, sql, parameters=()):
    with db.connection() as connection:
        return [tuple(r) for r in connection.execute(sql, parameters)]


def count(db, table, where="1 = 1", parameters=()):
    return rows(db, "SELECT COUNT(*) FROM " + table + " WHERE " + where, parameters)[0][0]


def snapshot(db):
    return {table: count(db, table) for table in INFORME_TABLES + ("funds", "fund_classes")}


def class_id(db, n):
    return rows(db, "SELECT id FROM fund_classes WHERE cnpj = ?", (fake_cnpj(n),))[0][0]


def expected_values(informe):
    return sum(len(r.values) for table in columns.TABLES for r in informe.rows(table))


def current(db, field_name, **subject):
    with db.connection() as connection:
        return ObservationRepository(connection).get_current(field_name=field_name, **subject)


def all_text(db):
    """Todo valor de texto de todas as tabelas do banco (para procurar o que nao pode estar la)."""

    found = []

    with db.connection() as connection:
        tables = [r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]

        for table in tables:
            for row in connection.execute('SELECT * FROM "' + table + '"'):
                found.extend(str(value) for value in tuple(row) if value is not None)

    return found


def run_summary(db):
    return rows(
        db,
        "SELECT status, requested_items, successful_items, failed_items, error_summary"
        " FROM collection_runs ORDER BY id DESC LIMIT 1",
    )[0]


def test_refuses_without_the_cadastro(full_db):
    with pytest.raises(LoadError, match="cadastro nao foi carregado"):
        load(full_db)

    assert count(full_db, "raw_records") == 0


def test_refuses_without_migration_002(tmp_path):
    db = create_schema(tmp_path / "fundos.db", (MIGRATION_001,))

    with pytest.raises(LoadError, match="Faltam as migrations 002_party_observations"):
        load(db)


def test_loads_class_observations_series_and_parties(loaded_db):
    informe = read()
    before = count(loaded_db, "observations")
    result = load(loaded_db, informe)
    fund_class = class_id(loaded_db, 1)

    assert result.status == "success"
    assert count(loaded_db, "observations") - before == expected_values(informe) == 122 + 2 * 3
    assert rows(
        loaded_db, "SELECT DISTINCT reference_date FROM observations WHERE field_name LIKE 'inf_mensal_fiagro%'"
    ) == [(COMPETENCE,)]
    assert count(
        loaded_db,
        "observations",
        "field_name LIKE 'inf_mensal_fiagro%' AND (field_name LIKE '%.CNPJ_Classe' OR field_name LIKE '%.Data_Referencia'"
        " OR field_name LIKE '%Administrador' OR field_name LIKE '%Gestor'"
        " OR field_name LIKE '%.Site' OR field_name LIKE '%.Servico_Atendimento_Cotista'"
        " OR field_name LIKE '%.Entidade_Administradora')",
    ) == 0
    assert current(loaded_db, "inf_mensal_fiagro.Patrimonio_Liquido", fund_class_id=fund_class).value_numeric == "1000.5"
    assert current(loaded_db, "inf_mensal_fiagro.Nome_Classe", fund_class_id=fund_class).value == subject_name(1)
    assert count(loaded_db, "observations", "field_name = 'inf_mensal_fiagro_subclasse.Nome_Classe'") == 0

    series = rows(
        loaded_db,
        "SELECT id, series_label_key, cvm_subclass_id FROM quota_series WHERE fund_class_id = ? ORDER BY id",
        (fund_class,),
    )
    assert [(key, subclass) for _, key, subclass in series] == [
        ("subclasse 1 (ou classe unica)", None),
        ("subclasse 2", None),
    ]
    assert current(loaded_db, "inf_mensal_fiagro_subclasse.Nome_Subclasse", quota_series_id=series[0][0]).value == FIRST_SUBCLASS
    assert current(loaded_db, "inf_mensal_fiagro_subclasse.Numero_Cotas", quota_series_id=series[1][0]).value_numeric == "100"
    assert rows(
        loaded_db,
        "SELECT role, field_name, party_cnpj, name_field_name, party_name FROM party_observations"
        " WHERE " + FIAGRO_CLASS_ROWS + " ORDER BY id",
        (fund_class,),
    ) == [
        ("administrador", "inf_mensal_fiagro.CNPJ_Administrador", ADMIN_CNPJ, "inf_mensal_fiagro.Nome_Administrador", ADMIN_NAME),
        ("gestor", "inf_mensal_fiagro.CNPJ_Gestor", MANAGER_CNPJ, "inf_mensal_fiagro.Nome_Gestor", MANAGER_NAME),
    ]
    assert count(loaded_db, "data_conflicts") == 0
    assert count(loaded_db, "party_conflicts") == 0
    assert result.counts[("casamento", CLASS, LOADED)] == 1
    assert result.counts[("casamento", SUBCLASS, LOADED)] == 2
    assert result.counts[("classes", LOADED)] == 1
    assert result.counts[("series", "criadas")] == 2
    assert result.counts[("papeis", "gestor", "criados")] == 1
    assert run_summary(loaded_db) == ("success", 1, 1, 0, None)


def test_manifest_has_the_parser_version_and_the_last_modified(loaded_db):
    load(loaded_db, last_modified="Sat, 24 Oct 2026 11:46:15 GMT")
    manifest = rows(
        loaded_db,
        "SELECT file_name, parent_raw_record_id IS NULL, line_count, last_modified, parser_version, processing_status"
        " FROM raw_records WHERE file_name LIKE 'inf_mensal_fiagro%' ORDER BY id",
    )

    assert manifest == [
        (ZIP_NAME, 1, None, "2026-10-24T11:46:15.000000+00:00", PARSER_VERSION, "processed"),
        ("inf_mensal_fiagro_202609.csv", 0, 1, None, PARSER_VERSION, "processed"),
        ("inf_mensal_fiagro_subclasse_202609.csv", 0, 2, None, PARSER_VERSION, "processed"),
    ]


def test_last_modified_is_optional(loaded_db):
    load(loaded_db)

    assert rows(loaded_db, "SELECT last_modified FROM raw_records WHERE file_name = ?", (ZIP_NAME,)) == [(None,)]


@pytest.mark.parametrize(
    ("value", "message"),
    (
        ("2026-10-24T11:46:15", "precisa ter fuso"),
        ("amanha", "invalida"),
        ("2099-01-01T00:00:00Z", "posterior a agora"),
    ),
)
def test_invalid_last_modified_is_refused_before_writing(loaded_db, value, message):
    before = snapshot(loaded_db)

    with pytest.raises(LoadError, match=message):
        load(loaded_db, last_modified=value)

    assert snapshot(loaded_db) == before


def repeated_class(*versions):
    """A classe 1 numa linha por Versao (a primeira com 2 subclasses, as outras com 1) e a classe 2."""

    first = subject_rows(1, Versao=versions[0])
    others = [
        subject_rows(1, labels=(FIRST_SUBCLASS,), Nome_Classe="FIAGRO Exemplo 1" + "BC"[i] + " (ficticio)", Versao=version)
        for i, version in enumerate(versions[1:])
    ]
    return merge(first, *others, subject_rows(2))


# A FU5.1 continua: mesma Versao, empate na maior ou Versao vazia nao escolhe linha.
@pytest.mark.parametrize(("versions", "different"), ((("1", "1"), 0), (("1", "2", "2"), 1), (("2", ""), 1)))
def test_repeated_key_loads_nothing_of_that_class(loaded_db, versions, different):
    informe = read_tables(repeated_class(*versions))
    result = load(loaded_db, informe)
    counts = result.counts

    assert informe.counts[("chaves", "repetidas_com_versao_diferente")] == different
    assert count(loaded_db, "observations", FIAGRO_CLASS_ROWS, (class_id(loaded_db, 1),)) == 0
    assert count(loaded_db, "quota_series", "fund_class_id = ?", (class_id(loaded_db, 1),)) == 0
    assert count(loaded_db, "party_observations", FIAGRO_CLASS_ROWS, (class_id(loaded_db, 1),)) == 0
    assert count(loaded_db, "observations", FIAGRO_CLASS_ROWS, (class_id(loaded_db, 2),)) == 122
    assert counts[("casamento", CLASS, REPEATED_KEY)] == len(versions)
    assert counts[("casamento", SUBCLASS, REPEATED_KEY)] == len(versions) + 1
    assert counts[("casamento", CLASS, SUPERSEDED)] == 0
    assert counts[("classes", REPEATED_KEY)] == 1
    assert counts[("classes", LOADED)] == 1
    status, requested, successful, failed, summary = run_summary(loaded_db)
    assert (status, requested, successful, failed) == ("success", 2, 1, 0)
    assert json.loads(summary) == {"chaves_repetidas_nao_carregadas": 1}


@pytest.mark.parametrize("versions", (("1", "2"), ("2", "1")))
def test_highest_version_in_the_same_zip_loads_and_its_subclasses_do_not(loaded_db, versions):
    tables = repeated_class(*versions)
    patrimonio = {"1": "1000", "2": "2000"}

    for row in tables[CLASS][:2]:
        row["Patrimonio_Liquido"] = patrimonio[row["Versao"]]

    result = load(loaded_db, read_tables(tables))
    counts = result.counts
    fund_class = class_id(loaded_db, 1)

    assert current(loaded_db, "inf_mensal_fiagro.Versao", fund_class_id=fund_class).value_numeric == "2"
    assert current(loaded_db, "inf_mensal_fiagro.Patrimonio_Liquido", fund_class_id=fund_class).value_numeric == "2000"
    assert count(loaded_db, "observations", FIAGRO_CLASS_ROWS, (fund_class,)) == 122
    assert count(loaded_db, "party_observations", FIAGRO_CLASS_ROWS, (fund_class,)) == 2
    # As subclasses nao se ligam a uma Versao: nenhuma entra (P2).
    assert count(loaded_db, "quota_series", "fund_class_id = ?", (fund_class,)) == 0
    assert count(loaded_db, "data_conflicts") == 0
    assert counts[("casamento", CLASS, LOADED)] == 2
    assert counts[("casamento", CLASS, SUPERSEDED)] == 1
    assert counts[("casamento", SUBCLASS, VERSIONED_SUBCLASS)] == 3
    assert counts[("casamento", SUBCLASS, REPEATED_KEY)] == 0
    assert counts[("classes", LOADED)] == 2
    assert counts[("classes", REPEATED_KEY)] == 0
    status, requested, successful, failed, summary = run_summary(loaded_db)
    assert (status, requested, successful, failed) == ("success", 2, 2, 0)
    assert json.loads(summary) == {
        "linhas_de_versao_anterior_nao_carregadas": 1,
        "subclasses_de_classe_com_mais_de_uma_versao": 3,
    }


def test_version_two_alone_is_the_current_value(loaded_db):
    load(loaded_db, read_tables(merge(subject_rows(1, Versao="2", Data_Entrega="2026-10-14"), subject_rows(2))))
    fund_class = class_id(loaded_db, 1)

    assert current(loaded_db, "inf_mensal_fiagro.Versao", fund_class_id=fund_class).value_numeric == "2"
    assert current(loaded_db, "inf_mensal_fiagro.Data_Entrega", fund_class_id=fund_class).value_date == "2026-10-14"
    assert count(loaded_db, "observations", "fund_class_id = ? AND field_name = 'inf_mensal_fiagro.Versao'", (fund_class,)) == 1
    assert count(loaded_db, "data_conflicts") == 0


def test_empty_isin_has_no_row_and_a_shared_isin_is_two_rows(loaded_db):
    load(
        loaded_db,
        read_tables(
            merge(
                subject_rows(1, Codigo_ISIN=""),
                subject_rows(2, Codigo_ISIN=fake_isin(7)),
                subject_rows(3, Codigo_ISIN=fake_isin(7)),
            )
        ),
    )

    assert rows(
        loaded_db,
        "SELECT c.cnpj, o.value_text FROM observations o JOIN fund_classes c ON c.id = o.fund_class_id"
        " WHERE o.field_name = 'inf_mensal_fiagro.Codigo_ISIN' ORDER BY c.cnpj",
    ) == [(fake_cnpj(2), fake_isin(7)), (fake_cnpj(3), fake_isin(7))]
    assert count(loaded_db, "data_conflicts") == 0


def test_two_spellings_of_the_first_subclass_are_two_series(loaded_db):
    load(
        loaded_db,
        read_tables(
            merge(
                subject_rows(1, labels=(FIRST_SUBCLASS,)),
                subject_rows(2, labels=(FIRST_SUBCLASS_NO_SPACE,)),
                subject_rows(3, labels=(FIRST_SUBCLASS, FIRST_SUBCLASS_NO_SPACE)),
            )
        ),
    )

    assert rows(
        loaded_db,
        "SELECT c.cnpj, s.series_label_key, o.value_text FROM quota_series s"
        " JOIN fund_classes c ON c.id = s.fund_class_id"
        " JOIN observations o ON o.quota_series_id = s.id AND o.field_name = 'inf_mensal_fiagro_subclasse.Nome_Subclasse'"
        " ORDER BY c.cnpj, s.id",
    ) == [
        (fake_cnpj(1), "subclasse 1 (ou classe unica)", FIRST_SUBCLASS),
        (fake_cnpj(2), "subclasse 1(ou classe unica)", FIRST_SUBCLASS_NO_SPACE),
        (fake_cnpj(3), "subclasse 1 (ou classe unica)", FIRST_SUBCLASS),
        (fake_cnpj(3), "subclasse 1(ou classe unica)", FIRST_SUBCLASS_NO_SPACE),
    ]


def test_repeated_subclass_pair_and_empty_label_are_not_loaded(loaded_db):
    tables = subject_rows(1, labels=(FIRST_SUBCLASS, SECOND_SUBCLASS, "Subclasse  2 |", " | "))
    result = load(loaded_db, read_tables(tables))

    assert rows(loaded_db, "SELECT series_label_key FROM quota_series") == [("subclasse 1 (ou classe unica)",)]
    assert count(loaded_db, "observations", "field_name LIKE 'inf_mensal_fiagro_subclasse.%'") == 3
    assert result.counts[("casamento", SUBCLASS, REPEATED_SERIES)] == 2
    assert result.counts[("casamento", SUBCLASS, EMPTY_LABEL)] == 1
    assert result.counts[("casamento", SUBCLASS, LOADED)] == 1


def test_party_identifiers_keep_only_a_valid_cnpj_and_never_a_cpf(loaded_db):
    tables = merge(
        subject_rows(1, CNPJ_Gestor=FAKE_CPF_MASKED, CNPJ_Administrador=masked(fake_cnpj(903))),
        subject_rows(2, CNPJ_Administrador=FAKE_CPF),
    )
    result = load(loaded_db, read_tables(tables))

    assert rows(
        loaded_db,
        "SELECT c.cnpj, p.role, p.party_cnpj FROM party_observations p JOIN fund_classes c ON c.id = p.fund_class_id"
        " WHERE p.field_name LIKE 'inf_mensal_fiagro.%' ORDER BY c.cnpj, p.role",
    ) == [
        (fake_cnpj(1), "administrador", fake_cnpj(903)),
        (fake_cnpj(2), "gestor", MANAGER_CNPJ),
    ]
    assert result.counts[("papeis", "gestor", "criados")] == 1
    assert result.counts[("varredura_cpf", "party_observations")] == 0

    stored = all_text(loaded_db)
    assert FAKE_CPF not in stored
    assert FAKE_CPF_MASKED not in stored
    assert not any(FAKE_CPF in value for value in stored)


def test_contact_fields_never_reach_the_database(loaded_db):
    load(loaded_db)
    stored = all_text(loaded_db)

    for value in CONTACTS.values():
        assert not any(value in text for text in stored)

    for column in ("Email_Administrador", "Site", "Servico_Atendimento_Cotista", "Entidade_Administradora"):
        assert count(loaded_db, "observations", "field_name LIKE ?", ("%." + column,)) == 0


def test_class_outside_the_cadastro_is_only_counted(loaded_db):
    before = snapshot(loaded_db)
    tables = merge(
        subject_rows(1),
        subject_rows(9),
        subject_rows(5),
        {CLASS: [class_row(6, CNPJ_Classe="12345")], SUBCLASS: [subclass_row(6, CNPJ_Classe="12345")]},
        {SUBCLASS: [subclass_row(3)]},
    )
    result = load(loaded_db, read_tables(tables))
    counts = result.counts

    assert snapshot(loaded_db)["funds"] == before["funds"]
    assert snapshot(loaded_db)["fund_classes"] == before["fund_classes"]
    assert [counts[("casamento", CLASS, outcome)] for outcome in (LOADED, ONLY_FUND, NOT_FOUND, INVALID_CNPJ)] == [1, 1, 1, 1]
    assert [
        counts[("casamento", SUBCLASS, outcome)] for outcome in (LOADED, ONLY_FUND, NOT_FOUND, INVALID_CNPJ, NO_CLASS_ROW)
    ] == [2, 2, 2, 1, 1]
    assert count(loaded_db, "observations", FIAGRO_CLASS_ROWS, (class_id(loaded_db, 3),)) == 0
    assert count(loaded_db, "quota_series", "fund_class_id = ?", (class_id(loaded_db, 3),)) == 0
    status, requested, successful, failed, summary = run_summary(loaded_db)
    assert (status, requested, successful, failed) == ("success", 3, 1, 0)
    assert json.loads(summary) == {"classes_fora_do_cadastro": 2, "linhas_com_cnpj_classe_invalido": 1}


def test_same_zip_twice_has_nothing_to_load(loaded_db):
    informe = read()
    load(loaded_db, informe)
    before = snapshot(loaded_db)

    with pytest.raises(LoadError, match=r"\(mesmo ZIP\); nada a carregar"):
        load(loaded_db, informe)

    assert snapshot(loaded_db) == before

    with loaded_db.connection() as connection:
        assert find_loaded_informe(connection, informe) == ALREADY_LOADED


def test_other_zip_of_the_same_competence_needs_last_modified(loaded_db):
    load(loaded_db)
    other = read(build_informe_zip(subject_rows(1, Patrimonio_Liquido="2000"), date_time=(2026, 10, 31, 8, 0, 0)))
    before = snapshot(loaded_db)

    with pytest.raises(LoadError, match="Para carregar este ZIP como reapresentacao, informe --last-modified"):
        load(loaded_db, other)

    assert snapshot(loaded_db) == before

    with loaded_db.connection() as connection:
        assert find_loaded_informe(connection, other) == SAME_COMPETENCE


def test_another_competence_is_a_normal_load_and_reuses_the_series(loaded_db):
    load(loaded_db)
    august = {
        CLASS: [class_row(Data_Referencia="2026-08-01")],
        SUBCLASS: [subclass_row(1, label, Data_Referencia="2026-08-01") for label in (FIRST_SUBCLASS, SECOND_SUBCLASS)],
    }
    result = load(loaded_db, read(build_informe_zip(august, period="202608"), name="inf_mensal_fiagro_202608.zip"))

    assert result.counts[("series", "existentes")] == 2
    assert count(loaded_db, "quota_series") == 2
    assert count(loaded_db, "data_conflicts") == 0
    # A competencia mais recente continua sendo o valor atual.
    assert current(loaded_db, "inf_mensal_fiagro.Patrimonio_Liquido", fund_class_id=class_id(loaded_db, 1)).reference_date == COMPETENCE


def test_cpf_like_text_rolls_back_the_whole_load(loaded_db):
    before = snapshot(loaded_db)

    with pytest.raises(LoadError, match="Texto com formato de CPF"):
        load(loaded_db, read_tables(subject_rows(1, Nome_Classe=FAKE_CPF)))

    assert snapshot(loaded_db) == before


def test_zero_is_recorded_empty_is_not_and_types_are_kept(loaded_db):
    load(loaded_db)
    fund_class = class_id(loaded_db, 1)
    stored = {
        field: (value_type, value_text, value_numeric, value_date, value_boolean)
        for field, value_type, value_text, value_numeric, value_date, value_boolean in rows(
            loaded_db,
            "SELECT field_name, value_type, value_text, value_numeric, value_date, value_boolean"
            " FROM observations WHERE fund_class_id = ?",
            (fund_class,),
        )
    }

    assert stored["inf_mensal_fiagro.LCA"] == ("numeric", None, "0", None, None)
    assert stored["inf_mensal_fiagro.Classe_Unica"] == ("boolean", None, None, None, 0)
    assert stored["inf_mensal_fiagro.Data_Registro"] == ("date", None, None, "2020-01-02", None)
    assert stored["inf_mensal_fiagro.Encerramento_Exercicio_Social"] == ("text", "31/12", None, None, None)
    assert stored["inf_mensal_fiagro.Versao"] == ("numeric", None, "1", None, None)
    assert "inf_mensal_fiagro.Classificacao_Autorregulada" not in stored


def test_fidc_and_fiagro_of_the_same_class_do_not_conflict(full_db):
    import apoio_informe_fidc
    from fundos.informe_fidc.loader import load_informe as load_fidc
    from fundos.informe_fidc.reader import read_informe_bytes as read_fidc

    load_fictitious_cadastro(full_db, classes=(1,))

    with full_db.transaction() as connection:
        load_fidc(connection, read_fidc(apoio_informe_fidc.build_informe_zip(), apoio_informe_fidc.ZIP_NAME))

    fidc_checksums = rows(full_db, "SELECT checksum FROM observations ORDER BY checksum")
    fidc_parties = rows(full_db, "SELECT checksum FROM party_observations ORDER BY checksum")
    load(full_db)
    fund_class = class_id(full_db, 1)

    assert rows(
        full_db, "SELECT checksum FROM observations WHERE field_name NOT LIKE 'inf_mensal_fiagro%' ORDER BY checksum"
    ) == fidc_checksums
    assert rows(
        full_db,
        "SELECT checksum FROM party_observations WHERE field_name NOT LIKE 'inf_mensal_fiagro%' ORDER BY checksum",
    ) == fidc_parties
    assert count(full_db, "data_conflicts") == 0
    assert count(full_db, "party_conflicts") == 0
    # A mesma administradora nos dois informes: duas linhas, uma por campo.
    assert rows(
        full_db,
        "SELECT field_name FROM party_observations WHERE fund_class_id = ? AND role = 'administrador' ORDER BY field_name",
        (fund_class,),
    ) == [("inf_mensal_fiagro.CNPJ_Administrador",), ("tab_I.CNPJ_ADMIN",)]
    assert current(full_db, "inf_mensal_fiagro.Patrimonio_Liquido", fund_class_id=fund_class).value_numeric == "1000.5"
    assert current(full_db, "tab_IV.TAB_IV_A_VL_PL", fund_class_id=fund_class).value_numeric == "1000.5"


def test_manager_from_the_informe_and_from_the_cadastro_coexist(loaded_db):
    load(loaded_db)

    assert rows(
        loaded_db,
        "SELECT fund_id IS NOT NULL, field_name, party_cnpj FROM party_observations"
        " WHERE role = 'gestor' AND (fund_id = (SELECT fund_id FROM fund_classes WHERE cnpj = ?) OR fund_class_id = ?)"
        " ORDER BY field_name",
        (fake_cnpj(1), class_id(loaded_db, 1)),
    ) == [
        (0, "inf_mensal_fiagro.CNPJ_Gestor", MANAGER_CNPJ),
        (1, "registro_fundo.CPF_CNPJ_Gestor", fake_cnpj(801)),
    ]
    assert count(loaded_db, "party_conflicts") == 0


def test_match_counts_are_what_the_load_writes(loaded_db):
    informe = read_tables(
        merge(subject_rows(1), subject_rows(2, labels=(FIRST_SUBCLASS,)), subject_rows(5), subject_rows(9))
    )

    with loaded_db.connection() as connection:
        counts = match_counts(informe, ClassResolver(connection, informe))

    result = load(loaded_db, informe)
    created = sum(n for key, n in result.counts.items() if key[0] == "observacoes" and key[3] == "criadas")

    assert sum(n for key, n in counts.items() if key[0] == "candidatas") == created
    assert counts[("series_candidatas",)] == result.counts[("series", "criadas")] == 3
    assert counts[("papeis_candidatos", "gestor")] == result.counts[("papeis", "gestor", "criados")] == 2

    for key, n in counts.items():
        if key[0] in ("casamento", "classes"):
            assert result.counts[key] == n


def test_progress_reports_each_file(loaded_db):
    seen = []
    load(loaded_db, progress=lambda table, observations, seconds: seen.append((table, observations)))

    assert seen == [(CLASS, 122), (SUBCLASS, 6)]


def test_reports_have_only_aggregates(loaded_db):
    informe = read_tables(merge(subject_rows(1), subject_rows(5)))

    with loaded_db.connection() as connection:
        counts = match_counts(informe, ClassResolver(connection, informe))

    text = "\n".join(format_match_report(counts) + format_candidates_report(counts) + format_load_report(load(loaded_db, informe)))

    assert "inf_mensal_fiagro: entram 1; fora 1" in text
    assert "party_observations: administrador 1, gestor 1" in text
    assert "manifesto: o ZIP e os 2 CSV em raw_records (" + PARSER_VERSION + ")" in text

    for secret in (fake_cnpj(1), fake_cnpj(5), ADMIN_CNPJ, MANAGER_CNPJ, ADMIN_NAME, MANAGER_NAME, subject_name(1), fake_isin(1)):
        assert secret not in text


# Reapresentacao (FU5.3): outro ZIP da mesma competencia.

LM1 = "2026-10-24T11:46:15Z"
LM2 = "2026-10-29T11:46:15Z"
LM3 = "2026-10-31T11:46:15Z"
LM4 = "2026-11-02T11:46:15Z"
DATE3 = (2026, 10, 31, 8, 34, 6)
DATE4 = (2026, 11, 2, 8, 34, 6)
PL = "inf_mensal_fiagro.Patrimonio_Liquido"
RENAMED_MANAGER = "Gestora Ficticia Renomeada Ltda"


def later(tables=None, date_time=LATER_MEMBER_DATE):
    return read(later_zip(tables, date_time))


def value(db, field=PL, n=1):
    """Valor atual (view) do campo na classe n, como texto."""

    record = current(db, field, fund_class_id=class_id(db, n))
    return None if record is None else str(record.value)


def reap(counts, *key):
    return counts[("reapresentacao",) + key]


def compared(counts, kind, status, tables=columns.TABLES):
    return sum(counts[("reapresentacao", kind, table, status)] for table in tables)


def delta(before, after, tables=None):
    return {table: after[table] - before[table] for table in (tables or after)}


def latest_manager(db):
    return rows(
        db,
        "SELECT party_cnpj, party_name FROM party_observations WHERE role = 'gestor'"
        " AND field_name LIKE 'inf_mensal_fiagro.%' ORDER BY collected_at DESC, id DESC LIMIT 1",
    )[0]


def test_second_zip_with_the_same_values_records_only_the_collection(loaded_db):
    load(loaded_db, last_modified=LM1)
    before = snapshot(loaded_db)
    informe = later()
    result = load(loaded_db, informe, last_modified=LM2)

    assert result.status == "success"
    assert delta(before, snapshot(loaded_db)) == {
        "observations": 0, "party_observations": 0, "quota_series": 0, "raw_records": 3,
        "collection_runs": 1, "data_conflicts": 0, "party_conflicts": 0, "funds": 0, "fund_classes": 0,
    }
    assert compared(result.counts, "celulas", "iguais") == expected_values(informe) == 128
    assert sum(n for key, n in result.counts.items() if key[0] == "observacoes" and key[3] == "existentes") == 128
    assert result.counts[("papeis", "gestor", "existentes")] == 1
    assert rows(
        loaded_db,
        "SELECT last_modified, parser_version FROM raw_records WHERE parent_raw_record_id IS NULL AND file_name = ? ORDER BY id",
        (ZIP_NAME,),
    ) == [("2026-10-24T11:46:15.000000+00:00", PARSER_VERSION), ("2026-10-29T11:46:15.000000+00:00", PARSER_VERSION)]


def test_changed_value_opens_a_conflict_and_becomes_current(loaded_db):
    load(loaded_db, last_modified=LM1)
    result = load(loaded_db, later(changed(inf_mensal_fiagro={"Patrimonio_Liquido": "2000"})), last_modified=LM2)

    assert value(loaded_db) == "2000"
    assert rows(loaded_db, "SELECT value_numeric FROM observations WHERE field_name = ? ORDER BY id", (PL,)) == [
        ("1000.5",), ("2000",)
    ]
    assert count(loaded_db, "data_conflicts", "status = 'open'") == 1
    assert result.counts[("conflitos", "data_conflicts")] == 1
    assert reap(result.counts, "celulas", CLASS, "alteradas") == 1


def test_emptied_cell_is_only_counted_and_the_old_value_stays_current(loaded_db):
    load(loaded_db, last_modified=LM1)
    before = count(loaded_db, "observations")
    result = load(loaded_db, later(changed(inf_mensal_fiagro={"Patrimonio_Liquido": ""})), last_modified=LM2)

    assert count(loaded_db, "observations") == before
    assert value(loaded_db) == "1000.5"
    assert reap(result.counts, "sumiram", CLASS, "vazias") == 1


def test_class_that_vanishes_is_counted_and_nothing_is_deleted(loaded_db):
    load(loaded_db, read_tables(merge(subject_rows(1), subject_rows(2))), last_modified=LM1)
    before = snapshot(loaded_db)
    result = load(loaded_db, later(), last_modified=LM2)

    assert delta(before, snapshot(loaded_db), ("observations", "party_observations", "quota_series")) == {
        "observations": 0, "party_observations": 0, "quota_series": 0,
    }
    assert reap(result.counts, "classes", "sumiram") == 1
    assert reap(result.counts, "classes", "celulas_das_que_sumiram") == 128
    assert reap(result.counts, "series", "sumiram") == 2
    assert reap(result.counts, "papeis", "gestor", "saiu") == 1
    assert reap(result.counts, "papeis", "administrador", "saiu") == 1
    assert value(loaded_db, n=2) == "1000.5"


def test_new_class_and_its_series_are_loaded(loaded_db):
    load(loaded_db, last_modified=LM1)
    result = load(loaded_db, later(merge(subject_rows(1), subject_rows(2))), last_modified=LM2)

    assert count(loaded_db, "observations", FIAGRO_CLASS_ROWS, (class_id(loaded_db, 2),)) == 122
    assert count(loaded_db, "quota_series") == 4
    assert reap(result.counts, "classes", "novas") == 1
    assert reap(result.counts, "series", "novas") == 2
    assert result.counts[("series", "criadas")] == 2


def test_version_two_over_one_becomes_current(loaded_db):
    load(loaded_db, last_modified=LM1)
    changes = {"Versao": "2", "Data_Entrega": "2026-10-20", "Patrimonio_Liquido": "2000"}
    result = load(loaded_db, later(changed(inf_mensal_fiagro=changes)), last_modified=LM2)

    assert value(loaded_db, "inf_mensal_fiagro.Versao") == "2"
    assert value(loaded_db, "inf_mensal_fiagro.Data_Entrega") == "2026-10-20"
    assert value(loaded_db) == "2000"
    assert count(loaded_db, "data_conflicts") == 3
    assert reap(result.counts, "celulas", CLASS, "alteradas") == 3
    assert reap(result.counts, "versao", "versao_maior") == 1


def test_lower_version_after_a_higher_one_is_withheld(loaded_db):
    load(loaded_db, read_tables(merge(subject_rows(1, Versao="2"), subject_rows(2))), last_modified=LM1)
    before = snapshot(loaded_db)
    first = changed(
        subject_rows(1),
        inf_mensal_fiagro={"Versao": "1", "Patrimonio_Liquido": "3000", "Nome_Gestor": RENAMED_MANAGER},
        inf_mensal_fiagro_subclasse={"Numero_Cotas": "999"},
    )
    second = changed(subject_rows(2), inf_mensal_fiagro={"Patrimonio_Liquido": "2000"})
    result = load(loaded_db, later(merge(first, second)), last_modified=LM2)
    counts = result.counts

    # A classe 1 nao entra (nem papel nem subclasse); a classe 2 segue a regra.
    assert delta(before, snapshot(loaded_db), ("observations", "party_observations", "quota_series", "data_conflicts", "party_conflicts")) == {
        "observations": 1, "party_observations": 0, "quota_series": 0, "data_conflicts": 1, "party_conflicts": 0,
    }
    assert value(loaded_db, "inf_mensal_fiagro.Versao") == "2"
    assert value(loaded_db) == "1000.5"
    assert value(loaded_db, n=2) == "2000"
    assert latest_manager(loaded_db) == (MANAGER_CNPJ, MANAGER_NAME)
    assert counts[("casamento", CLASS, LOWER_VERSION)] == 1
    assert counts[("casamento", SUBCLASS, LOWER_VERSION)] == 2
    assert counts[("classes", LOWER_VERSION)] == 1
    assert counts[("classes", LOADED)] == 1
    assert reap(counts, "classes", "retidas") == 1
    assert reap(counts, "classes", "sumiram") == 0
    assert reap(counts, "series", "retidas") == 2
    assert reap(counts, "series", "sumiram") == reap(counts, "series", "possivel_troca_de_rotulo") == 0
    assert reap(counts, "retidas", CLASS, LOWER_VERSION) == 122
    assert reap(counts, "retidas", SUBCLASS, LOWER_VERSION) == 6
    assert compared(counts, "sumiram", "vazias") + compared(counts, "sumiram", "sem_linha") == 0
    assert reap(counts, "papeis", "gestor", "retidos") == 1
    assert reap(counts, "papeis", "gestor", "saiu") == 0
    status, requested, successful, failed, summary = run_summary(loaded_db)
    assert (status, successful) == ("success", 1)
    assert json.loads(summary) == {"classes_com_versao_menor_que_a_carregada": 1}


def test_same_version_with_a_new_delivery_date(loaded_db):
    load(loaded_db, last_modified=LM1)
    changes = {"Data_Entrega": "2026-10-22", "Patrimonio_Liquido": "2000"}
    result = load(loaded_db, later(changed(inf_mensal_fiagro=changes)), last_modified=LM2)

    assert value(loaded_db, "inf_mensal_fiagro.Data_Entrega") == "2026-10-22"
    assert value(loaded_db, "inf_mensal_fiagro.Versao") == "1"
    assert value(loaded_db) == "2000"
    assert count(loaded_db, "data_conflicts") == 2
    assert reap(result.counts, "versao", "mesma_versao_alterada") == 1
    assert reap(result.counts, "versao", "versao_maior") == reap(result.counts, "versao", "data_entrega_anterior") == 0


def test_two_versions_in_the_new_zip_load_the_highest_and_withhold_the_subclasses(loaded_db):
    load(loaded_db, last_modified=LM1)
    series = rows(loaded_db, "SELECT id FROM quota_series WHERE fund_class_id = ? ORDER BY id", (class_id(loaded_db, 1),))
    tables = repeated_class("1", "2")
    tables[CLASS][1]["Patrimonio_Liquido"] = "2000"
    result = load(loaded_db, later(tables), last_modified=LM2)
    counts = result.counts

    assert value(loaded_db, "inf_mensal_fiagro.Versao") == "2"
    assert value(loaded_db) == "2000"
    assert counts[("casamento", CLASS, SUPERSEDED)] == 1
    assert counts[("casamento", SUBCLASS, VERSIONED_SUBCLASS)] == 3
    # As subclasses da classe 1 sao retidas: nem serie sumida nem possivel troca de rotulo.
    assert reap(counts, "series", "sumiram") == 0
    assert reap(counts, "series", "possivel_troca_de_rotulo") == 0
    assert reap(counts, "series", "retidas") == 2
    assert reap(counts, "series", "novas") == 2
    assert reap(counts, "retidas", SUBCLASS, VERSIONED_SUBCLASS) == 6
    assert compared(counts, "sumiram", "sem_linha", (SUBCLASS,)) == 0
    assert reap(counts, "classes", "nos_dois") == 1
    assert reap(counts, "classes", "novas") == 1
    assert count(loaded_db, "quota_series", "fund_class_id = ?", (class_id(loaded_db, 1),)) == 2
    assert current(loaded_db, "inf_mensal_fiagro_subclasse.Numero_Cotas", quota_series_id=series[0][0]).value_numeric == "100"


def test_value_that_returns_is_restated_and_the_conflict_opens_once(loaded_db):
    load(loaded_db, last_modified=LM1)
    load(loaded_db, later(changed(inf_mensal_fiagro={"Patrimonio_Liquido": "2000"})), last_modified=LM2)
    third = load(loaded_db, later(None, DATE3), last_modified=LM3)

    assert value(loaded_db) == "1000.5"
    assert reap(third.counts, "celulas", CLASS, "voltam") == 1
    assert count(loaded_db, "observations", "field_name = ?", (PL,)) == 3
    assert count(loaded_db, "data_conflicts") == 1

    fourth = load(loaded_db, later(changed(inf_mensal_fiagro={"Patrimonio_Liquido": "2000"}), DATE4), last_modified=LM4)

    assert value(loaded_db) == "2000"
    assert reap(fourth.counts, "celulas", CLASS, "voltam") == 1
    assert count(loaded_db, "observations", "field_name = ?", (PL,)) == 4
    assert count(loaded_db, "data_conflicts") == 1


def test_manager_name_cnpj_and_return(loaded_db):
    load(loaded_db, last_modified=LM1)
    second = load(loaded_db, later(changed(inf_mensal_fiagro={"Nome_Gestor": RENAMED_MANAGER})), last_modified=LM2)

    assert reap(second.counts, "papeis", "gestor", "nome_alterado") == 1
    assert count(loaded_db, "party_conflicts") == 1

    third = load(loaded_db, later(changed(inf_mensal_fiagro={"CNPJ_Gestor": fake_cnpj(803)}), DATE3), last_modified=LM3)

    # Limitacao conhecida: na mesma competencia as linhas do papel se somam.
    assert reap(third.counts, "papeis", "gestor", "cnpj_trocado") == 1
    assert count(loaded_db, "party_conflicts") == 1

    fourth = load(loaded_db, later(None, DATE4), last_modified=LM4)

    assert reap(fourth.counts, "papeis", "gestor", "voltam") == 1
    assert latest_manager(loaded_db) == (MANAGER_CNPJ, MANAGER_NAME)
    assert count(loaded_db, "party_observations", "role = 'gestor' AND field_name LIKE 'inf_mensal_fiagro.%'") == 4
    assert count(loaded_db, "party_conflicts") == 1


def test_older_zip_after_a_newer_one_is_refused(loaded_db):
    load(loaded_db, last_modified=LM2)
    before = snapshot(loaded_db)

    for last_modified in (LM1, LM2):
        with pytest.raises(LoadError, match="nao e posterior ao do ZIP mais novo") as error:
            load(loaded_db, later(changed(inf_mensal_fiagro={"Patrimonio_Liquido": "2000"})), last_modified=last_modified)

        assert "(2026-10-29T11:46:15.000000+00:00)" in str(error.value)

    assert snapshot(loaded_db) == before


def test_competence_loaded_by_v1_without_last_modified_is_the_base(loaded_db):
    load(loaded_db)

    with loaded_db.connection() as connection:
        connection.execute(
            "UPDATE raw_records SET parser_version = 'fundos.informe_fiagro.v1' WHERE parser_version = ?",
            (PARSER_VERSION,),
        )

    before = snapshot(loaded_db)

    with pytest.raises(LoadError, match="nao da para provar que este ZIP e mais novo"):
        load(loaded_db, later(), last_modified=LM2)

    assert snapshot(loaded_db) == before
    result = load(loaded_db, later(changed(inf_mensal_fiagro={"Patrimonio_Liquido": "2000"})), last_modified=utc_now())

    assert result.status == "success"
    assert reap(result.counts, "zips") == 1
    assert reap(result.counts, "celulas", CLASS, "alteradas") == 1
    assert reap(result.counts, "celulas", CLASS, "iguais") == 121
    assert value(loaded_db) == "2000"


def test_unknown_reader_version_is_refused(loaded_db):
    load(loaded_db, last_modified=LM1)

    with loaded_db.connection() as connection:
        connection.execute("UPDATE raw_records SET parser_version = 'fundos.informe_fiagro.v9' WHERE parser_version = ?", (PARSER_VERSION,))

    before = snapshot(loaded_db)
    informe = later()

    with pytest.raises(LoadError, match="versao do leitor que esta nao conhece"):
        load(loaded_db, informe, last_modified=LM2)

    assert snapshot(loaded_db) == before

    with loaded_db.connection() as connection:
        assert find_loaded_informe(connection, informe) == UNKNOWN_VERSION


def test_cpf_like_text_in_a_changed_cell_undoes_the_second_load(loaded_db):
    load(loaded_db, last_modified=LM1)
    before = snapshot(loaded_db)

    with pytest.raises(LoadError, match="Texto com formato de CPF"):
        load(loaded_db, later(changed(inf_mensal_fiagro={"Nome_Classe": FAKE_CPF})), last_modified=LM2)

    assert snapshot(loaded_db) == before


def test_failure_in_the_second_load_rolls_back_everything(loaded_db, monkeypatch):
    load(loaded_db, last_modified=LM1)
    before = snapshot(loaded_db)

    def failing(self, **arguments):
        raise RuntimeError("falha simulada")

    monkeypatch.setattr(ObservationRepository, "record", failing)

    with pytest.raises(RuntimeError, match="falha simulada"):
        load(loaded_db, later(changed(inf_mensal_fiagro={"Patrimonio_Liquido": "2000"})), last_modified=LM2)

    assert snapshot(loaded_db) == before


def test_reapresentation_works_with_only_migrations_001_and_002(tmp_path):
    db = create_schema(tmp_path / "fundos.db", (MIGRATION_001, MIGRATIONS_DIR / "002_party_observations.sql"))
    load_fictitious_cadastro(db, classes=(1,))
    load(db, last_modified=LM1)
    result = load(db, later(changed(inf_mensal_fiagro={"Nome_Gestor": RENAMED_MANAGER})), last_modified=LM2)

    assert reap(result.counts, "papeis", "gestor", "nome_alterado") == 1
    assert reap(result.counts, "papeis", "administrador", "iguais") == 1
    assert count(db, "party_conflicts") == 1


def record_everything(db, informe):
    """Grava de novo todas as celulas e papeis do ZIP que a carga aceita, sem pular nada; devolve as linhas criadas."""

    created = 0

    with db.transaction() as connection:
        run_id = connection.execute("SELECT MAX(id) FROM collection_runs").fetchone()[0]
        source_id = connection.execute("SELECT source_id FROM collection_runs WHERE id = ?", (run_id,)).fetchone()[0]
        raw_id = connection.execute("SELECT MAX(id) FROM raw_records").fetchone()[0]
        resolver = ClassResolver(connection, informe)
        observations = ObservationRepository(connection)
        parties = PartyObservationRepository(connection)
        series = QuotaSeriesRepository(connection)
        provenance = {"source_id": source_id, "collection_run_id": run_id, "raw_record_id": raw_id, "reference_date": informe.competence}

        for table in columns.TABLES:
            for r in informe.rows(table):
                found, _ = resolver.resolve(r)

                if found is None:
                    continue

                if table == SUBCLASS:
                    target = {"quota_series_id": series.get_or_create(fund_class_id=found, label=r.series_label)[0].id}
                else:
                    target = {"fund_class_id": found}

                for name, cell in r.values.items():
                    created += observations.record(
                        **target,
                        **provenance,
                        field_name=columns.field_name(table, name),
                        value_type=columns.VALUE_TYPE[columns.KINDS[table][name]],
                        value=cell,
                    ).created

                for party in r.parties:
                    created += parties.record(
                        fund_class_id=found,
                        **provenance,
                        role=party.role,
                        field_name=party.field_name,
                        party_cnpj=party.cnpj,
                        name_field_name=party.name_field_name,
                        party_name=party.name,
                    ).created

    return created


def test_recording_every_cell_after_the_load_creates_nothing(loaded_db):
    # Pular a celula igual da o mesmo banco que gravar tudo.
    load(loaded_db, last_modified=LM1)
    second = changed(inf_mensal_fiagro={"Patrimonio_Liquido": "2000", "Nome_Gestor": RENAMED_MANAGER})
    load(loaded_db, later(merge(second, subject_rows(2))), last_modified=LM2)
    third = later(merge(subject_rows(1), subject_rows(2)), DATE3)
    load(loaded_db, third, last_modified=LM3)
    before = snapshot(loaded_db)

    assert record_everything(loaded_db, third) == 0
    assert snapshot(loaded_db) == before


def reapresentation_keys(counts):
    return {key: n for key, n in counts.items() if key[0] in ("reapresentacao", "casamento", "classes") and n}


def test_dry_run_comparison_writes_nothing_and_matches_the_load(loaded_db):
    load(loaded_db, read_tables(merge(subject_rows(1), subject_rows(3, Versao="2"))), last_modified=LM1)
    informe = later(
        merge(
            changed(inf_mensal_fiagro={"Patrimonio_Liquido": "2000", "Codigo_ISIN": ""}),
            subject_rows(2),
            subject_rows(3, Versao="1"),
        )
    )
    before = snapshot(loaded_db)

    with loaded_db.connection() as connection:
        connection.execute("PRAGMA query_only = ON")
        counts = reapresentation_counts(connection, informe, ClassResolver(connection, informe))

    assert snapshot(loaded_db) == before
    result = load(loaded_db, informe, last_modified=LM2)

    assert reapresentation_keys(counts) == reapresentation_keys(result.counts)
    assert counts[("classes", LOWER_VERSION)] == 1


def test_reapresentation_report_has_only_counts(loaded_db):
    load(loaded_db, last_modified=LM1)
    changes = {"Patrimonio_Liquido": "98765.4321", "Nome_Gestor": RENAMED_MANAGER}
    result = load(loaded_db, later(changed(inf_mensal_fiagro=changes)), last_modified=LM2)
    text = "\n".join(format_reapresentation_report(result.counts) + format_load_report(result))

    assert "  celulas inf_mensal_fiagro: iguais 121, alteradas 1, novas 0, voltam a valor anterior 0, sumiram 0" in text
    assert "  party_observations gestor: iguais 0, voltam a valor anterior 0, nome alterado 1" in text
    assert "manifesto: o ZIP e os 2 CSV em raw_records (fundos.informe_fiagro.v2)" in text

    for secret in (fake_cnpj(1), ADMIN_CNPJ, MANAGER_CNPJ, MANAGER_NAME, RENAMED_MANAGER, subject_name(1), "98765.4321", "Ficticia"):
        assert secret not in text
