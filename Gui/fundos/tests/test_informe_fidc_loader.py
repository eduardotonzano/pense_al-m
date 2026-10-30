import re

import pytest

from apoio import FAKE_CPF
from apoio import FAKE_CPF_MASKED
from apoio_cadastro import fake_cnpj
from apoio_cadastro import fake_cnpj_with_leading_zero
from apoio_cadastro import masked
from apoio_informe_fidc import ADMIN_NAME
from apoio_informe_fidc import CEDENTE_CNPJ
from apoio_informe_fidc import CEDENTE_SHARE
from apoio_informe_fidc import COMPETENCE
from apoio_informe_fidc import LATER_MEMBER_DATE
from apoio_informe_fidc import SENIOR
from apoio_informe_fidc import SUBORDINATE
from apoio_informe_fidc import SUBORDINATE_X1
from apoio_informe_fidc import ZIP_NAME
from apoio_informe_fidc import ambiguous_cpf
from apoio_informe_fidc import build_informe_zip
from apoio_informe_fidc import cedente_cells
from apoio_informe_fidc import changed
from apoio_informe_fidc import cnpj_with_two_leading_zeros
from apoio_informe_fidc import later_zip
from apoio_informe_fidc import load_fictitious_cadastro
from apoio_informe_fidc import merge
from apoio_informe_fidc import row
from apoio_informe_fidc import subject_rows
from conftest import MIGRATION_001
from conftest import MIGRATIONS_DIR
from conftest import create_schema
from fundos.cadastro.loader import LoadError
from fundos.database import utc_now
from fundos.informe_fidc import columns
from fundos.informe_fidc.loader import ALREADY_LOADED
from fundos.informe_fidc.loader import OLDER_VERSION
from fundos.informe_fidc.loader import CLASS_NOT_FOUND
from fundos.informe_fidc.loader import CLASS_ONLY_FUND
from fundos.informe_fidc.loader import FUND_NOT_FOUND
from fundos.informe_fidc.loader import FUND_ONLY_CLASS
from fundos.informe_fidc.loader import SAME_COMPETENCE
from fundos.informe_fidc.loader import SubjectResolver
from fundos.informe_fidc.loader import find_loaded_informe
from fundos.informe_fidc.loader import load_informe
from fundos.informe_fidc.loader import match_counts
from fundos.informe_fidc.loader import reapresentation_counts
from fundos.informe_fidc.reader import read_informe_bytes
from fundos.informe_fidc.report import LOADED_TABLES
from fundos.repositories.observation_repository import ObservationRepository
from fundos.repositories.party_observation_repository import PartyObservationRepository
from fundos.repositories.quota_series_repository import QuotaSeriesRepository


INFORME_TABLES = (
    "observations", "party_observations", "party_observation_shares", "quota_series",
    "raw_records", "collection_runs", "data_conflicts", "party_conflicts",
)

# Last-Modified ficticios dos ZIPs da mesma competencia, em ordem, e as datas
# dos membros que mudam o SHA-256 de cada um.
LM1 = "2026-10-24T11:46:15Z"
LM2 = "2026-10-29T11:46:15Z"
LM3 = "2026-10-29T18:00:00Z"
LM4 = "Fri, 30 Oct 2026 09:00:00 GMT"
DATE3 = (2026, 10, 29, 15, 0, 0)
DATE4 = (2026, 10, 30, 6, 0, 0)
PL = "tab_IV.TAB_IV_A_VL_PL"


@pytest.fixture
def loaded_db(full_db):
    """Cadastro ficticio: classe 1 (fundo 1), fundo 2 sem classe, classe 3 do fundo 1."""

    load_fictitious_cadastro(full_db, classes=(1,), funds_without_class=(2,), extra_classes=((3, 1),))
    return full_db


def read(data=None, name=ZIP_NAME):
    return read_informe_bytes(build_informe_zip() if data is None else data, name)


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


