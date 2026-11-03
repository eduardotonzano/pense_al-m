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
from apoio_informe_fiagro import MANAGER_CNPJ
from apoio_informe_fiagro import MANAGER_NAME
from apoio_informe_fiagro import SECOND_SUBCLASS
from apoio_informe_fiagro import ZIP_NAME
from apoio_informe_fiagro import build_informe_zip
from apoio_informe_fiagro import class_row
from apoio_informe_fiagro import fake_isin
from apoio_informe_fiagro import load_fictitious_cadastro
from apoio_informe_fiagro import merge
from apoio_informe_fiagro import subclass_row
from apoio_informe_fiagro import subject_name
from apoio_informe_fiagro import subject_rows
from conftest import MIGRATION_001
from conftest import create_schema
from fundos.cadastro.loader import LoadError
from fundos.informe_fiagro import columns
from fundos.informe_fiagro.loader import ALREADY_LOADED
from fundos.informe_fiagro.loader import EMPTY_LABEL
from fundos.informe_fiagro.loader import INVALID_CNPJ
from fundos.informe_fiagro.loader import LOADED
from fundos.informe_fiagro.loader import NO_CLASS_ROW
from fundos.informe_fiagro.loader import NOT_FOUND
from fundos.informe_fiagro.loader import ONLY_FUND
from fundos.informe_fiagro.loader import PARSER_VERSION
from fundos.informe_fiagro.loader import REPEATED_KEY
from fundos.informe_fiagro.loader import REPEATED_SERIES
from fundos.informe_fiagro.loader import SAME_COMPETENCE
from fundos.informe_fiagro.loader import ClassResolver
from fundos.informe_fiagro.loader import find_loaded_informe
from fundos.informe_fiagro.loader import load_informe
from fundos.informe_fiagro.loader import match_counts
from fundos.informe_fiagro.reader import read_informe_bytes
from fundos.informe_fiagro.report import format_candidates_report
from fundos.informe_fiagro.report import format_load_report
from fundos.informe_fiagro.report import format_match_report
from fundos.repositories.observation_repository import ObservationRepository


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


@pytest.mark.parametrize(("second_version", "different"), (("1", 0), ("2", 1)))
def test_repeated_key_loads_nothing_of_that_class(loaded_db, second_version, different):
    informe = read_tables(
        merge(
            subject_rows(1),
            subject_rows(1, labels=(FIRST_SUBCLASS,), Nome_Classe="FIAGRO Exemplo 1B (ficticio)", Versao=second_version),
            subject_rows(2),
        )
    )
    result = load(loaded_db, informe)
    counts = result.counts

    assert informe.counts[("chaves", "repetidas_com_versao_diferente")] == different
    assert count(loaded_db, "observations", FIAGRO_CLASS_ROWS, (class_id(loaded_db, 1),)) == 0
    assert count(loaded_db, "quota_series", "fund_class_id = ?", (class_id(loaded_db, 1),)) == 0
    assert count(loaded_db, "party_observations", FIAGRO_CLASS_ROWS, (class_id(loaded_db, 1),)) == 0
    assert count(loaded_db, "observations", FIAGRO_CLASS_ROWS, (class_id(loaded_db, 2),)) == 122
    assert counts[("casamento", CLASS, REPEATED_KEY)] == 2
    assert counts[("casamento", SUBCLASS, REPEATED_KEY)] == 3
    assert counts[("classes", REPEATED_KEY)] == 1
    assert counts[("classes", LOADED)] == 1
    status, requested, successful, failed, summary = run_summary(loaded_db)
    assert (status, requested, successful, failed) == ("success", 2, 1, 0)
    assert json.loads(summary) == {"chaves_repetidas_nao_carregadas": 1}


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


def test_other_zip_of_the_same_competence_is_refused(loaded_db):
    load(loaded_db)
    other = read(build_informe_zip(subject_rows(1, Patrimonio_Liquido="2000"), date_time=(2026, 10, 31, 8, 0, 0)))
    before = snapshot(loaded_db)

    with pytest.raises(LoadError, match="reapresentacao do informe de FIAGRO ainda nao existe"):
        load(loaded_db, other, last_modified="2026-10-31T09:00:00Z")

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
