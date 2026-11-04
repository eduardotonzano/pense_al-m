from decimal import Decimal

import pytest

from apoio import FAKE_CPF_MASKED
from apoio import make_test_cnpj
from apoio_cda import CONFIDENTIAL_HOLDER
from apoio_cda import COMPETENCE
from apoio_cda import FUND_ONLY
from apoio_cda import HOLDER
from apoio_cda import INVESTEES
from apoio_cda import OTHER_HOLDER
from apoio_cda import UNKNOWN_HOLDER
from apoio_cda import ZIP_NAME
from apoio_cda import build_cda_zip
from apoio_cda import confid_row
from apoio_cda import fic_fidc_rows
from apoio_cda import fie_row
from apoio_cda import investee_name
from apoio_cda import load_fictitious_cadastro
from conftest import MIGRATION_001
from conftest import MIGRATIONS_DIR
from conftest import create_schema
from fundos.cadastro.loader import LoadError
from fundos.cda import columns
from fundos.cda import loader as cda_loader
from fundos.cda.loader import CHANGED
from fundos.cda.loader import CLASS_NOT_FOUND
from fundos.cda.loader import CLASS_ONLY_FUND
from fundos.cda.loader import EQUAL
from fundos.cda.loader import MIXED
from fundos.cda.loader import NEW
from fundos.cda.loader import OUTSIDE
from fundos.cda.loader import PARSER_VERSION
from fundos.cda.loader import UNKNOWN_TYPE
from fundos.cda.loader import SubjectResolver
from fundos.cda.loader import compare_counts
from fundos.cda.loader import investee_type_counts
from fundos.cda.loader import load_cda
from fundos.cda.loader import scan_positions
from fundos.cda.reader import CONFIDENTIAL
from fundos.cda.reader import IDENTIFIED
from fundos.cda.reader import read_cda_bytes
from fundos.cda.report import format_load_report
from fundos.cda.report import format_match_report
from fundos.personal_data import PersonalDataError
from fundos.repositories.holding_repository import HoldingRepository


LATER_DATE = (2026, 10, 30, 8, 0, 0)
LAST_MODIFIED = "2026-10-29T03:58:52Z"
LATER_LAST_MODIFIED = "2026-10-30T08:00:00Z"

TABLES = (
    "holdings", "confidential_holdings", "holding_conflicts", "confidential_holding_conflicts",
    "raw_records", "collection_runs", "funds", "fund_classes", "observations", "party_observations",
)


@pytest.fixture
def loaded_db(full_db):
    load_fictitious_cadastro(full_db)
    return full_db


def read(data=None):
    return read_cda_bytes(build_cda_zip() if data is None else data, ZIP_NAME)


def read_rows(fie_rows=None, confid_rows=None, date_time=None):
    options = {} if date_time is None else {"date_time": date_time}
    return read(build_cda_zip(fie_rows, confid_rows, **options))


def load(db, cda=None, last_modified=None):
    with db.transaction() as connection:
        return load_cda(connection, read() if cda is None else cda, last_modified=last_modified)


def rows(db, sql, parameters=()):
    with db.connection() as connection:
        return [tuple(r) for r in connection.execute(sql, parameters)]


def count(db, table, where="1 = 1", parameters=()):
    return rows(db, "SELECT COUNT(*) FROM " + table + " WHERE " + where, parameters)[0][0]


def snapshot(db):
    return {table: count(db, table) for table in TABLES}


def wrong_dv(cnpj):
    return cnpj[:13] + str((int(cnpj[13]) + 1) % 10)


def class_id(db, cnpj):
    return rows(db, "SELECT id FROM fund_classes WHERE cnpj = ?", (cnpj,))[0][0]


def fund_id(db, cnpj):
    return rows(db, "SELECT id FROM funds WHERE cnpj = ?", (cnpj,))[0][0]


def test_refuses_without_the_cadastro(full_db):
    with pytest.raises(LoadError, match="cadastro nao foi carregado"):
        load(full_db)

    assert count(full_db, "raw_records") == 0


def test_refuses_without_migration_004(tmp_path):
    migrations = [MIGRATION_001] + [
        MIGRATIONS_DIR / name for name in ("002_party_observations.sql", "003_party_observation_shares.sql")
    ]
    db = create_schema(tmp_path / "fundos.db", migrations)

    with pytest.raises(LoadError, match="Faltam as migrations 004_holdings"):
        load(db)