def test_loads_observations_series_administrator_and_cedente(loaded_db):
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
        "SELECT p.role, p.field_name, p.party_cnpj, p.name_field_name, p.party_name,"
        " s.share_field_name, s.share_value"
        " FROM party_observations p LEFT JOIN party_observation_shares s ON s.party_observation_id = p.id"
        " WHERE p.fund_class_id = ? AND p.field_name LIKE 'tab_I.%' ORDER BY p.id",
        (class_id,),
    ) == [
        ("administrador", "tab_I.CNPJ_ADMIN", fake_cnpj(901), "tab_I.ADMIN", ADMIN_NAME, None, None),
        (
            "cedente", "tab_I.TAB_I2B12_CPF_CNPJ_CEDENTE_1", CEDENTE_CNPJ, None, None,
            "tab_I.TAB_I2B12_PR_CEDENTE_1", CEDENTE_SHARE,
        ),
    ]
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
    assert all(m[4] == "fundos.informe_fidc.v2" for m in manifest)
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


def test_same_zip_and_other_zip_without_last_modified_are_refused(loaded_db):
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
        load(loaded_db, informe, last_modified=LM2)

    with pytest.raises(LoadError, match="informe --last-modified"):
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
    assert count(loaded_db, "party_observations", "role = 'cedente'") == 2
    assert count(loaded_db, "party_conflicts") == 0


def all_text_values(db):
    values = []

    with db.connection() as connection:
        for (table,) in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"):
            for record in connection.execute('SELECT * FROM "' + table + '"'):
                values.extend(str(v) for v in tuple(record) if isinstance(v, str))

    return values


def test_cpf_never_reaches_the_database_and_the_cedente_only_as_a_party(loaded_db):
    load(loaded_db)
    values = all_text_values(loaded_db)
    cpf_like = re.compile(r"[0-9]{11}|[0-9]{3}[.][0-9]{3}[.][0-9]{3}-[0-9]{2}")

    assert not any(FAKE_CPF in v for v in values)
    assert not any(cpf_like.fullmatch(v.strip()) for v in values)
    assert count(loaded_db, "observations", "field_name LIKE '%CPF_CNPJ_CEDENTE%' OR field_name LIKE '%PR_CEDENTE%'") == 0
    # O percentual do CPF (60.5) vai embora junto com ele.
    assert count(loaded_db, "observations", "value_numeric = '60.5'") == 0
    assert count(loaded_db, "party_observation_shares", "share_value = '60.5'") == 0
    assert count(loaded_db, "party_observations", "party_cnpj = ?", (CEDENTE_CNPJ,)) == 1


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
    assert counts[("papeis_candidatos", "administrador")] == 1
    assert counts[("papeis_candidatos", "cedente")] == 1
    assert counts[("percentuais_candidatos",)] == 1
    assert result.counts[("papeis", "cedente", "criados")] == 1
    assert result.counts[("percentuais", "criados")] == 1


def wrong_dv(cnpj):
    return cnpj[:12] + ("00" if cnpj[12:] != "00" else "11")


def cedente_field(prefix, position):
    identifier, share = columns.cedente_columns(prefix, position)
    return "tab_I." + identifier, "tab_I." + share


def test_cedentes_are_recorded_by_the_rules(loaded_db):
    repeated = fake_cnpj(701)
    entries = [
        ("TAB_I2A12", 1, repeated, "37.125"),
        ("TAB_I2A12", 2, repeated, "-3.5"),
        ("TAB_I2A12", 3, fake_cnpj_with_leading_zero(8)[1:], "1.5e1"),
        ("TAB_I2A12", 4, cnpj_with_two_leading_zeros()[2:], "17521903.58"),
        ("TAB_I2A12", 5, FAKE_CPF, "5.5"),
        ("TAB_I2A12", 6, FAKE_CPF_MASKED, "4.5"),
        ("TAB_I2A12", 7, ambiguous_cpf(), "3.25"),
        ("TAB_I2A12", 8, wrong_dv(fake_cnpj(702)), "2.25"),
        ("TAB_I2A12", 9, "", "1.25"),
        ("TAB_I2B12", 1, repeated, "6.75"),
        ("TAB_I2B12", 2, fake_cnpj(703), ""),
    ]
    tables = subject_rows()
    tables["tab_I"] = [row("tab_I", **cedente_cells(*entries))]
    informe = read(build_informe_zip(tables))
    result = load(loaded_db, informe)
    class_id = subject_id(loaded_db, "fund_classes", 1)
    member = rows(
        loaded_db,
        "SELECT id FROM raw_records WHERE file_name = ?",
        (columns.member_name("tab_I", "202609"),),
    )[0][0]

    with loaded_db.connection() as connection:
        cedentes = PartyObservationRepository(connection).list_by_subject(
            fund_class_id=class_id, role="cedente"
        )

    def expected(prefix, position, cnpj, share):
        identifier, share_field = cedente_field(prefix, position)
        return (identifier, cnpj, None if share is None else share_field, share)

    assert sorted((p.field_name, p.party_cnpj, p.share_field_name, p.share_value) for p in cedentes) == sorted([
        expected("TAB_I2A12", 1, repeated, "37.125"),
        expected("TAB_I2A12", 2, repeated, "-3.5"),
        expected("TAB_I2A12", 3, fake_cnpj_with_leading_zero(8), "15"),
        expected("TAB_I2A12", 4, cnpj_with_two_leading_zeros(), "17521903.58"),
        expected("TAB_I2B12", 1, repeated, "6.75"),
        expected("TAB_I2B12", 2, fake_cnpj(703), None),
    ])
    assert all((p.name_field_name, p.party_name) == (None, None) for p in cedentes)
    assert {(p.collection_run_id, p.raw_record_id, p.reference_date) for p in cedentes} == {
        (result.run_id, member, COMPETENCE)
    }
    assert result.status == "success"
    assert result.counts[("papeis", "cedente", "criados")] == 6
    assert result.counts[("percentuais", "criados")] == 5
    assert result.counts[("varredura_cpf", "party_observations")] == 0
    assert count(loaded_db, "party_conflicts") == 0
    assert count(loaded_db, "observations", "field_name LIKE '%CPF_CNPJ_CEDENTE%' OR field_name LIKE '%PR_CEDENTE%'") == 0
    assert not any(
        FAKE_CPF in v or ambiguous_cpf() in v or wrong_dv(fake_cnpj(702)) in v
        for v in all_text_values(loaded_db)
    )


