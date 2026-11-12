import hashlib
import io
import zipfile

import pytest

from apoio import FAKE_CPF
from apoio import FAKE_CPF_MASKED
from apoio_cadastro import csv_bytes
from apoio_cadastro import fake_cnpj
from apoio_cadastro import fake_cnpj_with_leading_zero
from apoio_cadastro import masked
from apoio_cadastro import write_zip
from apoio_informe_fidc import ADMIN_NAME
from apoio_informe_fidc import CEDENTE_CNPJ
from apoio_informe_fidc import CEDENTE_SHARE
from apoio_informe_fidc import COMPETENCE
from apoio_informe_fidc import OPERATIONS
from apoio_informe_fidc import SENIOR
from apoio_informe_fidc import SUBORDINATE
from apoio_informe_fidc import SUBORDINATE_X1
from apoio_informe_fidc import ZIP_NAME
from apoio_informe_fidc import ambiguous_cpf
from apoio_informe_fidc import build_informe_zip
from apoio_informe_fidc import cedente_cells
from apoio_informe_fidc import cnpj_with_two_leading_zeros
from apoio_informe_fidc import merge
from apoio_informe_fidc import row
from apoio_informe_fidc import subject_name
from apoio_informe_fidc import subject_rows
from fundos.cnpj import is_valid_cnpj
from fundos.informe_fidc import columns
from fundos.informe_fidc.reader import InformeFormatError
from fundos.informe_fidc.reader import convert_numeric
from fundos.informe_fidc.reader import read_informe_bytes
from fundos.informe_fidc.reader import read_informe_zip
from fundos.informe_fidc.report import format_read_report


# Campos por tabela no dado de 09/2026 (docs/fundos-descoberta.md, secao 10.2).
FIELDS_PER_TABLE = {
    "tab_I": 109, "tab_II": 37, "tab_III": 13, "tab_IV": 6, "tab_V": 37,
    "tab_VI": 37, "tab_VII": 29, "tab_VIII": 6, "tab_IX": 76, "tab_X": 23,
    "tab_X_1": 7, "tab_X_1_1": 36, "tab_X_2": 7, "tab_X_3": 6, "tab_X_4": 8,
    "tab_X_5": 11, "tab_X_6": 7, "tab_X_7": 6,
}


def read(data=None, **options):
    return read_informe_bytes(
        build_informe_zip() if data is None else data,
        ZIP_NAME,
        **options,
    )


def with_table(table, rows):
    tables = subject_rows()
    tables[table] = rows
    return build_informe_zip(tables)


def first(informe, table):
    return next(informe.rows(table))


def test_column_list_has_18_tables_and_461_fields():
    assert {table: len(header) for table, header in columns.HEADERS.items()} == FIELDS_PER_TABLE
    assert sum(FIELDS_PER_TABLE.values()) == 461
    assert columns.TABLES[0] == "tab_I"
    assert columns.TABLES.index("tab_X_1") < columns.TABLES.index("tab_X_2")
    assert columns.NOT_LOADED == ("tab_VIII", "tab_X_4")

    for header in columns.HEADERS.values():
        assert header[:4] == ("TP_FUNDO_CLASSE", "CNPJ_FUNDO_CLASSE", "DENOM_SOCIAL", "DT_COMPTC")


def test_series_tables_follow_the_data_not_the_dictionary():
    # O dicionario traz CNPJ_FUNDO; o dado traz TP_FUNDO_CLASSE e
    # CNPJ_FUNDO_CLASSE, e a X_1 tem ID_SUBCLASSE (secao 10.2).
    for table in ("tab_X_1", "tab_X_2", "tab_X_3", "tab_X_4", "tab_X_6"):
        assert "CNPJ_FUNDO" not in columns.HEADERS[table]
        assert "TAB_X_CLASSE_SERIE" in columns.HEADERS[table]

    assert "ID_SUBCLASSE" in columns.HEADERS["tab_X_1"]