def test_basic_load(loaded_db):
    before = snapshot(loaded_db)
    result = load(loaded_db, last_modified=LAST_MODIFIED)
    holder = class_id(loaded_db, HOLDER)
    holdings = rows(
        loaded_db,
        "SELECT fund_id, fund_class_id, investee_field_name, investee_cnpj, name_field_name, investee_name,"
        " quantity_field_name, quantity, value_field_name, market_value, reference_date"
        " FROM holdings ORDER BY id",
    )

    assert result.status == "success"
    assert holdings == [
        (
            None, holder, "cda_fie.CPF_CNPJ_EMISSOR", investee, "cda_fie.EMISSOR", investee_name(n),
            "cda_fie.QT_POS_FINAL", "10.5", "cda_fie.VL_MERC_POS_FINAL", str(100 * n) + ".5", COMPETENCE,
        )
        for n, investee in enumerate(INVESTEES, start=1)
    ]
    assert rows(
        loaded_db,
        "SELECT fund_class_id, value_field_name, market_value, confidential_until_field_name,"
        " confidential_until, reference_date FROM confidential_holdings",
    ) == [
        (
            class_id(loaded_db, CONFIDENTIAL_HOLDER), "cda_fie_CONFID.VL_MERC_POS_FINAL", "4321.25",
            "cda_fie_CONFID.DT_CONFID_APLIC", "2026-12-31", COMPETENCE,
        )
    ]
    # Nenhum fundo nem classe criado; nada em observations nem em papeis.
    for table in ("funds", "fund_classes", "observations", "party_observations"):
        assert count(loaded_db, table) == before[table]

    assert result.counts[("gravadas", IDENTIFIED, "criadas")] == 3
    assert result.counts[("gravadas", CONFIDENTIAL, "criadas")] == 1
    assert result.counts[("varredura", "cnpj_invalido")] == 0
    assert result.counts[("varredura", "formato_cpf")] == 0
    assert rows(loaded_db, "SELECT status, requested_items, successful_items FROM collection_runs ORDER BY id DESC LIMIT 1") == [
        ("success", 4, 4)
    ]


def test_manifest_has_the_zip_and_the_12_members(loaded_db):
    load(loaded_db, last_modified=LAST_MODIFIED)
    zip_row = rows(
        loaded_db,
        "SELECT id, last_modified, processing_status, parser_version FROM raw_records WHERE file_name = ?",
        (ZIP_NAME,),
    )[0]
    members = rows(
        loaded_db,
        "SELECT file_name, line_count, processing_status FROM raw_records WHERE parent_raw_record_id = ?",
        (zip_row[0],),
    )
    by_name = {name: (lines, status) for name, lines, status in members}

    assert zip_row[1:] == ("2026-10-29T03:58:52.000000+00:00", "processed", PARSER_VERSION)
    assert len(members) == 12
    assert by_name["cda_fie_202609.csv"] == (3, "processed")
    assert by_name["cda_fie_CONFID_202609.csv"] == (1, "processed")
    assert {by_name[columns.member_name(t, "202609")] for t in columns.IGNORED_TABLES} == {(None, "ignored")}
    assert rows(
        loaded_db,
        "SELECT COUNT(*) FROM holdings h JOIN raw_records r ON r.id = h.raw_record_id WHERE r.file_name = ?",
        ("cda_fie_202609.csv",),
    ) == [(3,)]


def test_investee_outside_the_cadastro_is_recorded_without_foreign_key(loaded_db):
    load(loaded_db)

    assert count(loaded_db, "funds", "cnpj = ?", (INVESTEES[2],)) == 0
    assert count(loaded_db, "holdings", "investee_cnpj = ?", (INVESTEES[2],)) == 1
    assert rows(loaded_db, "PRAGMA foreign_key_check") == []