def test_competence_loaded_by_an_older_reader_version_is_refused(loaded_db):
    informe = read()
    load(loaded_db, informe)

    with loaded_db.connection() as connection:
        connection.execute(
            "UPDATE raw_records SET parser_version = 'fundos.informe_fidc.v1'"
            " WHERE parser_version = 'fundos.informe_fidc.v2'"
        )

    before = snapshot(loaded_db)
    other_tables = subject_rows()
    other_tables["tab_IV"] = [row("tab_IV", TAB_IV_A_VL_PL="1200.00")]
    other = read(build_informe_zip(other_tables))
    message = (
        "O informe da competencia 2026-09 foi carregado por versao anterior do leitor"
        " (fundos.informe_fidc.v1). Esta versao nao atualiza esse carregamento: use um"
        " banco novo e carregue de novo."
    )

    with loaded_db.connection() as connection:
        assert find_loaded_informe(connection, informe) == OLDER_VERSION
        assert find_loaded_informe(connection, other) == OLDER_VERSION

    for candidate in (informe, other):
        with pytest.raises(LoadError) as error:
            load(loaded_db, candidate)

        assert str(error.value) == message

    assert snapshot(loaded_db) == before


def test_cpf_like_share_undoes_the_load(loaded_db):
    tables = subject_rows()
    tables["tab_I"] = [row("tab_I", **cedente_cells(("TAB_I2A12", 1, fake_cnpj(711), FAKE_CPF)))]
    before = snapshot(loaded_db)

    with pytest.raises(LoadError, match="Texto com formato de CPF") as error:
        load(loaded_db, read(build_informe_zip(tables)))

    assert "0 em observations, 1 em party_observations" in str(error.value)
    assert FAKE_CPF not in str(error.value)
    assert snapshot(loaded_db) == before


def test_refuses_without_migration_003(tmp_path):
    db = create_schema(tmp_path / "fundos.db", (MIGRATION_001, MIGRATIONS_DIR / "002_party_observations.sql"))
    load_fictitious_cadastro(db)

    with pytest.raises(LoadError, match="Faltam as migrations 003_party_observation_shares"):
        load(db)

    assert count(db, "raw_records", "file_name LIKE 'inf_mensal%'") == 0


# Reapresentacao (FU4.2): outro ZIP da mesma competencia.


def later(tables=None, date_time=LATER_MEMBER_DATE):
    return read(later_zip(tables, date_time))


def current(db, field_name=PL, n=1):
    """Valor atual (view) do campo na classe n."""

    with db.connection() as connection:
        record = ObservationRepository(connection).get_current(
            fund_class_id=subject_id(db, "fund_classes", n), field_name=field_name
        )

    return record.value_numeric


