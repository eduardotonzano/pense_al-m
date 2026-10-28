import re

import pytest

from apoio import FAKE_CPF
from apoio import FAKE_CPF_MASKED
from apoio_cadastro import DIRECTOR_NAME
from apoio_cadastro import PF_AUDITOR_NAME
from apoio_cadastro import PF_MANAGER_NAME
from apoio_cadastro import REFERENCE_DATE
from apoio_cadastro import build_zip
from apoio_cadastro import class_row
from apoio_cadastro import fake_cnpj
from apoio_cadastro import fund_row
from apoio_cadastro import pf_manager_row
from conftest import create_schema
from fundos.cadastro.loader import LoadError
from fundos.cadastro.loader import find_loaded_zip
from fundos.cadastro.loader import load_cadastro
from fundos.cadastro.loader import missing_migrations
from fundos.cadastro.reader import read_cadastro_bytes
from fundos.cadastro.selection import select_fidc_fiagro
from fundos.personal_data import find_cpf_columns
from fundos.repositories.observation_repository import ObservationRepository


TWO_MANAGERS = [
    fund_row(),
    fund_row(CPF_CNPJ_Gestor=fake_cnpj(802), Gestor="Segunda Gestora Ficticia"),
]


def load(db, data, reference=REFERENCE_DATE):
    cadastro = read_cadastro_bytes(data, "registro_fundo_classe.zip")
    selection = select_fidc_fiagro(cadastro)

    with db.transaction() as connection:
        return load_cadastro(connection, cadastro, selection, reference)


def count(db, table, where="1 = 1", parameters=()):
    with db.connection() as connection:
        return connection.execute(
            "SELECT COUNT(*) FROM " + table + " WHERE " + where,
            parameters,
        ).fetchone()[0]


def rows(db, sql, parameters=()):
    with db.connection() as connection:
        return [tuple(row) for row in connection.execute(sql, parameters)]


def snapshot(db):
    tables = (
        "funds", "fund_classes", "observations", "party_observations",
        "raw_records", "data_conflicts", "party_conflicts",
    )
    return {table: count(db, table) for table in tables}


def all_text_values(db):
    """Todo valor de texto de todas as tabelas do banco."""

    values = []

    with db.connection() as connection:
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        ]

        for table in tables:
            for row in connection.execute('SELECT * FROM "' + table + '"'):
                values.extend(str(value) for value in tuple(row) if isinstance(value, str))

    return values


def test_loads_funds_classes_observations_parties_and_manifest(full_db):
    data = build_zip(TWO_MANAGERS, [class_row()])
    result = load(full_db, data)

    assert result.status == "success"
    assert count(full_db, "funds") == 1
    assert count(full_db, "fund_classes") == 1
    assert rows(full_db, "SELECT DISTINCT reference_date FROM observations") == [(REFERENCE_DATE,)]
    assert rows(
        full_db,
        "SELECT value_type, COUNT(*) FROM observations GROUP BY value_type ORDER BY value_type",
    ) == [("boolean", 2), ("date", 12), ("numeric", 2), ("text", 15)]
    assert rows(
        full_db,
        "SELECT role, COUNT(*) FROM party_observations GROUP BY role ORDER BY role",
    ) == [("administrador", 1), ("auditor", 1), ("custodiante", 1), ("gestor", 2)]
    assert count(full_db, "data_conflicts") == 0
    assert count(full_db, "party_conflicts") == 0
    assert rows(
        full_db,
        "SELECT field_name FROM observations WHERE field_name LIKE 'registro_fundo.%'"
        " AND field_name = 'registro_fundo.Patrimonio_Liquido'",
    ) == [("registro_fundo.Patrimonio_Liquido",)]

    with full_db.connection() as connection:
        fund_id = connection.execute("SELECT id FROM funds").fetchone()[0]
        pl = ObservationRepository(connection).get_current(
            fund_id=fund_id,
            field_name="registro_fundo.Patrimonio_Liquido",
        )

    assert pl.value_numeric == "1000.5"


def test_manifest_has_the_zip_and_the_three_csv(full_db):
    data = build_zip(TWO_MANAGERS, [class_row()])
    cadastro = read_cadastro_bytes(data, "registro_fundo_classe.zip")
    load(full_db, data)

    manifest = rows(
        full_db,
        "SELECT file_name, sha256, line_count, processing_status, parser_version,"
        " parent_raw_record_id IS NULL FROM raw_records ORDER BY id",
    )

    assert manifest[0] == (
        "registro_fundo_classe.zip",
        cadastro.zip.sha256,
        None,
        "processed",
        "fundos.cadastro.v1",
        1,
    )
    assert manifest[1:] == [
        (m.file_name, m.sha256, m.line_count, status, "fundos.cadastro.v1", 0)
        for m, status in zip(cadastro.members, ("processed", "processed", "ignored"))
    ]
    assert rows(full_db, "SELECT status, requested_items, successful_items FROM collection_runs") == [
        ("success", 2, 2)
    ]


def test_cpf_and_forbidden_fields_never_reach_the_database(full_db):
    data = build_zip(
        [pf_manager_row(), fund_row(ID_Registro_Fundo="2", CNPJ_Fundo=fake_cnpj(2), CPF_CNPJ_Gestor=FAKE_CPF_MASKED, Gestor=PF_MANAGER_NAME)],
        [class_row(CNPJ_Auditor=FAKE_CPF, Auditor=PF_AUDITOR_NAME)],
    )
    load(full_db, data)
    values = all_text_values(full_db)
    cpf_like = re.compile(r"[0-9]{11}|[0-9]{3}\.[0-9]{3}\.[0-9]{3}-[0-9]{2}")

    with full_db.connection() as connection:
        assert find_cpf_columns(connection) == []

    assert count(full_db, "observations") > 0

    for secret in (FAKE_CPF, FAKE_CPF_MASKED, PF_MANAGER_NAME, PF_AUDITOR_NAME, DIRECTOR_NAME):
        assert not any(secret in value for value in values)

    assert not any(cpf_like.fullmatch(value.strip()) for value in values)
    assert count(full_db, "observations", "field_name LIKE '%Diretor%'") == 0
    assert count(full_db, "party_observations", "role = 'gestor'") == 0