def test_holder_outside_fund_classes_is_only_counted(loaded_db):
    before = snapshot(loaded_db)
    fie = fic_fidc_rows() + [
        fie_row(TP_FUNDO_CLASSE="CLASSES FIIM", investee=INVESTEES[0], CNPJ_FUNDO_CLASSE=OTHER_HOLDER),
        fie_row(UNKNOWN_HOLDER),
        fie_row(FUND_ONLY),
    ]
    confid = [confid_row(), confid_row(OTHER_HOLDER, TP_FUNDO_CLASSE="CLASSES FIIM")]
    result = load(loaded_db, read_rows(fie, confid))

    assert result.counts[("casamento", IDENTIFIED, UNKNOWN_TYPE)] == 1
    assert result.counts[("casamento", IDENTIFIED, CLASS_NOT_FOUND)] == 1
    assert result.counts[("casamento", IDENTIFIED, CLASS_ONLY_FUND)] == 1
    assert result.counts[("casamento", IDENTIFIED, "classe")] == 3
    assert result.counts[("casamento", CONFIDENTIAL, UNKNOWN_TYPE)] == 1
    assert result.counts[("detentores", IDENTIFIED, "classe")] == 1
    assert count(loaded_db, "holdings") == 3
    assert count(loaded_db, "confidential_holdings") == 1
    assert count(loaded_db, "fund_classes") == before["fund_classes"]
    assert count(loaded_db, "funds") == before["funds"]
    assert "posicoes_com_detentor_fora_do_cadastro" in rows(
        loaded_db, "SELECT error_summary FROM collection_runs ORDER BY id DESC LIMIT 1"
    )[0][0]


@pytest.mark.parametrize(
    "holder, holder_type",
    [(FUND_ONLY, "FIDC"), (HOLDER, "FIDC"), (make_test_cnpj(5), "FIAGRO")],
)
def test_holder_of_fund_type_is_loaded_by_fund_id(loaded_db, holder, holder_type):
    fie = [fie_row(holder, TP_FUNDO_CLASSE=holder_type)]
    confid = [confid_row(holder, TP_FUNDO_CLASSE=holder_type)]
    result = load(loaded_db, read_rows(fie, confid))

    assert result.counts[("casamento", IDENTIFIED, "fundo")] == 1
    assert rows(loaded_db, "SELECT fund_id, fund_class_id FROM holdings") == [(fund_id(loaded_db, holder), None)]
    assert rows(loaded_db, "SELECT fund_id, fund_class_id FROM confidential_holdings") == [
        (fund_id(loaded_db, holder), None)
    ]


def test_fiagro_class_holder_is_loaded(loaded_db):
    holder = make_test_cnpj(5)
    load(loaded_db, read_rows([fie_row(holder, TP_FUNDO_CLASSE="CLASSES - FIAGRO")], []))

    assert rows(loaded_db, "SELECT fund_class_id FROM holdings") == [(class_id(loaded_db, holder),)]


def test_same_zip_is_not_loaded_again(loaded_db):
    load(loaded_db)
    before = snapshot(loaded_db)

    with pytest.raises(LoadError, match="nada a carregar"):
        load(loaded_db)

    assert snapshot(loaded_db) == before


def test_rerun_with_the_same_values_records_nothing_new(loaded_db):
    load(loaded_db, last_modified=LAST_MODIFIED)
    holdings = rows(loaded_db, "SELECT * FROM holdings ORDER BY id")
    same_content = read_rows(date_time=LATER_DATE)
    result = load(loaded_db, same_content, last_modified=LATER_LAST_MODIFIED)

    assert result.counts[("gravadas", IDENTIFIED, "existentes")] == 3
    assert result.counts[("gravadas", IDENTIFIED, "criadas")] == 0
    assert result.counts[("gravadas", CONFIDENTIAL, "existentes")] == 1
    assert rows(loaded_db, "SELECT * FROM holdings ORDER BY id") == holdings
    assert count(loaded_db, "holding_conflicts") == 0


def test_reapresentation_with_another_value_adds_a_row_and_a_conflict(loaded_db):
    load(loaded_db, last_modified=LAST_MODIFIED)
    fie = fic_fidc_rows()
    fie[0] = dict(fie[0], VL_MERC_POS_FINAL="999.5")
    del fie[2]
    confid = [confid_row(DT_CONFID_APLIC="2027-01-31")]
    result = load(loaded_db, read_rows(fie, confid, LATER_DATE), last_modified=LATER_LAST_MODIFIED)

    assert result.counts[("gravadas", IDENTIFIED, "criadas")] == 1
    assert result.counts[("gravadas", IDENTIFIED, "existentes")] == 1
    assert result.counts[("conflitos", IDENTIFIED)] == 1
    assert result.counts[("conflitos", CONFIDENTIAL)] == 1
    assert result.counts[("reapresentacao", IDENTIFIED, "sumiram")] == 1
    assert result.counts[("reapresentacao", "zips")] == 1
    assert count(loaded_db, "holdings") == 4
    assert rows(
        loaded_db, "SELECT market_value FROM holdings WHERE investee_cnpj = ? ORDER BY id", (INVESTEES[0],)
    ) == [("100.5",), ("999.5",)]
    assert rows(loaded_db, "SELECT status FROM holding_conflicts") == [("open",)]
    assert count(loaded_db, "confidential_holding_conflicts") == 1
    # A posicao que sumiu continua no banco.
    assert count(loaded_db, "holdings", "investee_cnpj = ?", (INVESTEES[2],)) == 1


