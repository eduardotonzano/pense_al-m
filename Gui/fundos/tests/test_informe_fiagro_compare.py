import pytest

from apoio import FAKE_CPF
from apoio_cadastro import fake_cnpj
from apoio_informe_fiagro import FIRST_SUBCLASS
from apoio_informe_fiagro import MANAGER_NAME
from apoio_informe_fiagro import SECOND_SUBCLASS
from apoio_informe_fiagro import ZIP_NAME
from apoio_informe_fiagro import build_informe_zip
from apoio_informe_fiagro import changed
from apoio_informe_fiagro import later_zip
from apoio_informe_fiagro import load_fictitious_cadastro
from apoio_informe_fiagro import merge
from apoio_informe_fiagro import subject_name
from apoio_informe_fiagro import subject_rows
from conftest import MIGRATION_001
from conftest import MIGRATIONS_DIR
from conftest import create_schema
from fundos.informe_fiagro import columns
from fundos.informe_fiagro.compare import DELIVERY_EARLIER
from fundos.informe_fiagro.compare import SAME_VERSION_CHANGED
from fundos.informe_fiagro.compare import VERSION_HIGHER
from fundos.informe_fiagro.compare import WITHHELD
from fundos.informe_fiagro.compare import Comparison
from fundos.informe_fiagro.loader import ClassResolver
from fundos.informe_fiagro.loader import load_informe
from fundos.informe_fiagro.reader import read_informe_bytes
from fundos.informe_fidc.compare import CHANGED
from fundos.informe_fidc.compare import EQUAL
from fundos.informe_fidc.compare import NEW
from fundos.informe_fidc.compare import RETURNS
from fundos.informe_fidc.compare import LatestValues
from fundos.informe_fidc.compare import _Values


CLASS = columns.CLASS_TABLE
SUBCLASS = columns.SUBCLASS_TABLE

TABLES = (
    "observations", "party_observations", "quota_series",
    "raw_records", "collection_runs", "data_conflicts", "party_conflicts",
)

# Motivo de retencao de teste (os da carga ficam em loader.py).
HELD = "retida no teste"


@pytest.fixture
def cadastro_db(full_db):
    """Cadastro ficticio de FIAGRO: classes 1, 2 e 3."""

    load_fictitious_cadastro(full_db, classes=(1, 2, 3))
    return full_db


def load(db, tables=None):
    with db.transaction() as connection:
        load_informe(connection, read_informe_bytes(build_informe_zip(tables), ZIP_NAME))


@pytest.fixture
def first_db(cadastro_db):
    """O primeiro ZIP (classe 1, com 2 subclasses) ja carregado."""

    load(cadastro_db)
    return cadastro_db


def class_id(connection, n):
    return connection.execute("SELECT id FROM fund_classes WHERE cnpj = ?", (fake_cnpj(n),)).fetchone()[0]


def compare(db, tables=None, withheld=()):
    """Compara um ZIP da semana seguinte com o banco, so lendo.

    withheld: (n, arquivos) das classes que a carga reteria; as linhas delas
    nesses arquivos nao sao comparadas.
    """

    informe = read_informe_bytes(later_zip(tables), ZIP_NAME)

    with db.connection() as connection:
        connection.execute("PRAGMA query_only = ON")
        resolver = ClassResolver(connection, informe)
        zip_ids = [
            row[0]
            for row in connection.execute(
                "SELECT id FROM raw_records WHERE parent_raw_record_id IS NULL AND file_name = ?"
                " AND processing_status = 'processed' ORDER BY id",
                (ZIP_NAME,),
            )
        ]
        comparison = Comparison(connection, informe, zip_ids)
        held = set()

        for n, files in withheld:
            comparison.withhold(class_id(connection, n), HELD, files)
            held.update((table, fake_cnpj(n)) for table in files)

        parties = comparison.parties()

        for table in columns.TABLES:
            state = comparison.table(table)

            for row in informe.rows(table):
                found, _ = resolver.resolve(row)

                if found is None or (table, row.cnpj) in held:
                    continue

                series_id = comparison.series_id(found, row.series_key) if table == SUBCLASS else None
                state.row(row, found, series_id)

                for party in row.parties:
                    parties.party(found, party)

            state.finish()

        parties.finish()
        return comparison.finish(), comparison


def cells(counts, status, table=None):
    tables = columns.TABLES if table is None else (table,)
    return sum(counts[("reapresentacao", "celulas", t, status)] for t in tables)


def vanished(counts, reason, table=None):
    tables = columns.TABLES if table is None else (table,)
    return sum(counts[("reapresentacao", "sumiram", t, reason)] for t in tables)


