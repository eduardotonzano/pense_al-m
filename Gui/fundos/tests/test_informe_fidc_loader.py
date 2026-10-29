import re

import pytest

from apoio import FAKE_CPF
from apoio_cadastro import fake_cnpj
from apoio_informe_fidc import ADMIN_NAME
from apoio_informe_fidc import COMPETENCE
from apoio_informe_fidc import SENIOR
from apoio_informe_fidc import SUBORDINATE
from apoio_informe_fidc import SUBORDINATE_X1
from apoio_informe_fidc import ZIP_NAME
from apoio_informe_fidc import build_informe_zip
from apoio_informe_fidc import load_fictitious_cadastro
from apoio_informe_fidc import merge
from apoio_informe_fidc import row
from apoio_informe_fidc import subject_rows
from fundos.cadastro.loader import LoadError
from fundos.informe_fidc import columns
from fundos.informe_fidc.loader import ALREADY_LOADED
from fundos.informe_fidc.loader import CLASS_NOT_FOUND
from fundos.informe_fidc.loader import CLASS_ONLY_FUND
from fundos.informe_fidc.loader import FUND_NOT_FOUND
from fundos.informe_fidc.loader import FUND_ONLY_CLASS
from fundos.informe_fidc.loader import SAME_COMPETENCE
from fundos.informe_fidc.loader import SubjectResolver
from fundos.informe_fidc.loader import find_loaded_informe
from fundos.informe_fidc.loader import load_informe
from fundos.informe_fidc.loader import match_counts
from fundos.informe_fidc.reader import read_informe_bytes
from fundos.repositories.observation_repository import ObservationRepository
from fundos.repositories.quota_series_repository import QuotaSeriesRepository


INFORME_TABLES = (
    "observations", "party_observations", "quota_series", "raw_records",
    "collection_runs", "data_conflicts", "party_conflicts",
)


@pytest.fixture
def loaded_db(full_db):
    """Cadastro ficticio: classe 1 (fundo 1), fundo 2 sem classe, classe 3 do fundo 1."""

    load_fictitious_cadastro(full_db, classes=(1,), funds_without_class=(2,), extra_classes=((3, 1),))
    return full_db


def read(data=None, name=ZIP_NAME):
    return read_informe_bytes(build_informe_zip() if data is None else data, name)


def load(db, informe=None, progress=None):
    informe = read() if informe is None else informe

    with db.transaction() as connection:
        return load_informe(connection, informe, progress=progress)


def rows(db, sql, parameters=()):
    with db.connection() as connection:
        return [tuple(r) for r in connection.execute(sql, parameters)]


def count(db, table, where="1 = 1", parameters=()):
    return rows(db, "SELECT COUNT(*) FROM " + table + " WHERE " + where, parameters)[0][0]


def snapshot(db):
    return {table: count(db, table) for table in INFORME_TABLES + ("funds", "fund_classes")}


def subject_id(db, table, n):
    return rows(db, "SELECT id FROM " + table + " WHERE cnpj = ?", (fake_cnpj(n),))[0][0]


def expected_values(informe):
    return sum(
        len(r.values)
        for table in columns.TABLES
        if table not in columns.NOT_LOADED
        for r in informe.rows(table)
    )


def test_refuses_without_the_cadastro(full_db):
    with pytest.raises(LoadError, match="cadastro nao foi carregado"):
        load(full_db)

    assert count(full_db, "raw_records") == 0