@pytest.mark.parametrize(
    "last_modified, message",
    [
        (None, "informe --last-modified"),
        ("2026-10-29T03:58:52Z", "nao e posterior ao do ZIP mais novo"),
        ("2026-10-28T00:00:00Z", "nao e posterior ao do ZIP mais novo"),
    ],
)
def test_reapresentation_needs_a_later_last_modified(loaded_db, last_modified, message):
    load(loaded_db, last_modified=LAST_MODIFIED)
    before = snapshot(loaded_db)
    other = read_rows([fie_row(VL_MERC_POS_FINAL="1")], [], LATER_DATE)

    with pytest.raises(LoadError, match=message):
        load(loaded_db, other, last_modified=last_modified)

    assert snapshot(loaded_db) == before


def test_reapresentation_over_a_zip_without_last_modified_uses_the_load_start(loaded_db):
    load(loaded_db)
    other = read_rows([fie_row(VL_MERC_POS_FINAL="1")], [], LATER_DATE)

    # Um Last-Modified anterior ao inicio da primeira carga nao prova nada.
    with pytest.raises(LoadError, match="nao tem Last-Modified"):
        load(loaded_db, other, last_modified="2026-10-30T08:00:00Z")


def test_confidential_holder_with_two_lines_refuses_the_commit(loaded_db):
    before = snapshot(loaded_db)

    with pytest.raises(LoadError, match="chave repetida nas confidenciais: 1 detentor"):
        load(loaded_db, read_rows(fic_fidc_rows(), [confid_row(), confid_row(VL_MERC_POS_FINAL="1")]))

    assert snapshot(loaded_db) == before


def repeated_rows(sizes=(2, 3, 4), changes=None):
    """Para cada tamanho n, n linhas ficticias da mesma chave do detentor 1 (investidos 4, 5, 6).

    changes: {(indice do investido, ordem): {coluna: valor}}.
    """

    rows = []

    for index, size in enumerate(sizes):
        for order in range(1, size + 1):
            values = {"VL_MERC_POS_FINAL": str(10 * index + order) + ".5", "QT_POS_FINAL": str(order)}
            values.update((changes or {}).get((index, order), {}))
            rows.append(fie_row(investee=INVESTEES[index], **values))

    return rows


def orders(db):
    return rows(db, "SELECT investee_cnpj, line_order, market_value FROM holdings ORDER BY id")


def test_repeated_lines_in_the_same_file_are_positions_without_conflict(loaded_db):
    # Como no CDA real de 09/2026: chaves com 2, 3 e 4 linhas.
    result = load(loaded_db, read_rows(repeated_rows(), []))
    found = orders(loaded_db)

    assert result.counts[("gravadas", IDENTIFIED, "criadas")] == 9
    assert result.counts[("conflitos", IDENTIFIED)] == 0
    assert count(loaded_db, "holding_conflicts") == 0
    assert [(cnpj, order) for cnpj, order, _ in found] == (
        [(INVESTEES[0], k) for k in (1, 2)]
        + [(INVESTEES[1], k) for k in (1, 2, 3)]
        + [(INVESTEES[2], k) for k in (1, 2, 3, 4)]
    )


def test_reapresentation_with_the_same_order_and_another_value_opens_a_conflict(loaded_db):
    load(loaded_db, read_rows(repeated_rows(), []), last_modified=LAST_MODIFIED)
    changed = repeated_rows(changes={(1, 2): {"VL_MERC_POS_FINAL": "77.5"}})
    result = load(loaded_db, read_rows(changed, [], LATER_DATE), last_modified=LATER_LAST_MODIFIED)
    conflict = rows(
        loaded_db,
        "SELECT a.investee_cnpj, a.line_order, a.market_value, b.line_order, b.market_value"
        " FROM holding_conflicts c JOIN holdings a ON a.id = c.holding_a_id JOIN holdings b ON b.id = c.holding_b_id",
    )

    assert result.counts[("gravadas", IDENTIFIED, "criadas")] == 1
    assert result.counts[("gravadas", IDENTIFIED, "existentes")] == 8
    assert result.counts[("conflitos", IDENTIFIED)] == 1
    assert conflict == [(INVESTEES[1], 2, "12.5", 2, "77.5")]
    assert count(loaded_db, "holdings") == 10