def total_cells(tables, table=None):
    informe = read_informe_bytes(build_informe_zip(tables), ZIP_NAME)
    files = columns.TABLES if table is None else (table,)
    return sum(len(r.values) for t in files for r in informe.rows(t))


def snapshot(db):
    with db.connection() as connection:
        return {t: connection.execute("SELECT COUNT(*) FROM " + t).fetchone()[0] for t in TABLES}


def test_the_latest_values_of_fidc_are_reused():
    values = LatestValues()
    values.load(("k",), "A")
    values.load(("k",), "B")
    values.loaded()

    assert LatestValues is _Values
    assert values.compare(("k",), "A") == (RETURNS, "B")


def test_same_values_are_all_equal_and_nothing_is_written(first_db):
    before = snapshot(first_db)
    counts, _ = compare(first_db)

    assert counts[("reapresentacao", "zips")] == 1
    assert cells(counts, EQUAL) == total_cells(None) == 122 + 2 * 3
    assert (cells(counts, CHANGED), cells(counts, NEW), cells(counts, RETURNS)) == (0, 0, 0)
    assert vanished(counts, "vazias") + vanished(counts, "sem_linha") == 0
    assert counts[("reapresentacao", "classes", "nos_dois")] == 1
    assert counts[("reapresentacao", "papeis", "administrador", "iguais")] == 1
    assert counts[("reapresentacao", "papeis", "gestor", "iguais")] == 1
    assert snapshot(first_db) == before


def test_changed_and_emptied_cells(first_db):
    counts, _ = compare(first_db, changed(inf_mensal_fiagro={"Patrimonio_Liquido": "2000", "Codigo_ISIN": ""}))

    assert cells(counts, CHANGED) == cells(counts, CHANGED, CLASS) == 1
    assert vanished(counts, "vazias") == vanished(counts, "vazias", CLASS) == 1
    assert vanished(counts, "sem_linha") == 0
    assert cells(counts, EQUAL) == total_cells(None) - 2


def test_new_class_and_its_series(first_db):
    counts, _ = compare(first_db, merge(subject_rows(1), subject_rows(2)))

    assert counts[("reapresentacao", "classes", "novas")] == 1
    assert counts[("reapresentacao", "classes", "sumiram")] == 0
    assert cells(counts, NEW) == total_cells(subject_rows(2))
    assert counts[("reapresentacao", "series", "novas")] == 2
    assert counts[("reapresentacao", "papeis", "gestor", "entrou")] == 1


def test_class_that_vanishes_is_counted_with_its_cells(cadastro_db):
    load(cadastro_db, merge(subject_rows(1), subject_rows(3)))
    counts, _ = compare(cadastro_db)

    assert counts[("reapresentacao", "classes", "sumiram")] == 1
    assert counts[("reapresentacao", "classes", "celulas_das_que_sumiram")] == total_cells(subject_rows(3))
    assert vanished(counts, "sem_linha") == total_cells(subject_rows(3))
    assert counts[("reapresentacao", "series", "sumiram")] == 2
    assert counts[("reapresentacao", "series", "possivel_troca_de_rotulo")] == 0
    assert counts[("reapresentacao", "papeis", "administrador", "saiu")] == 1
    assert counts[("reapresentacao", "papeis", "gestor", "saiu")] == 1


def test_label_that_changes_is_a_possible_swap(first_db):
    counts, _ = compare(first_db, subject_rows(1, labels=(FIRST_SUBCLASS, "Subclasse 3")))

    assert counts[("reapresentacao", "series", "novas")] == 1
    assert counts[("reapresentacao", "series", "sumiram")] == 1
    assert counts[("reapresentacao", "series", "possivel_troca_de_rotulo")] == 1
    assert vanished(counts, "sem_linha", SUBCLASS) == cells(counts, NEW, SUBCLASS) == 3


@pytest.mark.parametrize(
    "changes, role, status",
    [
        ({"Nome_Gestor": "Gestora Ficticia Renomeada Ltda"}, "gestor", "nome_alterado"),
        ({"CNPJ_Gestor": fake_cnpj(803)}, "gestor", "cnpj_trocado"),
        ({"CNPJ_Administrador": FAKE_CPF}, "administrador", "saiu"),
        ({"CNPJ_Administrador": "", "Nome_Administrador": ""}, "administrador", "saiu"),
    ],
)
def test_parties_by_position(first_db, changes, role, status):
    counts, _ = compare(first_db, changed(inf_mensal_fiagro=changes))

    assert counts[("reapresentacao", "papeis", role, status)] == 1