def test_cedente_columns_are_18_identifiers_and_18_shares():
    identifiers = set()
    shares = set()

    for prefix in ("TAB_I2A12", "TAB_I2B12"):
        for position in range(1, 10):
            identifiers.add(prefix + "_CPF_CNPJ_CEDENTE_" + str(position))
            shares.add(prefix + "_PR_CEDENTE_" + str(position))
            assert columns.cedente_columns(prefix, position) == (
                prefix + "_CPF_CNPJ_CEDENTE_" + str(position),
                prefix + "_PR_CEDENTE_" + str(position),
            )

    def of_kind(kind):
        return {
            column
            for kinds in columns.KINDS.values()
            for column, found in kinds.items()
            if found == kind
        }

    assert (len(identifiers), len(shares)) == (18, 18)
    assert of_kind(columns.CEDENTE_ID) == identifiers
    assert of_kind(columns.CEDENTE_SHARE) == shares
    assert set(columns.CEDENTE_COLUMNS) == identifiers | shares
    assert all(column in columns.HEADERS["tab_I"] for column in identifiers | shares)
    assert not hasattr(columns, "EXCLUDED")
    assert "excluded" not in {kind for kinds in columns.KINDS.values() for kind in kinds.values()}


def test_reads_the_18_members_and_the_competence():
    data = build_informe_zip()
    informe = read(data)

    assert informe.zip.sha256 == hashlib.sha256(data).hexdigest()
    assert informe.zip.period == "202609"
    assert informe.zip.member_dates == ("2026-10-24",)
    assert informe.competence == COMPETENCE
    assert len(informe.members) == 18
    assert sum(m.column_count for m in informe.members) == 461
    assert informe.member("tab_VIII").line_count == 2
    assert informe.member("tab_X_4").line_count == 4

    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for member in informe.members:
            raw = archive.read(member.file_name)
            assert member.sha256 == hashlib.sha256(raw).hexdigest()
            assert member.size_bytes == len(raw)


def test_rows_are_normalized_and_keys_are_not_values():
    informe = read()
    tab_i = first(informe, "tab_I")
    tab_ii = first(informe, "tab_II")

    assert (tab_i.subject_type, tab_i.cnpj, tab_i.competence) == ("Classe", fake_cnpj(1), COMPETENCE)
    assert tab_i.values["CLASSE_UNICA"] is True
    assert tab_i.values["FUNDO_EXCLUSIVO"] is False
    assert tab_i.values["CONDOM"] == "FECHADO"
    assert tab_i.values["TAB_I_VL_ATIVO"] == "1200"
    assert tab_i.values["TAB_I2A1_VL_CRED_VENC_AD"] == "0"
    assert tab_i.values["CNPJ_CLASSE"] == fake_cnpj(1)
    assert tab_i.values["DENOM_SOCIAL"] == subject_name(1)
    assert "DENOM_SOCIAL" not in tab_ii.values
    assert tab_ii.name == subject_name(1)

    for key in ("TP_FUNDO_CLASSE", "CNPJ_FUNDO_CLASSE", "DT_COMPTC", "CNPJ_ADMIN", "ADMIN", "PRAZO_CONVERSAO_COTA"):
        assert key not in tab_i.values

    assert [
        (p.role, p.field_name, p.cnpj, p.name_field_name, p.name, p.share_field_name, p.share)
        for p in tab_i.parties
    ] == [
        ("administrador", "tab_I.CNPJ_ADMIN", fake_cnpj(901), "tab_I.ADMIN", ADMIN_NAME, None, None),
        (
            "cedente", "tab_I.TAB_I2B12_CPF_CNPJ_CEDENTE_1", CEDENTE_CNPJ, None, None,
            "tab_I.TAB_I2B12_PR_CEDENTE_1", CEDENTE_SHARE,
        ),
    ]
    assert first(informe, "tab_IV").values["TAB_IV_A_VL_PL"] == "1000.5"


def test_decodes_cp1252():
    informe = read()
    operations = [r.values["TAB_X_TP_OPER"] for r in informe.rows("tab_X_4")]

    assert operations[:2] == list(OPERATIONS)


def test_byte_undefined_in_cp1252_fails():
    content = csv_bytes(columns.HEADERS["tab_II"], [row("tab_II")]).replace(b"Exemplo", b"Exem\x81lo")

    with pytest.raises(InformeFormatError, match="nao decodifica como cp1252"):
        read(build_informe_zip(members={"tab_II": content}))