def compared(counts, kind, status, tables=LOADED_TABLES):
    return sum(counts[("reapresentacao", kind, table, status)] for table in tables)


def latest_cedente_share(db):
    return rows(
        db,
        "SELECT s.share_value FROM party_observations p"
        " JOIN party_observation_shares s ON s.party_observation_id = p.id"
        " WHERE p.role = 'cedente' ORDER BY p.collected_at DESC, p.id DESC LIMIT 1",
    )[0][0]


def test_second_zip_with_the_same_values_records_only_the_collection(loaded_db):
    load(loaded_db, last_modified=LM1)
    before = snapshot(loaded_db)
    informe = later()
    result = load(loaded_db, informe, last_modified=LM2)
    after = snapshot(loaded_db)

    assert result.status == "success"
    assert {table: after[table] - before[table] for table in after} == {
        "observations": 0, "party_observations": 0, "party_observation_shares": 0, "quota_series": 0,
        "raw_records": 19, "collection_runs": 1, "data_conflicts": 0, "party_conflicts": 0,
        "funds": 0, "fund_classes": 0,
    }
    assert compared(result.counts, "celulas", "iguais") == expected_values(informe)
    assert sum(n for key, n in result.counts.items() if key[0] == "observacoes" and key[3] == "existentes") == expected_values(informe)
    assert result.counts[("papeis", "cedente", "existentes")] == 1
    assert rows(
        loaded_db,
        "SELECT last_modified FROM raw_records WHERE parent_raw_record_id IS NULL AND file_name = ? ORDER BY id",
        (ZIP_NAME,),
    ) == [("2026-10-24T11:46:15.000000+00:00",), ("2026-10-29T11:46:15.000000+00:00",)]


def test_changed_value_opens_a_conflict_and_becomes_current(loaded_db):
    load(loaded_db, last_modified=LM1)
    result = load(loaded_db, later(changed(tab_IV={"TAB_IV_A_VL_PL": "1200.00"})), last_modified=LM2)

    assert current(loaded_db) == "1200"
    assert rows(loaded_db, "SELECT value_numeric FROM observations WHERE field_name = ? ORDER BY id", (PL,)) == [
        ("1000.5",), ("1200",)
    ]
    assert count(loaded_db, "data_conflicts", "status = 'open'") == 1
    assert result.counts[("conflitos", "data_conflicts")] == 1
    assert result.counts[("reapresentacao", "celulas", "tab_IV", "alteradas")] == 1


def test_emptied_cell_is_only_counted_and_the_old_value_stays_current(loaded_db):
    load(loaded_db, last_modified=LM1)
    before = count(loaded_db, "observations")
    result = load(loaded_db, later(changed(tab_IV={"TAB_IV_A_VL_PL": ""})), last_modified=LM2)

    assert count(loaded_db, "observations") == before
    assert current(loaded_db) == "1000.5"
    assert result.counts[("reapresentacao", "sumiram", "tab_IV", "vazias")] == 1


def test_new_subject_and_its_series_are_loaded(loaded_db):
    load(loaded_db, last_modified=LM1)
    result = load(loaded_db, later(merge(subject_rows(1), subject_rows(3))), last_modified=LM2)

    assert count(loaded_db, "observations", "fund_class_id = ?", (subject_id(loaded_db, "fund_classes", 3),)) > 0
    assert count(loaded_db, "quota_series") == 4
    assert result.counts[("reapresentacao", "assuntos", "novos")] == 1
    assert result.counts[("reapresentacao", "series", "novas")] == 2
    assert result.counts[("series", "criadas")] == 2


def test_subject_that_vanishes_is_counted_and_nothing_is_deleted(loaded_db):
    load(loaded_db, read(build_informe_zip(merge(subject_rows(1), subject_rows(3)))), last_modified=LM1)
    before = snapshot(loaded_db)
    result = load(loaded_db, later(), last_modified=LM2)
    after = snapshot(loaded_db)

    assert {table: after[table] - before[table] for table in ("observations", "party_observations", "quota_series")} == {
        "observations": 0, "party_observations": 0, "quota_series": 0,
    }
    assert result.counts[("reapresentacao", "assuntos", "sumiram")] == 1
    assert result.counts[("reapresentacao", "papeis", "cedente", "saiu")] == 1
    assert result.counts[("reapresentacao", "papeis", "administrador", "saiu")] == 1
    assert current(loaded_db, n=3) == "1000.5"


