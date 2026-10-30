import pytest

from apoio_cadastro import fake_cnpj
from apoio_cadastro import masked
from apoio_informe_fidc import SENIOR
from apoio_informe_fidc import ZIP_NAME
from apoio_informe_fidc import build_informe_zip
from apoio_informe_fidc import changed
from apoio_informe_fidc import later_zip
from apoio_informe_fidc import load_fictitious_cadastro
from apoio_informe_fidc import merge
from apoio_informe_fidc import subject_rows
from fundos.informe_fidc import columns
from fundos.informe_fidc.compare import CHANGED
from fundos.informe_fidc.compare import EQUAL
from fundos.informe_fidc.compare import NEW
from fundos.informe_fidc.compare import RETURNS
from fundos.informe_fidc.compare import _Values
from fundos.informe_fidc.loader import SubjectResolver
from fundos.informe_fidc.loader import load_informe
from fundos.informe_fidc.loader import reapresentation_counts
from fundos.informe_fidc.reader import read_informe_bytes
from fundos.informe_fidc.report import LOADED_TABLES
from fundos.informe_fidc.report import format_reapresentation_report


TABLES = (
    "observations", "party_observations", "party_observation_shares", "quota_series",
    "raw_records", "collection_runs", "data_conflicts", "party_conflicts",
)


@pytest.fixture
def cadastro_db(full_db):
    """Cadastro ficticio: classe 1 (fundo 1), fundo 2 sem classe, classe 3 do fundo 1."""

    load_fictitious_cadastro(full_db, classes=(1,), funds_without_class=(2,), extra_classes=((3, 1),))
    return full_db


def load(db, tables=None):
    with db.transaction() as connection:
        load_informe(connection, read_informe_bytes(build_informe_zip(tables), ZIP_NAME))


@pytest.fixture
def first_db(cadastro_db):
    """O primeiro ZIP (assunto 1) ja carregado."""

    load(cadastro_db)
    return cadastro_db


def compare(db, tables=None):
    informe = read_informe_bytes(later_zip(tables), ZIP_NAME)

    with db.connection() as connection:
        return reapresentation_counts(connection, informe, SubjectResolver(connection))


def cells(counts, status, table=None):
    tables = LOADED_TABLES if table is None else (table,)
    return sum(counts[("reapresentacao", "celulas", t, status)] for t in tables)


def vanished(counts, reason, table=None):
    tables = LOADED_TABLES if table is None else (table,)
    return sum(counts[("reapresentacao", "sumiram", t, reason)] for t in tables)


def total_cells(tables):
    informe = read_informe_bytes(build_informe_zip(tables), ZIP_NAME)
    return sum(
        len(r.values)
        for table in LOADED_TABLES
        for r in informe.rows(table)
        if table not in columns.SERIES_TABLES or r.series_key is not None
    )


def snapshot(db):
    with db.connection() as connection:
        return {t: connection.execute("SELECT COUNT(*) FROM " + t).fetchone()[0] for t in TABLES}


def test_values_keep_the_latest_and_the_older_ones():
    values = _Values()
    values.load(("k",), "A")
    values.load(("k",), "B")
    values.loaded()

    assert values.compare(("k",), "B") == (EQUAL, "B")
    assert values.compare(("k",), "A") == (RETURNS, "B")
    assert values.compare(("k",), "C") == (CHANGED, "A")
    assert values.compare(("outra",), "A") == (NEW, None)
    assert values.pending == set()


def test_same_values_are_all_equal_and_nothing_is_written(first_db):
    before = snapshot(first_db)
    counts = compare(first_db)

    assert counts[("reapresentacao", "zips")] == 1
    assert cells(counts, EQUAL) == total_cells(None)
    assert (cells(counts, CHANGED), cells(counts, NEW), cells(counts, RETURNS)) == (0, 0, 0)
    assert vanished(counts, "vazias") + vanished(counts, "sem_linha") == 0
    assert counts[("reapresentacao", "assuntos", "nos_dois")] == 1
    assert counts[("reapresentacao", "papeis", "administrador", "iguais")] == 1
    assert counts[("reapresentacao", "papeis", "cedente", "iguais")] == 1
    assert snapshot(first_db) == before


def test_changed_and_emptied_cells(first_db):
    counts = compare(first_db, changed(tab_IV={"TAB_IV_A_VL_PL": "1200.00"}, tab_X={"TAB_X_DEBITO_TRIBUT": ""}))

    assert cells(counts, CHANGED) == 1
    assert cells(counts, CHANGED, "tab_IV") == 1
    assert vanished(counts, "vazias") == 1
    assert vanished(counts, "vazias", "tab_X") == 1
    assert vanished(counts, "sem_linha") == 0
    assert cells(counts, EQUAL) == total_cells(None) - 2