@pytest.mark.parametrize(
    "header, message",
    [
        (columns.HEADERS["tab_III"][:-1], "faltam TAB_III_B4_VL_SWAP_PAGAR"),
        (columns.HEADERS["tab_III"] + ("COLUNA_NOVA",), "1 coluna(s) desconhecida(s)"),
        (
            columns.HEADERS["tab_III"][:4] + columns.HEADERS["tab_III"][5:6] + columns.HEADERS["tab_III"][4:5] + columns.HEADERS["tab_III"][6:],
            "a posicao 5 deveria ser TAB_III_VL_PASSIVO",
        ),
    ],
)
def test_different_header_fails(header, message):
    content = csv_bytes(header, [dict(row("tab_III"), COLUNA_NOVA="0")])

    with pytest.raises(InformeFormatError) as error:
        read(build_informe_zip(members={"tab_III": content}))

    assert "inf_mensal_fidc_tab_III_202609.csv" in str(error.value)
    assert message in str(error.value)


def test_missing_or_extra_member_fails():
    with pytest.raises(InformeFormatError, match="faltam tab_X_7"):
        read(build_informe_zip(drop=("tab_X_7",)))

    with pytest.raises(InformeFormatError) as error:
        read(build_informe_zip(extra={"inf_mensal_fidc_tab_XI_202609.csv": b"a\r\n"}))

    assert "1 membro(s) inesperado(s)" in str(error.value)


def test_members_with_different_periods_fail():
    data = build_informe_zip(drop=("tab_X_7",), extra={
        "inf_mensal_fidc_tab_X_7_202608.csv": csv_bytes(columns.HEADERS["tab_X_7"], [row("tab_X_7")]),
    })

    with pytest.raises(InformeFormatError, match="AAAAMM diferente entre os membros"):
        read(data)


def test_zip_name_with_another_period_fails():
    with pytest.raises(InformeFormatError, match="nao bate com o AAAAMM"):
        read_informe_bytes(build_informe_zip(), "inf_mensal_fidc_202608.zip")


def test_row_with_wrong_width_fails_citing_the_line():
    content = csv_bytes(columns.HEADERS["tab_IV"], [row("tab_IV")]) + b"1;2;3\r\n"

    with pytest.raises(InformeFormatError) as error:
        read(build_informe_zip(members={"tab_IV": content}))

    assert "inf_mensal_fidc_tab_IV_202609.csv, linha 3: 3 campo(s)" in str(error.value)


def test_more_than_one_competence_is_refused():
    data = with_table("tab_X_5", [row("tab_X_5", DT_COMPTC="2026-09-29")])

    with pytest.raises(InformeFormatError, match="DT_COMPTC com 2 valores diferentes"):
        read(data)


def test_competence_of_another_month_is_refused():
    tables = {table: [dict(r, DT_COMPTC="2026-08-31") for r in rows] for table, rows in subject_rows().items()}

    with pytest.raises(InformeFormatError, match="nao e do mes do AAAAMM"):
        read(build_informe_zip(tables))


def test_future_competence_is_refused():
    tables = {table: [dict(r, DT_COMPTC="2999-01-31") for r in rows] for table, rows in subject_rows().items()}

    with pytest.raises(InformeFormatError, match="posterior a hoje"):
        read_informe_bytes(build_informe_zip(tables, period="299901"), "inf_mensal_fidc_299901.zip")


def test_competence_out_of_format_fails():
    data = with_table("tab_IV", [row("tab_IV", DT_COMPTC="30/09/2026")])

    with pytest.raises(InformeFormatError) as error:
        read(data)

    assert "linha 2, coluna DT_COMPTC: valor fora do formato date" in str(error.value)
    assert "30/09/2026" not in str(error.value)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("1.5e+10", "15000000000"),
        ("1.5E10", "15000000000"),
        ("-2.5e-3", "-0.0025"),
        ("1e5", "100000"),
        ("1234567.891e+2", "123456789.1"),
    ],
)
def test_scientific_notation_is_converted_exactly(text, expected):
    assert convert_numeric(text) == (expected, True)


@pytest.mark.parametrize("text", ["1,5", "1.5e", "e5", "1.5e+1000", "1.5e+31", "0x10", "1.5d+3"])
def test_other_numeric_formats_are_refused(text):
    with pytest.raises(ValueError):
        convert_numeric(text)