def test_cedente_share_change_opens_a_party_conflict(loaded_db):
    load(loaded_db, last_modified=LM1)
    result = load(loaded_db, later(changed(tab_I={"TAB_I2B12_PR_CEDENTE_1": "12.5"})), last_modified=LM2)

    assert count(loaded_db, "party_conflicts", "status = 'open'") == 1
    assert count(loaded_db, "party_observations", "role = 'cedente'") == 2
    assert count(loaded_db, "party_observation_shares") == 2
    assert latest_cedente_share(loaded_db) == "12.5"
    assert result.counts[("reapresentacao", "papeis", "cedente", "percentual_alterado")] == 1


def test_cedente_that_enters_and_one_that_leaves_add_rows_without_conflict(loaded_db):
    load(loaded_db, last_modified=LM1)
    tables = changed(tab_I=cedente_cells(("TAB_I2A12", 2, fake_cnpj(557), "7.25")))
    result = load(loaded_db, later(tables), last_modified=LM2)

    # Limitacao conhecida: as linhas da competencia se somam.
    assert count(loaded_db, "party_observations", "role = 'cedente'") == 2
    assert count(loaded_db, "party_conflicts") == 0
    assert result.counts[("reapresentacao", "papeis", "cedente", "entrou")] == 1
    assert result.counts[("reapresentacao", "papeis", "cedente", "saiu")] == 1


def test_administrator_name_and_cnpj_changes(loaded_db):
    renamed = "Administradora Ficticia Renomeada SA"
    load(loaded_db, last_modified=LM1)
    second = load(loaded_db, later(changed(tab_I={"ADMIN": renamed})), last_modified=LM2)
    third = load(
        loaded_db,
        later(changed(tab_I={"ADMIN": renamed, "CNPJ_ADMIN": masked(fake_cnpj(902))}), DATE3),
        last_modified=LM3,
    )

    assert second.counts[("reapresentacao", "papeis", "administrador", "nome_alterado")] == 1
    assert third.counts[("reapresentacao", "papeis", "administrador", "cnpj_trocado")] == 1
    assert count(loaded_db, "party_observations", "field_name = 'tab_I.CNPJ_ADMIN'") == 3
    assert count(loaded_db, "party_conflicts") == 1


def test_subclass_id_that_appears_fills_the_key_of_the_existing_series(loaded_db):
    load(loaded_db, read(build_informe_zip(subject_rows(subclass_ids=("", "")))), last_modified=LM1)
    result = load(loaded_db, later(subject_rows(subclass_ids=("SUBFICTICIA0001", ""))), last_modified=LM2)

    assert count(loaded_db, "quota_series") == 2
    assert rows(loaded_db, "SELECT cvm_subclass_id FROM quota_series WHERE cvm_subclass_id IS NOT NULL") == [
        ("SUBFICTICIA0001",)
    ]
    assert result.counts[("reapresentacao", "id_subclasse", "aparece")] == 1
    assert result.counts[("reapresentacao", "series", "novas")] == 0
    assert result.status == "success"


def test_subclass_id_that_disappears_keeps_the_key(loaded_db):
    load(loaded_db, last_modified=LM1)
    result = load(loaded_db, later(subject_rows(subclass_ids=("", ""))), last_modified=LM2)

    assert count(loaded_db, "quota_series") == 2
    assert count(loaded_db, "quota_series", "cvm_subclass_id = 'SUBFICTICIA0001'") == 1
    assert result.counts[("reapresentacao", "id_subclasse", "some")] == 1


def test_label_change_with_the_same_subclass_id_is_a_possible_swap(loaded_db):
    load(loaded_db, last_modified=LM1)
    tables = subject_rows()

    for table in columns.SERIES_TABLES:
        tables[table] = [
            dict(r, TAB_X_CLASSE_SERIE="Subclasse Senior Serie Unica") if r["TAB_X_CLASSE_SERIE"] == SENIOR else r
            for r in tables[table]
        ]

    result = load(loaded_db, later(tables), last_modified=LM2)

    assert result.status == "partial"
    assert result.counts[("id_subclasse", "recusado")] == 1
    assert count(loaded_db, "quota_series") == 3
    assert result.counts[("reapresentacao", "series", "novas")] == 1
    assert result.counts[("reapresentacao", "series", "sumiram")] == 1
    assert result.counts[("reapresentacao", "series", "possivel_troca_de_rotulo")] == 1