def test_new_subject_and_its_series(first_db):
    counts = compare(first_db, merge(subject_rows(1), subject_rows(3)))

    assert counts[("reapresentacao", "assuntos", "novos")] == 1
    assert counts[("reapresentacao", "assuntos", "sumiram")] == 0
    assert cells(counts, NEW) == total_cells(subject_rows(3))
    assert counts[("reapresentacao", "series", "novas")] == 2
    assert counts[("reapresentacao", "papeis", "cedente", "entrou")] == 1


def test_subject_that_vanishes_is_counted_with_its_cells(cadastro_db):
    load(cadastro_db, merge(subject_rows(1), subject_rows(3)))
    counts = compare(cadastro_db)

    assert counts[("reapresentacao", "assuntos", "sumiram")] == 1
    assert counts[("reapresentacao", "assuntos", "celulas_dos_que_sumiram")] == total_cells(subject_rows(3))
    assert vanished(counts, "sem_linha") == total_cells(subject_rows(3))
    assert counts[("reapresentacao", "series", "sumiram")] == 2
    assert counts[("reapresentacao", "series", "possivel_troca_de_rotulo")] == 0
    assert counts[("reapresentacao", "papeis", "cedente", "saiu")] == 1


def test_label_that_changes_is_a_possible_swap(first_db):
    renamed = "Subclasse Senior Serie Unica"
    tables = subject_rows()

    for table in columns.SERIES_TABLES:
        tables[table] = [
            dict(r, TAB_X_CLASSE_SERIE=renamed) if r["TAB_X_CLASSE_SERIE"] == SENIOR else r
            for r in tables[table]
        ]

    counts = compare(first_db, tables)

    assert counts[("reapresentacao", "series", "novas")] == 1
    assert counts[("reapresentacao", "series", "sumiram")] == 1
    assert counts[("reapresentacao", "series", "possivel_troca_de_rotulo")] == 1
    assert vanished(counts, "sem_linha") == cells(counts, NEW)


def test_subclass_id_that_appears_or_disappears(cadastro_db):
    load(cadastro_db, subject_rows(subclass_ids=("", "")))

    appears = compare(cadastro_db, subject_rows(subclass_ids=("SUBFICTICIA0001", "")))

    assert appears[("reapresentacao", "id_subclasse", "aparece")] == 1
    assert appears[("reapresentacao", "series", "novas")] == 0


def test_subclass_id_that_disappears(first_db):
    counts = compare(first_db, subject_rows(subclass_ids=("", "")))

    assert counts[("reapresentacao", "id_subclasse", "some")] == 1
    assert counts[("reapresentacao", "series", "novas")] == 0


@pytest.mark.parametrize(
    "changes, role, status",
    [
        ({"TAB_I2B12_PR_CEDENTE_1": "12.5"}, "cedente", "percentual_alterado"),
        ({"TAB_I2B12_CPF_CNPJ_CEDENTE_1": fake_cnpj(556)}, "cedente", "cnpj_trocado"),
        ({"TAB_I2B12_CPF_CNPJ_CEDENTE_2": fake_cnpj(557), "TAB_I2B12_PR_CEDENTE_2": "5"}, "cedente", "entrou"),
        ({"TAB_I2B12_CPF_CNPJ_CEDENTE_1": "", "TAB_I2B12_PR_CEDENTE_1": ""}, "cedente", "saiu"),
        ({"ADMIN": "Administradora Ficticia Renomeada SA"}, "administrador", "nome_alterado"),
        ({"CNPJ_ADMIN": masked(fake_cnpj(902))}, "administrador", "cnpj_trocado"),
    ],
)
def test_parties_by_position(first_db, changes, role, status):
    counts = compare(first_db, changed(tab_I=changes))

    assert counts[("reapresentacao", "papeis", role, status)] == 1


def test_subject_outside_the_cadastro_is_not_compared(first_db):
    counts = compare(first_db, merge(subject_rows(1), subject_rows(99)))

    assert counts[("reapresentacao", "assuntos", "novos")] == 0
    assert counts[("casamento", "tab_I", "Classe: CNPJ fora do cadastro carregado")] == 1
    assert cells(counts, NEW) == 0


def test_report_has_only_counts(first_db):
    counts = compare(first_db, changed(tab_IV={"TAB_IV_A_VL_PL": "1200.00"}, tab_I={"TAB_I2B12_PR_CEDENTE_1": "12.5"}))
    text = "\n".join(format_reapresentation_report(counts))

    assert "  celulas tab_IV: iguais " in text
    assert "alteradas 1" in text
    assert "percentual alterado 1" in text

    for secret in (fake_cnpj(1), masked(fake_cnpj(1)), fake_cnpj(555), fake_cnpj(901), "1200", "12.5", "Ficticia", "ficticio", SENIOR):
        assert secret not in text