def test_scientific_notation_in_the_file_is_converted_and_counted():
    data = with_table("tab_IX", [row("tab_IX", TAB_IX_A1_1_2_COMPRA_MEDIA="1.5e+10", TAB_IX_B1_1_3_COMPRA_MAX="2E3")])
    informe = read(data)
    values = first(informe, "tab_IX").values

    assert values["TAB_IX_A1_1_2_COMPRA_MEDIA"] == "15000000000"
    assert values["TAB_IX_B1_1_3_COMPRA_MAX"] == "2000"
    assert informe.counts[("notacao_cientifica", "tab_IX.TAB_IX_A1_1_2_COMPRA_MEDIA")] == 1
    text = "\n".join(format_read_report(informe))
    assert "tab_IX.TAB_IX_A1_1_2_COMPRA_MEDIA: 1" in text
    assert "  total: 2" in text


@pytest.mark.parametrize(
    "table, column, value, kind",
    [
        ("tab_IV", "TAB_IV_A_VL_PL", "1.000,50", "numeric"),
        ("tab_I", "FUNDO_EXCLUSIVO", "talvez", "boolean"),
        ("tab_IX", "TAB_IX_A1_1_1_COMPRA_MIN", "1.5e+1000", "numeric"),
    ],
)
def test_value_out_of_format_aborts_without_repeating_it(table, column, value, kind):
    data = with_table(table, [row(table, **{column: value})])

    with pytest.raises(InformeFormatError) as error:
        read(data)

    message = str(error.value)
    assert "linha 2, coluna " + column + ": valor fora do formato " + kind in message
    assert value not in message


def test_default_cedentes_keep_only_the_cnpj_with_its_share():
    informe = read()
    tab_i = first(informe, "tab_I")
    everything = repr(informe) + repr([r for table in columns.TABLES for r in informe.rows(table)])
    report = "\n".join(format_read_report(informe))
    cedentes = [p for p in tab_i.parties if p.role == "cedente"]

    assert [(p.cnpj, p.share) for p in cedentes] == [(CEDENTE_CNPJ, CEDENTE_SHARE)]
    assert informe.counts[("cedentes_preenchidas",)] == 4
    assert informe.counts[("cedente_identificador", "TAB_I2A12", "cpf")] == 1
    assert informe.counts[("cedente_percentual", "TAB_I2A12", "sem_identificador")] == 1
    assert FAKE_CPF not in everything
    assert CEDENTE_CNPJ not in everything
    assert "60.5" not in everything
    assert FAKE_CPF not in report
    assert CEDENTE_CNPJ not in report
    assert "celulas preenchidas: 4 (identificadores 2 + percentuais 2)" in report
    assert not any(column in tab_i.values for column in columns.CEDENTE_COLUMNS)


def cedente_row(*entries, n=1):
    return row("tab_I", n, **cedente_cells(*entries))


def cedentes_of(informe):
    return [
        (p.field_name, p.cnpj, p.share_field_name, p.share)
        for r in informe.rows("tab_I")
        for p in r.parties
        if p.role == "cedente"
    ]


def expected_cedente(prefix, position, cnpj, share):
    """(campo do identificador, CNPJ, campo do percentual, percentual) esperados."""

    identifier, share_column = columns.cedente_columns(prefix, position)
    return (
        "tab_I." + identifier,
        cnpj,
        None if share is None else "tab_I." + share_column,
        share,
    )


def wrong_dv(cnpj):
    return cnpj[:12] + ("00" if cnpj[12:] != "00" else "11")