def test_value_that_returns_is_restated_and_the_conflict_opens_once(loaded_db):
    load(loaded_db, last_modified=LM1)
    load(loaded_db, later(changed(tab_IV={"TAB_IV_A_VL_PL": "1200.00"})), last_modified=LM2)
    third = load(loaded_db, later(None, DATE3), last_modified=LM3)

    assert current(loaded_db) == "1000.5"
    assert third.counts[("reapresentacao", "celulas", "tab_IV", "voltam")] == 1
    assert count(loaded_db, "observations", "field_name = ?", (PL,)) == 3
    assert count(loaded_db, "data_conflicts") == 1

    fourth = load(loaded_db, later(changed(tab_IV={"TAB_IV_A_VL_PL": "1200.00"}), DATE4), last_modified=LM4)

    assert current(loaded_db) == "1200"
    assert fourth.counts[("reapresentacao", "celulas", "tab_IV", "voltam")] == 1
    assert count(loaded_db, "observations", "field_name = ?", (PL,)) == 4
    assert count(loaded_db, "data_conflicts") == 1


def test_cedente_share_that_returns_is_restated(loaded_db):
    load(loaded_db, last_modified=LM1)
    load(loaded_db, later(changed(tab_I={"TAB_I2B12_PR_CEDENTE_1": "12.5"})), last_modified=LM2)
    third = load(loaded_db, later(None, DATE3), last_modified=LM3)

    assert third.counts[("reapresentacao", "papeis", "cedente", "voltam")] == 1
    assert latest_cedente_share(loaded_db) == "10"
    assert count(loaded_db, "party_observations", "role = 'cedente'") == 3
    assert count(loaded_db, "party_conflicts") == 1


def test_older_zip_after_a_newer_one_is_refused(loaded_db):
    load(loaded_db, last_modified=LM2)
    before = snapshot(loaded_db)

    for last_modified in (LM1, LM2):
        with pytest.raises(LoadError, match="nao e posterior ao do ZIP mais novo") as error:
            load(loaded_db, later(changed(tab_IV={"TAB_IV_A_VL_PL": "1200.00"})), last_modified=last_modified)

        assert "(2026-10-29T11:46:15.000000+00:00)" in str(error.value)

    assert snapshot(loaded_db) == before


def test_zip_loaded_without_last_modified_is_compared_by_the_start_of_its_load(loaded_db):
    load(loaded_db)
    before = snapshot(loaded_db)

    with pytest.raises(LoadError, match="nao da para provar que este ZIP e mais novo"):
        load(loaded_db, later(), last_modified=LM2)

    assert snapshot(loaded_db) == before
    assert load(loaded_db, later(), last_modified=utc_now()).status == "success"


@pytest.mark.parametrize(
    "value, message",
    [
        ("2026-10-29T11:46:15", "precisa ter fuso"),
        ("Thu, 29 Oct 2026 11:46:15", "precisa ter fuso"),
        ("29/10/2026", "invalida"),
        ("2099-01-01T00:00:00Z", "posterior a agora"),
    ],
)
def test_invalid_last_modified_is_refused(loaded_db, value, message):
    before = snapshot(loaded_db)

    with pytest.raises(LoadError, match=message):
        load(loaded_db, last_modified=value)

    assert snapshot(loaded_db) == before


def test_older_reader_version_is_still_refused_with_last_modified(loaded_db):
    load(loaded_db, last_modified=LM1)

    with loaded_db.connection() as connection:
        connection.execute(
            "UPDATE raw_records SET parser_version = 'fundos.informe_fidc.v1'"
            " WHERE parser_version = 'fundos.informe_fidc.v2'"
        )

    with pytest.raises(LoadError, match="versao anterior do leitor"):
        load(loaded_db, later(), last_modified=LM2)


def test_cpf_like_text_in_a_changed_cell_undoes_the_second_load(loaded_db):
    load(loaded_db, last_modified=LM1)
    before = snapshot(loaded_db)

    with pytest.raises(LoadError, match="Texto com formato de CPF"):
        load(loaded_db, later(changed(tab_I={"CLASSE": "12345678901"})), last_modified=LM2)

    assert snapshot(loaded_db) == before