def test_loads_observations_series_and_administrator(loaded_db):
    informe = read()
    before = count(loaded_db, "observations")
    result = load(loaded_db, informe)
    class_id = subject_id(loaded_db, "fund_classes", 1)

    assert result.status == "success"
    assert count(loaded_db, "observations") - before == expected_values(informe)
    assert rows(loaded_db, "SELECT DISTINCT reference_date FROM observations WHERE field_name LIKE 'tab%'") == [(COMPETENCE,)]
    assert count(loaded_db, "observations", "field_name LIKE 'tab_VIII.%' OR field_name LIKE 'tab_X_4.%'") == 0
    assert count(loaded_db, "observations", "field_name LIKE '%.DENOM_SOCIAL'") == 1
    assert count(
        loaded_db,
        "observations",
        "field_name LIKE '%.TP_FUNDO_CLASSE' OR field_name LIKE '%.CNPJ_FUNDO_CLASSE' OR field_name LIKE '%.DT_COMPTC'",
    ) == 0
    assert rows(
        loaded_db,
        "SELECT value_numeric FROM observations WHERE fund_class_id = ? AND field_name = 'tab_IV.TAB_IV_A_VL_PL'",
        (class_id,),
    ) == [("1000.5",)]
    assert count(loaded_db, "data_conflicts") == 0
    assert rows(
        loaded_db,
        "SELECT role, field_name, party_cnpj, name_field_name, party_name FROM party_observations"
        " WHERE fund_class_id = ? AND field_name LIKE 'tab_I.%'",
        (class_id,),
    ) == [("administrador", "tab_I.CNPJ_ADMIN", fake_cnpj(901), "tab_I.ADMIN", ADMIN_NAME)]
    assert rows(loaded_db, "SELECT status, requested_items, successful_items, failed_items FROM collection_runs ORDER BY id DESC LIMIT 1") == [
        ("success", 1, 1, 0)
    ]


def test_x1_and_x2_fall_on_the_same_series(loaded_db):
    load(loaded_db)
    class_id = subject_id(loaded_db, "fund_classes", 1)
    series = rows(
        loaded_db,
        "SELECT id, series_label_key, cvm_subclass_id FROM quota_series WHERE fund_class_id = ? ORDER BY id",
        (class_id,),
    )

    assert [(key, sid) for _, key, sid in series] == [
        ("subclasse senior serie 1", "SUBFICTICIA0001"),
        ("subclasse subordinada subordinada 1", None),
    ]
    subordinate = series[1][0]
    assert rows(
        loaded_db,
        "SELECT field_name, value_text FROM observations WHERE quota_series_id = ? AND field_name LIKE '%.TAB_X_CLASSE_SERIE' ORDER BY field_name",
        (subordinate,),
    ) == [
        ("tab_X_1.TAB_X_CLASSE_SERIE", SUBORDINATE_X1),
        ("tab_X_2.TAB_X_CLASSE_SERIE", SUBORDINATE),
        ("tab_X_3.TAB_X_CLASSE_SERIE", SUBORDINATE),
        ("tab_X_6.TAB_X_CLASSE_SERIE", SUBORDINATE),
    ]
    assert rows(
        loaded_db,
        "SELECT value_text FROM observations WHERE quota_series_id = ? AND field_name = 'tab_X_1.ID_SUBCLASSE'",
        (series[0][0],),
    ) == [("SUBFICTICIA0001",)]
    assert count(loaded_db, "observations", "quota_series_id IS NOT NULL AND field_name = 'tab_X_2.TAB_X_VL_COTA'") == 2


def test_manifest_has_the_zip_and_the_18_csv(loaded_db):
    informe = read()
    load(loaded_db, informe)
    manifest = rows(
        loaded_db,
        "SELECT r.file_name, r.sha256, r.line_count, r.processing_status, r.parser_version"
        " FROM raw_records r JOIN raw_records z ON z.id = r.parent_raw_record_id"
        " WHERE z.sha256 = ? ORDER BY r.id",
        (informe.zip.sha256,),
    )

    assert len(manifest) == 18
    assert [m[0] for m in manifest] == [columns.member_name(t, "202609") for t in columns.TABLES]
    assert {m[0]: m[3] for m in manifest}[columns.member_name("tab_VIII", "202609")] == "ignored"
    assert {m[0]: m[3] for m in manifest}[columns.member_name("tab_X_4", "202609")] == "ignored"
    assert sum(1 for m in manifest if m[3] == "processed") == 16
    assert all(m[4] == "fundos.informe_fidc.v1" for m in manifest)
    assert [m[2] for m in manifest] == [informe.member(t).line_count for t in columns.TABLES]