def test_cedente_identifier_rules():
    invalid = wrong_dv(fake_cnpj(602))
    entries = [
        ("TAB_I2A12", 1, fake_cnpj(601), "37.125"),
        ("TAB_I2A12", 2, fake_cnpj_with_leading_zero(7)[1:], "12.5"),
        ("TAB_I2A12", 3, cnpj_with_two_leading_zeros()[2:], "8.25"),
        ("TAB_I2A12", 4, FAKE_CPF, "5.5"),
        ("TAB_I2A12", 5, ambiguous_cpf(), "4.75"),
        ("TAB_I2A12", 6, FAKE_CPF_MASKED, "3.5"),
        ("TAB_I2A12", 7, invalid, "2.5"),
        ("TAB_I2A12", 8, "", "1.5"),
        ("TAB_I2B12", 1, fake_cnpj(603), ""),
    ]
    informe = read(with_table("tab_I", [cedente_row(*entries)]))
    counts = informe.counts
    everything = repr(informe) + repr(list(informe.rows("tab_I")))
    report = "\n".join(format_read_report(informe))

    # O ambiguo fecha como CNPJ com zeros, mas 11 digitos sao tratados como CPF.
    assert is_valid_cnpj(ambiguous_cpf().zfill(14))
    assert cedentes_of(informe) == [
        expected_cedente("TAB_I2A12", 1, fake_cnpj(601), "37.125"),
        expected_cedente("TAB_I2A12", 2, fake_cnpj_with_leading_zero(7), "12.5"),
        expected_cedente("TAB_I2A12", 3, cnpj_with_two_leading_zeros(), "8.25"),
        expected_cedente("TAB_I2B12", 1, fake_cnpj(603), None),
    ]
    assert [counts[("cedente_identificador", "TAB_I2A12", s)] for s in ("cnpj", "cpf", "invalido")] == [3, 3, 1]
    assert counts[("cedente_zeros_restaurados", "TAB_I2A12")] == 2
    assert counts[("cedente_percentual", "TAB_I2A12", "com_identificador")] == 3
    assert counts[("cedente_percentual", "TAB_I2A12", "sem_identificador")] == 5
    assert counts[("cedente_sem_percentual", "TAB_I2B12")] == 1
    assert counts[("cedentes_preenchidas",)] == 16

    for value in (fake_cnpj(601), fake_cnpj(603), FAKE_CPF, FAKE_CPF_MASKED, ambiguous_cpf(), invalid, "37.125", "4.75"):
        assert value not in everything
        assert value not in report


def test_same_cnpj_in_two_positions_and_in_both_groups_is_kept_and_counted():
    repeated = fake_cnpj(611)
    entries = [
        ("TAB_I2A12", 1, repeated, "10.5"),
        ("TAB_I2A12", 2, repeated, "9.5"),
        ("TAB_I2B12", 1, repeated, "1.25"),
        ("TAB_I2B12", 2, fake_cnpj(612), "2.25"),
    ]
    informe = read(with_table("tab_I", [cedente_row(*entries)]))

    assert [entry[1] for entry in cedentes_of(informe)] == [repeated, repeated, repeated, fake_cnpj(612)]
    assert informe.counts[("cedente_repetido_no_grupo", "TAB_I2A12")] == 1
    assert informe.counts[("cedente_repetido_no_grupo", "TAB_I2B12")] == 0
    assert informe.counts[("cedente_nos_dois_grupos",)] == 1
    assert informe.counts[("cedente_assuntos_com_gravavel",)] == 1


def test_share_in_scientific_notation_negative_and_above_100():
    entries = [
        ("TAB_I2A12", 1, fake_cnpj(621), "1.5e1"),
        ("TAB_I2A12", 2, fake_cnpj(622), "-3.5"),
        ("TAB_I2A12", 3, fake_cnpj(623), "17521903.58"),
        ("TAB_I2B12", 1, fake_cnpj(624), "100"),
    ]
    informe = read(with_table("tab_I", [cedente_row(*entries)]))
    report = format_read_report(informe)

    assert [entry[3] for entry in cedentes_of(informe)] == ["15", "-3.5", "17521903.58", "100"]
    assert informe.counts[("notacao_cientifica", "tab_I.TAB_I2A12_PR_CEDENTE_1")] == 1
    assert informe.counts[("cedente_percentual_negativo", "TAB_I2A12")] == 1
    assert informe.counts[("cedente_percentual_acima_de_100", "TAB_I2A12")] == 1
    assert informe.counts[("cedente_percentual_acima_de_100", "TAB_I2B12")] == 0
    assert any(
        line.startswith("    percentual com identificador 3,") and "negativo 1, acima de 100 1;" in line
        for line in report
    )
    assert "17521903.58" not in "\n".join(report)


@pytest.mark.parametrize("identifier", [fake_cnpj(631), FAKE_CPF, ""])
def test_share_out_of_format_aborts_without_the_value(identifier):
    data = with_table("tab_I", [cedente_row(("TAB_I2A12", 1, identifier, "12,5"))])

    with pytest.raises(InformeFormatError) as error:
        read(data)

    message = str(error.value)
    assert "linha 2, coluna TAB_I2A12_PR_CEDENTE_1: valor fora do formato numeric" in message
    assert "12,5" not in message