def test_reapresentation_with_the_same_order_and_value_records_nothing(loaded_db):
    load(loaded_db, read_rows(repeated_rows(), []), last_modified=LAST_MODIFIED)
    before = orders(loaded_db)
    result = load(loaded_db, read_rows(repeated_rows(), [], LATER_DATE), last_modified=LATER_LAST_MODIFIED)

    assert result.counts[("gravadas", IDENTIFIED, "criadas")] == 0
    assert result.counts[("gravadas", IDENTIFIED, "existentes")] == 9
    assert result.counts[("reapresentacao", IDENTIFIED, "sumiram")] == 0
    assert orders(loaded_db) == before
    assert count(loaded_db, "holding_conflicts") == 0


def test_line_that_vanishes_from_a_repeated_key_is_counted(loaded_db):
    load(loaded_db, read_rows(repeated_rows(), []), last_modified=LAST_MODIFIED)
    result = load(loaded_db, read_rows(repeated_rows((2, 3, 3)), [], LATER_DATE), last_modified=LATER_LAST_MODIFIED)

    assert result.counts[("reapresentacao", IDENTIFIED, "sumiram")] == 1
    assert result.counts[("gravadas", IDENTIFIED, "criadas")] == 0
    assert count(loaded_db, "holdings") == 9


def test_sum_per_class_is_only_done_on_read(loaded_db):
    lines = repeated_rows()
    load(loaded_db, read_rows(lines, []))
    stored = rows(loaded_db, "SELECT market_value FROM holdings WHERE fund_class_id = ?", (class_id(loaded_db, HOLDER),))
    total = sum(Decimal(value) for (value,) in stored)

    # Uma linha por linha do arquivo, com o valor como veio; a soma so existe na leitura.
    assert sorted(value for (value,) in stored) == sorted(row["VL_MERC_POS_FINAL"] for row in lines)
    assert total == sum(Decimal(row["VL_MERC_POS_FINAL"]) for row in lines)
    assert str(total) not in {value for (value,) in stored}
    assert rows(
        loaded_db,
        "SELECT COUNT(*) FROM sqlite_master WHERE type IN ('table', 'view') AND (name LIKE '%total%' OR name LIKE '%sum%')",
    ) == [(0,)]


def test_name_with_cpf_format_is_refused_and_rolled_back(loaded_db):
    before = snapshot(loaded_db)

    with pytest.raises(PersonalDataError, match="formato de CPF"):
        load(loaded_db, read_rows([fie_row(EMISSOR=FAKE_CPF_MASKED)], []))

    assert snapshot(loaded_db) == before


def test_scan_counts_invalid_cnpj_and_cpf_format(loaded_db):
    load(loaded_db)

    with loaded_db.connection() as connection:
        run = connection.execute("SELECT id FROM collection_runs ORDER BY id DESC LIMIT 1").fetchone()[0]
        assert scan_positions(connection, run) == (0, 0)
        # Linha alterada direto no banco, numa transacao desfeita no fim, so
        # para provar a varredura.
        connection.execute("BEGIN")
        connection.execute("DROP TRIGGER trg_holdings_no_update")
        connection.execute(
            "UPDATE holdings SET investee_name = ?, investee_cnpj = ? WHERE id = 1",
            (FAKE_CPF_MASKED, wrong_dv(INVESTEES[0])),
        )
        found = scan_positions(connection, run)
        connection.execute("ROLLBACK")

    assert found == (1, 1)
    assert count(loaded_db, "holdings", "investee_name = ?", (FAKE_CPF_MASKED,)) == 0


def test_failed_scan_rolls_back_everything(loaded_db, monkeypatch):
    before = snapshot(loaded_db)
    monkeypatch.setattr(cda_loader, "scan_positions", lambda connection, run_id: (0, 1))

    with pytest.raises(LoadError, match="formato de CPF: 1"):
        load(loaded_db)

    assert snapshot(loaded_db) == before


def test_error_in_the_middle_rolls_back_everything(loaded_db, monkeypatch):
    before = snapshot(loaded_db)

    def fail(self, **values):
        raise RuntimeError("falha ficticia")

    monkeypatch.setattr(HoldingRepository, "record_confidential", fail)

    with pytest.raises(RuntimeError, match="falha ficticia"):
        load(loaded_db)

    assert snapshot(loaded_db) == before