def test_failure_in_the_second_load_rolls_back_everything(loaded_db, monkeypatch):
    load(loaded_db, last_modified=LM1)
    before = snapshot(loaded_db)

    def failing(self, **arguments):
        raise RuntimeError("falha simulada")

    monkeypatch.setattr(ObservationRepository, "record", failing)

    with pytest.raises(RuntimeError, match="falha simulada"):
        load(loaded_db, later(changed(tab_IV={"TAB_IV_A_VL_PL": "1200.00"})), last_modified=LM2)

    assert snapshot(loaded_db) == before


def record_everything(db, informe):
    """Grava de novo todas as celulas e papeis do ZIP, sem pular nada; devolve as linhas criadas."""

    created = 0

    with db.transaction() as connection:
        run_id = connection.execute("SELECT MAX(id) FROM collection_runs").fetchone()[0]
        source_id = connection.execute("SELECT source_id FROM collection_runs WHERE id = ?", (run_id,)).fetchone()[0]
        raw_id = connection.execute("SELECT MAX(id) FROM raw_records").fetchone()[0]
        resolver = SubjectResolver(connection)
        observations = ObservationRepository(connection)
        parties = PartyObservationRepository(connection)
        series = QuotaSeriesRepository(connection)
        provenance = {
            "source_id": source_id,
            "collection_run_id": run_id,
            "raw_record_id": raw_id,
            "reference_date": informe.competence,
        }

        for table in LOADED_TABLES:
            for r in informe.rows(table):
                column, subject = resolver.resolve(r.subject_type, r.cnpj)

                if column is None:
                    continue

                if table in columns.SERIES_TABLES:
                    target = {"quota_series_id": series.get_or_create(**{column: subject}, label=r.series_label)[0].id}
                else:
                    target = {column: subject}

                for name, value in r.values.items():
                    created += observations.record(
                        **target,
                        **provenance,
                        field_name=columns.field_name(table, name),
                        value_type=columns.VALUE_TYPE[columns.KINDS[table][name]],
                        value=value,
                    ).created

                for party in r.parties:
                    created += parties.record(
                        **{column: subject},
                        **provenance,
                        role=party.role,
                        field_name=party.field_name,
                        party_cnpj=party.cnpj,
                        name_field_name=party.name_field_name,
                        party_name=party.name,
                        share_field_name=party.share_field_name,
                        share_value=party.share,
                    ).created

    return created


def test_recording_every_cell_after_the_load_creates_nothing(loaded_db):
    # Pular a celula igual da o mesmo banco que gravar tudo.
    load(loaded_db, last_modified=LM1)
    second = changed(tab_IV={"TAB_IV_A_VL_PL": "1200.00"}, tab_I={"TAB_I2B12_PR_CEDENTE_1": "12.5"})
    load(loaded_db, later(merge(second, subject_rows(3))), last_modified=LM2)
    third = later(merge(subject_rows(1), subject_rows(3)), DATE3)
    load(loaded_db, third, last_modified=LM3)
    before = snapshot(loaded_db)

    assert record_everything(loaded_db, third) == 0
    assert snapshot(loaded_db) == before


def reapresentation_keys(counts):
    return {key: n for key, n in counts.items() if key[0] == "reapresentacao" and n}


def test_dry_run_comparison_writes_nothing_and_matches_the_load(loaded_db):
    load(loaded_db, last_modified=LM1)
    informe = later(merge(changed(tab_IV={"TAB_IV_A_VL_PL": "1200.00"}, tab_X={"TAB_X_DEBITO_TRIBUT": ""}), subject_rows(3)))
    before = snapshot(loaded_db)

    with loaded_db.connection() as connection:
        connection.execute("PRAGMA query_only = ON")
        counts = reapresentation_counts(connection, informe, SubjectResolver(connection))

    assert snapshot(loaded_db) == before
    result = load(loaded_db, informe, last_modified=LM2)

    assert reapresentation_keys(counts) == reapresentation_keys(result.counts)


def scenario_second_zip(pl="1200.00", share="12.5"):
    """Classe 1 com mudancas, fundo 2 novo e classe 3 ausente (cenario do resumo da FU4.2)."""

    first = changed(
        subject_rows(1, subclass_ids=("SUBFICTICIA0042", "")),
        tab_IV={"TAB_IV_A_VL_PL": pl},
        tab_X={"TAB_X_DEBITO_TRIBUT": ""},
        tab_I={
            "ADMIN": "Administradora Ficticia Renomeada SA",
            **cedente_cells(("TAB_I2A12", 2, fake_cnpj(557), "7.25"), ("TAB_I2B12", 1, fake_cnpj(555), share)),
        },
    )
    return merge(first, subject_rows(2, subject_type="Fundo", subclass_ids=("", "")))