def test_cedente_counts_close_with_the_filled_cells():
    rows = [
        row("tab_I", 1),
        cedente_row(
            ("TAB_I2A12", 1, fake_cnpj(641), "20"),
            ("TAB_I2A12", 2, FAKE_CPF, "10"),
            ("TAB_I2A12", 3, "", "5"),
            ("TAB_I2B12", 4, fake_cnpj(642), ""),
            ("TAB_I2B12", 5, wrong_dv(fake_cnpj(643)), "1"),
            n=2,
        ),
    ]
    tables = merge(subject_rows(1), subject_rows(2))
    tables["tab_I"] = rows
    counts = read(build_informe_zip(tables)).counts
    identifiers = sum(n for key, n in counts.items() if key[0] == "cedente_identificador")
    shares = sum(n for key, n in counts.items() if key[0] == "cedente_percentual")

    assert counts[("cedentes_preenchidas",)] == identifiers + shares == 6 + 6

    for prefix, _ in columns.CEDENTE_GROUPS:
        assert counts[("cedente_identificador", prefix, "cnpj")] == (
            counts[("cedente_percentual", prefix, "com_identificador")]
            + counts[("cedente_sem_percentual", prefix)]
        )


def test_reports_cedentes_by_group():
    report = format_read_report(read())

    assert "  com risco (TAB_I2A12): identificador CNPJ 0 (zeros restaurados 0), CPF descartado 1, invalido 0" in report
    assert "  sem risco (TAB_I2B12): identificador CNPJ 1 (zeros restaurados 0), CPF descartado 0, invalido 0" in report
    assert (
        "    percentual com identificador 0, sem identificador (so contado) 1; identificador sem percentual 0;"
        " percentual gravado negativo 0, acima de 100 0; mesmo CNPJ repetido no grupo 0"
    ) in report
    assert "  mesmo CNPJ nos dois grupos do mesmo assunto: 0; assuntos com cedente de CNPJ valido: 1" in report


def test_repr_shows_no_identifier_name_or_value():
    informe = read()
    everything = repr(informe) + repr([r for table in columns.TABLES for r in informe.rows(table)])

    for value in (
        fake_cnpj(1), masked(fake_cnpj(1)), subject_name(1), fake_cnpj(901), ADMIN_NAME,
        CEDENTE_CNPJ, FAKE_CPF, "Classe Ficticia Unica", SENIOR, "1000.5", "SUBFICTICIA0001",
    ):
        assert value not in everything

    assert "role='cedente'" in everything
    assert "field_name='tab_I.TAB_I2B12_CPF_CNPJ_CEDENTE_1'" in everything


def test_cnpj_classe_rules():
    cases = [
        row("tab_I", 1, CNPJ_CLASSE=fake_cnpj(1) + "    "),
        row("tab_I", 2, CNPJ_CLASSE=masked(fake_cnpj(2))),
        row("tab_I", 3, CNPJ_CLASSE=fake_cnpj(3)[:12] + ("00" if fake_cnpj(3)[12:] != "00" else "11")),
        row("tab_I", 4, CNPJ_CLASSE=FAKE_CPF),
        row("tab_I", 5, CNPJ_CLASSE=""),
    ]
    informe = read(with_table("tab_I", cases))
    stored = [r.values.get("CNPJ_CLASSE") for r in informe.rows("tab_I")]

    assert stored == [fake_cnpj(1), fake_cnpj(2), None, None, None]
    assert [informe.counts[("cnpj_classe", s)] for s in ("vazio", "cnpj", "cpf", "invalido")] == [1, 2, 1, 1]
    assert FAKE_CPF not in repr([r for r in informe.rows("tab_I")])


def test_cnpj_classe_with_13_digits_gets_the_leading_zero():
    cnpj = fake_cnpj_with_leading_zero(3)
    informe = read(with_table("tab_I", [row("tab_I", CNPJ_CLASSE=cnpj[1:])]))

    assert first(informe, "tab_I").values["CNPJ_CLASSE"] == cnpj


def test_administrator_without_a_valid_cnpj_loses_the_name():
    wrong = fake_cnpj(901)[:12] + ("00" if fake_cnpj(901)[12:] != "00" else "11")
    informe = read(with_table("tab_I", [row("tab_I", CNPJ_ADMIN=wrong)]))

    assert [p for p in first(informe, "tab_I").parties if p.role == "administrador"] == []
    assert informe.counts[("administradora", "invalido")] == 1
    assert informe.counts[("nome_descartado", "tab_I.ADMIN")] == 1
    assert ADMIN_NAME not in repr(list(informe.rows("tab_I")))