def test_subjects_are_resolved_and_the_rest_counted_by_reason(loaded_db):
    tables = merge(
        subject_rows(1, subclass_ids=("SUBFICTICIA0011", "")),
        subject_rows(2, "Fundo", subclass_ids=("SUBFICTICIA0012", "")),
        subject_rows(2, "Classe", subclass_ids=("SUBFICTICIA0013", "")),
        subject_rows(9, "Classe", subclass_ids=("SUBFICTICIA0014", "")),
        subject_rows(3, "Fundo", subclass_ids=("SUBFICTICIA0015", "")),
        subject_rows(8, "Fundo", subclass_ids=("SUBFICTICIA0016", "")),
    )
    before = snapshot(loaded_db)
    result = load(loaded_db, read(build_informe_zip(tables)))
    counts = result.counts
    fund_id = subject_id(loaded_db, "funds", 2)

    for outcome in ("classe", "fundo", CLASS_ONLY_FUND, CLASS_NOT_FOUND, FUND_ONLY_CLASS, FUND_NOT_FOUND):
        assert counts[("assuntos", outcome)] == 1
        assert counts[("casamento", "tab_I", outcome)] == 1
        assert counts[("casamento", "tab_X_4", outcome)] == 4

    after = snapshot(loaded_db)
    assert (after["funds"], after["fund_classes"]) == (before["funds"], before["fund_classes"])
    assert count(loaded_db, "observations", "fund_id = ? AND field_name LIKE 'tab_I.%'", (fund_id,)) > 0
    assert count(loaded_db, "quota_series", "fund_id = ?", (fund_id,)) == 2
    assert rows(loaded_db, "SELECT error_summary FROM collection_runs ORDER BY id DESC LIMIT 1") == [
        ('{"assuntos_fora_do_cadastro":4}',)
    ]


def test_subclass_id_shared_between_subjects_is_not_a_key(loaded_db):
    tables = merge(
        subject_rows(1, subclass_ids=("SUBFICTICIA0009", "")),
        subject_rows(3, subclass_ids=("SUBFICTICIA0009", "")),
    )
    result = load(loaded_db, read(build_informe_zip(tables)))

    assert count(loaded_db, "quota_series", "cvm_subclass_id IS NOT NULL") == 0
    assert count(loaded_db, "observations", "field_name = 'tab_X_1.ID_SUBCLASSE'") == 2
    assert result.counts[("id_subclasse", "chave")] == 0
    assert result.status == "success"


def test_subclass_id_refused_by_the_database_still_loads_by_label(loaded_db):
    with loaded_db.connection() as connection:
        QuotaSeriesRepository(connection).get_or_create(
            fund_class_id=subject_id(loaded_db, "fund_classes", 3),
            label="Outra Serie Ficticia",
            cvm_subclass_id="SUBFICTICIA0001",
        )

    result = load(loaded_db)
    class_id = subject_id(loaded_db, "fund_classes", 1)
    senior = rows(
        loaded_db,
        "SELECT id, cvm_subclass_id FROM quota_series WHERE fund_class_id = ? AND series_label_key = 'subclasse senior serie 1'",
        (class_id,),
    )

    assert result.status == "partial"
    assert result.counts[("id_subclasse", "recusado")] == 1
    assert senior[0][1] is None
    assert rows(
        loaded_db,
        "SELECT value_text FROM observations WHERE quota_series_id = ? AND field_name = 'tab_X_1.ID_SUBCLASSE'",
        (senior[0][0],),
    ) == [("SUBFICTICIA0001",)]
    assert count(loaded_db, "observations", "quota_series_id = ? AND field_name = 'tab_X_1.TAB_X_NR_COTST'", (senior[0][0],)) == 1
    assert rows(loaded_db, "SELECT status, failed_items, error_summary FROM collection_runs ORDER BY id DESC LIMIT 1") == [
        ("partial", 1, '{"id_subclasse_recusado":1}')
    ]