def totals(counts):
    cells = {status: compared(counts, "celulas", status) for status in ("iguais", "alteradas", "novas", "voltam")}
    cells.update({reason: compared(counts, "sumiram", reason) for reason in ("vazias", "sem_linha")})
    return {
        "celulas": cells,
        "assuntos": {k: counts[("reapresentacao", "assuntos", k)] for k in ("nos_dois", "novos", "sumiram")},
        "series": {k: counts[("reapresentacao", "series", k)] for k in ("novas", "sumiram", "possivel_troca_de_rotulo")},
        "id_subclasse": {k: counts[("reapresentacao", "id_subclasse", k)] for k in ("aparece", "some")},
        "papeis": {
            role: {k[3]: n for k, n in counts.items() if k[:3] == ("reapresentacao", "papeis", role) and n}
            for role in ("administrador", "cedente")
        },
    }


def test_synthetic_scenario_counts(loaded_db):
    # Os numeros do resumo da FU4.2, para conferencia independente.
    no_id = ("", "")
    load(loaded_db, read(build_informe_zip(merge(subject_rows(1, subclass_ids=no_id), subject_rows(3, subclass_ids=no_id)))), last_modified=LM1)
    before = snapshot(loaded_db)
    second = load(loaded_db, later(scenario_second_zip()), last_modified=LM2)
    middle = snapshot(loaded_db)
    third = load(loaded_db, later(scenario_second_zip("1000.50", "10"), DATE3), last_modified=LM3)
    after = snapshot(loaded_db)

    assert totals(second.counts) == {
        "celulas": {"iguais": 349, "alteradas": 1, "novas": 352, "voltam": 0, "vazias": 1, "sem_linha": 351},
        "assuntos": {"nos_dois": 1, "novos": 1, "sumiram": 1},
        "series": {"novas": 2, "sumiram": 2, "possivel_troca_de_rotulo": 0},
        "id_subclasse": {"aparece": 1, "some": 0},
        "papeis": {
            "administrador": {"nome_alterado": 1, "entrou": 1, "saiu": 1},
            "cedente": {"percentual_alterado": 1, "entrou": 2, "saiu": 1},
        },
    }
    assert {t: middle[t] - before[t] for t in ("observations", "data_conflicts", "party_observations", "party_conflicts", "quota_series")} == {
        "observations": 353, "data_conflicts": 1, "party_observations": 5, "party_conflicts": 2, "quota_series": 2,
    }
    assert totals(third.counts) == {
        "celulas": {"iguais": 701, "alteradas": 0, "novas": 0, "voltam": 1, "vazias": 1, "sem_linha": 351},
        "assuntos": {"nos_dois": 2, "novos": 0, "sumiram": 1},
        "series": {"novas": 0, "sumiram": 2, "possivel_troca_de_rotulo": 0},
        "id_subclasse": {"aparece": 0, "some": 0},
        "papeis": {
            "administrador": {"iguais": 2, "saiu": 1},
            "cedente": {"iguais": 2, "voltam": 1, "saiu": 1},
        },
    }
    assert {t: after[t] - middle[t] for t in ("observations", "data_conflicts", "party_observations", "party_conflicts", "quota_series")} == {
        "observations": 1, "data_conflicts": 0, "party_observations": 1, "party_conflicts": 0, "quota_series": 0,
    }
    assert (second.counts[("reapresentacao", "assuntos", "celulas_dos_que_sumiram")], second.status, third.status) == (
        351, "success", "success"
    )


def test_database_grows_only_by_changed_new_and_returning_cells(loaded_db):
    load(loaded_db, last_modified=LM1)
    before = count(loaded_db, "observations")
    tables = merge(changed(tab_IV={"TAB_IV_A_VL_PL": "1200.00"}, tab_X={"TAB_X_DEBITO_TRIBUT": "5"}), subject_rows(3))
    result = load(loaded_db, later(tables), last_modified=LM2)
    grown = count(loaded_db, "observations") - before

    assert grown == sum(compared(result.counts, "celulas", status) for status in ("alteradas", "novas", "voltam"))
    assert compared(result.counts, "celulas", "alteradas") == 2
    assert compared(result.counts, "celulas", "novas") == expected_values(read(build_informe_zip(subject_rows(3))))