def test_denom_social_divergence_is_counted():
    tables = subject_rows()
    tables["tab_X_5"] = [row("tab_X_5", DENOM_SOCIAL="Outro Nome Ficticio")]
    informe = read(build_informe_zip(tables))

    assert informe.counts[("denom_divergente",)] == 1
    assert "DENOM_SOCIAL" not in first(informe, "tab_X_5").values


def test_series_labels_fall_on_the_same_key():
    informe = read()
    x1 = list(informe.rows("tab_X_1"))
    x2 = list(informe.rows("tab_X_2"))

    assert [r.series_key for r in x1] == [r.series_key for r in x2]
    assert x1[1].series_label == SUBORDINATE_X1
    assert x2[1].series_label == SUBORDINATE
    assert x1[1].values["TAB_X_CLASSE_SERIE"] == SUBORDINATE_X1
    assert x1[0].subclass_id == "SUBFICTICIA0001"
    assert x1[1].subclass_id is None
    assert informe.counts[("series", "tab_X_1")] == 2
    assert informe.counts[("id_subclasse", "repetidos")] == 0


def test_subclass_id_shared_between_subjects_is_flagged():
    tables = merge(
        subject_rows(1, subclass_ids=("SUBFICTICIA0009", "")),
        subject_rows(2, subclass_ids=("SUBFICTICIA0009", "")),
    )
    informe = read(build_informe_zip(tables))

    assert informe.shared_subclass_ids == frozenset({"SUBFICTICIA0009"})
    assert informe.counts[("id_subclasse", "repetidos")] == 1
    assert informe.counts[("id_subclasse", "linhas_repetidos")] == 2


def test_unknown_subject_type_and_invalid_cnpj_are_counted():
    tables = merge(subject_rows(1), subject_rows(2, subject_type="Outro"))
    tables["tab_X_7"].append(row("tab_X_7", 3, CNPJ_FUNDO_CLASSE="12.345.678/0001-00"))
    informe = read(build_informe_zip(tables))
    x7 = list(informe.rows("tab_X_7"))

    assert [r.subject_type for r in x7] == ["Classe", None, "Classe"]
    assert x7[2].cnpj is None
    assert informe.counts[("linhas_por_tipo", "tab_X_7", "outro")] == 1
    assert informe.counts[("cnpj_assunto_invalido", "tab_X_7")] == 1


def test_report_has_only_aggregates():
    tables = merge(subject_rows(1), subject_rows(2, subject_type="Fundo"))
    informe = read(build_informe_zip(tables))
    text = "\n".join(format_read_report(informe))

    assert "Linhas lidas (18 tabelas, 461 campos," in text
    assert "tab_I: 2 linha(s), 109 coluna(s); Classe 1, Fundo 1, outro 0" in text
    assert "tab_X_4: 8 linha(s), 8 coluna(s); Classe 4, Fundo 4, outro 0; lida, nao carregada" in text
    assert "Competencia (DT_COMPTC): 2026-09-30 (AAAAMM 202609)" in text

    for secret in (
        FAKE_CPF,
        fake_cnpj(1),
        fake_cnpj(2),
        masked(fake_cnpj(1)),
        fake_cnpj(901),
        ADMIN_NAME,
        subject_name(1),
        "Ficticia",
        "ficticio",
        SENIOR,
        "SUBFICTICIA",
    ):
        assert secret not in text


def test_progress_is_called_per_table_in_order():
    seen = []
    read(progress=lambda table, lines: seen.append((table, lines)))

    assert [table for table, _ in seen] == list(columns.TABLES)
    assert dict(seen)["tab_X_4"] == 4


def test_reads_from_disk_without_extracting_anything(tmp_path):
    path = write_zip(tmp_path, build_informe_zip(), name=ZIP_NAME)
    before = sorted(p.name for p in tmp_path.iterdir())

    informe = read_informe_zip(path)

    assert informe.zip.file_name == ZIP_NAME
    assert sorted(p.name for p in tmp_path.iterdir()) == before


def test_missing_zip_is_refused(tmp_path):
    with pytest.raises(FileNotFoundError, match="ZIP nao encontrado"):
        read_informe_zip(tmp_path / "inexistente.zip")