@pytest.mark.parametrize(
    "changes, expected",
    [
        ({"Versao": "2", "Data_Entrega": "2026-10-20"}, {VERSION_HIGHER: 1}),
        ({"Patrimonio_Liquido": "2000"}, {SAME_VERSION_CHANGED: 1}),
        ({"Data_Entrega": "2026-10-20"}, {SAME_VERSION_CHANGED: 1}),
        ({"Data_Entrega": "2026-10-10"}, {SAME_VERSION_CHANGED: 1, DELIVERY_EARLIER: 1}),
        ({"Versao": "2", "Data_Entrega": "2026-10-10"}, {VERSION_HIGHER: 1, DELIVERY_EARLIER: 1}),
        ({}, {}),
    ],
)
def test_version_and_delivery_are_counted_and_order_nothing(first_db, changes, expected):
    counts, _ = compare(first_db, changed(inf_mensal_fiagro=changes))
    found = {key[2]: n for key, n in counts.items() if key[:2] == ("reapresentacao", "versao") and n}

    assert found == expected
    # Versao e Data_Entrega sao celulas comuns: a mudanca delas e celula alterada.
    assert cells(counts, CHANGED, CLASS) == len(changes)


def test_versions_are_read_from_the_loaded_zips(cadastro_db):
    load(cadastro_db, merge(subject_rows(1, Versao="2"), subject_rows(2)))
    informe = read_informe_bytes(later_zip(), ZIP_NAME)

    with cadastro_db.connection() as connection:
        zip_ids = [row[0] for row in connection.execute("SELECT id FROM raw_records WHERE file_name = ?", (ZIP_NAME,))]

        assert Comparison(connection, informe, zip_ids).versions() == {class_id(connection, 1): "2", class_id(connection, 2): "1"}
        assert Comparison(connection, informe, []).versions() == {}


def test_withheld_subclasses_are_not_gone_nor_a_possible_swap(first_db):
    # Sem retencao, as subclasses que nao vieram somem; retidas, so sao contadas a parte.
    absent, _ = compare(first_db, {CLASS: subject_rows(1)[CLASS], SUBCLASS: []})
    counts, _ = compare(first_db, subject_rows(1, labels=("Subclasse 7", "Subclasse 8")), withheld=((1, (SUBCLASS,)),))

    assert absent[("reapresentacao", "series", "sumiram")] == 2
    assert counts[("reapresentacao", "series", "sumiram")] == 0
    assert counts[("reapresentacao", "series", "novas")] == 0
    assert counts[("reapresentacao", "series", "possivel_troca_de_rotulo")] == 0
    assert counts[("reapresentacao", "series", "retidas")] == 2
    assert counts[("reapresentacao", "retidas", SUBCLASS, HELD)] == 6
    assert vanished(counts, "sem_linha") + vanished(counts, "vazias") == 0
    assert counts[("reapresentacao", "classes", "nos_dois")] == 1
    assert cells(counts, EQUAL, CLASS) == 122


def test_withheld_class_is_not_gone_and_its_parties_are_withheld(first_db):
    counts, _ = compare(first_db, withheld=((1, columns.TABLES),))

    assert counts[("reapresentacao", "classes", "sumiram")] == 0
    assert counts[("reapresentacao", "classes", "retidas")] == 1
    assert counts[("reapresentacao", "retidas", CLASS, HELD)] == 122
    assert counts[("reapresentacao", "retidas", SUBCLASS, HELD)] == 6
    assert counts[("reapresentacao", "series", "retidas")] == 2
    assert counts[("reapresentacao", "papeis", "gestor", WITHHELD)] == 1
    assert counts[("reapresentacao", "papeis", "administrador", WITHHELD)] == 1
    assert counts[("reapresentacao", "papeis", "gestor", "saiu")] == 0
    assert vanished(counts, "sem_linha") == 0


def test_database_with_only_migrations_001_and_002(tmp_path):
    db = create_schema(tmp_path / "fundos.db", (MIGRATION_001, MIGRATIONS_DIR / "002_party_observations.sql"))
    load_fictitious_cadastro(db, classes=(1,))
    load(db)
    counts, _ = compare(db, changed(inf_mensal_fiagro={"Nome_Gestor": "Gestora Ficticia Renomeada Ltda"}))

    assert counts[("reapresentacao", "papeis", "gestor", "nome_alterado")] == 1
    assert counts[("reapresentacao", "papeis", "administrador", "iguais")] == 1


def test_counts_have_no_identifier_name_or_value(first_db):
    counts, _ = compare(first_db, changed(inf_mensal_fiagro={"Patrimonio_Liquido": "98765.4321", "Nome_Gestor": "Renomeada"}))
    text = repr(sorted(counts.items()))

    for secret in (fake_cnpj(1), subject_name(1), MANAGER_NAME, "Renomeada", "98765.4321", FIRST_SUBCLASS, SECOND_SUBCLASS):
        assert secret not in text