def test_compare_counts_and_investee_types_only_read(loaded_db):
    fie = fic_fidc_rows() + [fie_row(OTHER_HOLDER, make_test_cnpj(9))]
    cda = read_rows(fie)

    with loaded_db.connection() as connection:
        connection.execute("PRAGMA query_only = ON")
        first = compare_counts(connection, cda, SubjectResolver(connection))
        types = investee_type_counts(connection, cda)

    assert first[("comparacao", IDENTIFIED, NEW)] == 4
    assert first[("comparacao", CONFIDENTIAL, NEW)] == 1
    assert types[("tipo_investido", "linhas", "FIDC")] == 1
    assert types[("tipo_investido", "linhas", "FIAGRO")] == 1
    assert types[("tipo_investido", "linhas", MIXED)] == 1
    assert types[("tipo_investido", "linhas", OUTSIDE)] == 1
    assert types[("tipo_investido", "investidos", OUTSIDE)] == 1

    load(loaded_db, cda, last_modified=LAST_MODIFIED)
    fie[0] = dict(fie[0], VL_MERC_POS_FINAL="1")
    del fie[1]
    other = read_rows(fie, None, LATER_DATE)

    with loaded_db.connection() as connection:
        second = compare_counts(connection, other, SubjectResolver(connection))

    assert second[("comparacao", IDENTIFIED, EQUAL)] == 2
    assert second[("comparacao", IDENTIFIED, CHANGED)] == 1
    assert second[("comparacao", IDENTIFIED, NEW)] == 0
    assert second[("reapresentacao", IDENTIFIED, "sumiram")] == 1
    assert second[("comparacao", CONFIDENTIAL, EQUAL)] == 1


def test_load_report_has_only_aggregates(loaded_db):
    result = load(loaded_db)
    text = "\n".join(format_match_report(result.counts) + format_load_report(result))

    assert "holdings: criadas 3, existentes 0, conflitos abertos 0" in text
    assert "posicoes identificadas: classe 3, fundo 0; fora 0" in text
    assert "12 CSV em raw_records (10 cda_fi_* como ignored)" in text

    for secret in (HOLDER, CONFIDENTIAL_HOLDER) + INVESTEES + (investee_name(1), "100.5", "4321.25"):
        assert secret not in text


def test_repository_refuses_invalid_investee_before_sql(loaded_db):
    load(loaded_db)

    with loaded_db.transaction() as connection:
        repository = HoldingRepository(connection)
        base = rows(loaded_db, "SELECT source_id, collection_run_id, raw_record_id FROM holdings LIMIT 1")[0]
        common = {
            "fund_class_id": class_id(loaded_db, HOLDER),
            "investee_field_name": columns.INVESTEE_FIELD,
            "value_field_name": columns.VALUE_FIELD,
            "market_value": "1",
            "source_id": base[0],
            "collection_run_id": base[1],
            "raw_record_id": base[2],
            "reference_date": COMPETENCE,
            "line_order": 1,
        }

        for investee in (FAKE_CPF_MASKED, wrong_dv(INVESTEES[0]), INVESTEES[0][1:]):
            with pytest.raises(PersonalDataError):
                repository.record(investee_cnpj=investee, **common)

        with pytest.raises(PersonalDataError):
            repository.record(investee_cnpj=INVESTEES[0], **dict(common, value_field_name="cda_fie.CPF_CNPJ_EMISSOR"))

        with pytest.raises(ValueError, match="juntos"):
            repository.record(investee_cnpj=INVESTEES[0], quantity="1", **common)

        for order in (0, -1, 1.0, True, "1"):
            with pytest.raises(ValueError, match="ordem da linha"):
                repository.record(investee_cnpj=INVESTEES[0], **dict(common, line_order=order))

        same = repository.record(investee_cnpj=INVESTEES[0], **common)
        again = repository.record(investee_cnpj=INVESTEES[0], **common)
        second_line = repository.record(investee_cnpj=INVESTEES[0], **dict(common, line_order=2))

        assert same.created and not again.created
        assert again.holding.id == same.holding.id
        # Mesmo valor em outra ordem: outra posicao, sem conflito entre elas.
        assert second_line.created and second_line.conflicts == ()
        assert second_line.holding.line_order == 2