def test_natural_person_manager_only_records_the_type(full_db):
    load(full_db, build_zip([pf_manager_row()], [class_row()]))

    assert rows(
        full_db,
        "SELECT value_text FROM observations WHERE field_name = 'registro_fundo.Tipo_Pessoa_Gestor'",
    ) == [("PF",)]
    assert count(full_db, "party_observations", "role = 'gestor'") == 0
    assert count(full_db, "party_observations", "role = 'administrador'") == 1


def test_several_managers_record_parties_without_conflict(full_db):
    load(full_db, build_zip(TWO_MANAGERS, [class_row()]))

    assert rows(
        full_db,
        "SELECT party_cnpj, party_name FROM party_observations WHERE role = 'gestor' ORDER BY party_cnpj",
    ) == [
        (fake_cnpj(801), "Gestora Ficticia Ltda"),
        (fake_cnpj(802), "Segunda Gestora Ficticia"),
    ]
    assert count(full_db, "data_conflicts") == 0
    assert count(full_db, "party_conflicts") == 0


def test_loading_the_same_zip_twice_duplicates_nothing(full_db):
    data = build_zip(TWO_MANAGERS, [class_row()])
    load(full_db, data)
    before = snapshot(full_db)

    second = load(full_db, data)

    assert snapshot(full_db) == before
    assert second.counts[("funds", "criados")] == 0
    assert second.counts[("fund_classes", "criadas")] == 0
    assert sum(n for key, n in second.counts.items() if key[0] == "observacoes" and key[-1] == "criadas") == 0
    assert sum(n for key, n in second.counts.items() if key[0] == "papeis" and key[-1] == "criados") == 0


def test_reapresentation_with_other_values_opens_conflicts(full_db):
    load(full_db, build_zip(TWO_MANAGERS, [class_row()]))
    changed = [dict(row, Patrimonio_Liquido="1200.00", Administrador="Administradora Ficticia Renomeada") for row in TWO_MANAGERS]

    result = load(full_db, build_zip(changed, [class_row()]))

    assert result.counts[("conflitos", "data_conflicts")] == 1
    assert result.counts[("conflitos", "party_conflicts")] == 1
    assert rows(
        full_db,
        "SELECT value_numeric FROM observations WHERE field_name = 'registro_fundo.Patrimonio_Liquido' ORDER BY id",
    ) == [("1000.5",), ("1200",)]
    assert count(full_db, "party_observations", "role = 'administrador'") == 2
    assert count(full_db, "raw_records", "parent_raw_record_id IS NULL") == 2


def test_new_reference_date_is_history_without_conflict(full_db):
    data = build_zip(TWO_MANAGERS, [class_row()])
    load(full_db, data)
    first = count(full_db, "observations")

    load(full_db, data, reference="2026-10-28")

    assert count(full_db, "observations") == 2 * first
    assert count(full_db, "data_conflicts") == 0


def test_failure_rolls_back_everything(full_db, monkeypatch):
    calls = []
    original = ObservationRepository.record

    def failing(self, **arguments):
        calls.append(1)

        if len(calls) == 5:
            raise RuntimeError("falha simulada")

        return original(self, **arguments)

    monkeypatch.setattr(ObservationRepository, "record", failing)

    with pytest.raises(RuntimeError, match="falha simulada"):
        load(full_db, build_zip(TWO_MANAGERS, [class_row()]))

    assert set(snapshot(full_db).values()) == {0}
    assert count(full_db, "collection_runs") == 0


def test_cpf_like_text_in_a_recorded_field_undoes_the_load(full_db):
    data = build_zip([fund_row(Denominacao_Social="12345678901")], [class_row()])

    with pytest.raises(LoadError, match="Texto com formato de CPF"):
        load(full_db, data)

    assert set(snapshot(full_db).values()) == {0}


def test_identity_conflict_blocks_only_the_class(full_db):
    with full_db.connection() as connection:
        connection.execute("INSERT INTO funds (cnpj) VALUES (?)", (fake_cnpj(50),))
        connection.execute(
            "INSERT INTO fund_classes (fund_id, cnpj) VALUES (1, ?)",
            (fake_cnpj(1),),
        )

    result = load(full_db, build_zip(TWO_MANAGERS, [class_row()]))

    assert result.status == "partial"
    assert result.counts[("fund_classes", "bloqueadas")] == 1
    assert count(full_db, "observations", "fund_class_id IS NOT NULL") == 0
    assert rows(full_db, "SELECT status, failed_items FROM collection_runs") == [("partial", 1)]


def test_missing_migrations_and_loaded_zip(tmp_path, full_db):
    with create_schema(tmp_path / "versao_1.db").connection() as connection:
        assert missing_migrations(connection) == ["002_party_observations"]

    data = build_zip(TWO_MANAGERS, [class_row()])
    cadastro = read_cadastro_bytes(data, "registro_fundo_classe.zip")

    with full_db.connection() as connection:
        assert missing_migrations(connection) == []
        assert find_loaded_zip(connection, cadastro.zip) is None

    load(full_db, data)

    with full_db.connection() as connection:
        loaded = find_loaded_zip(connection, cadastro.zip)

    assert loaded.reference_dates == (REFERENCE_DATE,)