def test_same_zip_and_same_competence_are_refused(loaded_db):
    informe = read()
    load(loaded_db, informe)
    before = snapshot(loaded_db)
    other_tables = subject_rows()
    other_tables["tab_IV"] = [row("tab_IV", TAB_IV_A_VL_PL="1200.00")]
    other = read(build_informe_zip(other_tables))

    with loaded_db.connection() as connection:
        assert find_loaded_informe(connection, informe) == ALREADY_LOADED
        assert find_loaded_informe(connection, other) == SAME_COMPETENCE

    with pytest.raises(LoadError, match="mesmo ZIP"):
        load(loaded_db, informe)

    with pytest.raises(LoadError, match="FU4.2"):
        load(loaded_db, other)

    assert snapshot(loaded_db) == before


def test_new_competence_is_history_without_conflict(loaded_db):
    load(loaded_db)
    first = count(loaded_db, "observations", "field_name LIKE 'tab%'")
    august = {
        table: [dict(r, DT_COMPTC="2026-08-31") for r in table_rows]
        for table, table_rows in subject_rows().items()
    }
    informe = read(build_informe_zip(august, period="202608"), "inf_mensal_fidc_202608.zip")

    result = load(loaded_db, informe)

    assert result.status == "success"
    assert count(loaded_db, "observations", "field_name LIKE 'tab%'") == 2 * first
    assert count(loaded_db, "data_conflicts") == 0
    assert count(loaded_db, "quota_series") == 2


def test_cpf_and_cedentes_never_reach_the_database(loaded_db):
    load(loaded_db)
    values = []

    with loaded_db.connection() as connection:
        for (table,) in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"):
            for record in connection.execute('SELECT * FROM "' + table + '"'):
                values.extend(str(v) for v in tuple(record) if isinstance(v, str))

    cpf_like = re.compile(r"[0-9]{11}|[0-9]{3}[.][0-9]{3}[.][0-9]{3}-[0-9]{2}")

    assert not any(FAKE_CPF in v or fake_cnpj(555) in v for v in values)
    assert not any(cpf_like.fullmatch(v.strip()) for v in values)
    assert count(loaded_db, "observations", "field_name LIKE '%CPF_CNPJ_CEDENTE%' OR field_name LIKE '%PR_CEDENTE%'") == 0
    assert count(loaded_db, "observations", "value_numeric = '60.5'") == 0


def test_cpf_like_text_undoes_the_load(loaded_db):
    tables = subject_rows()
    tables["tab_I"] = [row("tab_I", CLASSE="12345678901")]
    before = snapshot(loaded_db)

    with pytest.raises(LoadError, match="Texto com formato de CPF"):
        load(loaded_db, read(build_informe_zip(tables)))

    assert snapshot(loaded_db) == before


def test_failure_rolls_back_everything(loaded_db, monkeypatch):
    calls = []
    original = ObservationRepository.record

    def failing(self, **arguments):
        calls.append(1)

        if len(calls) == 50:
            raise RuntimeError("falha simulada")

        return original(self, **arguments)

    before = snapshot(loaded_db)
    monkeypatch.setattr(ObservationRepository, "record", failing)

    with pytest.raises(RuntimeError, match="falha simulada"):
        load(loaded_db)

    assert snapshot(loaded_db) == before


def test_progress_is_reported_per_table(loaded_db):
    seen = []
    load(loaded_db, progress=lambda table, observations, seconds: seen.append((table, observations)))

    assert [table for table, _ in seen] == list(columns.TABLES)
    assert dict(seen)["tab_VIII"] == 0
    assert dict(seen)["tab_X_4"] == 0
    assert dict(seen)["tab_IV"] == 2


def test_match_counts_does_not_write_and_matches_the_load(loaded_db):
    informe = read()
    before = snapshot(loaded_db)

    with loaded_db.connection() as connection:
        connection.execute("PRAGMA query_only = ON")
        counts = match_counts(informe, SubjectResolver(connection))

    assert snapshot(loaded_db) == before
    result = load(loaded_db, informe)
    candidates = sum(n for key, n in counts.items() if key[0] == "candidatas")
    created = sum(n for key, n in result.counts.items() if key[0] == "observacoes" and key[3] == "criadas")

    assert candidates == created
    assert counts[("series_candidatas",)] == 2
    assert counts[("papeis_candidatos",)] == 1
