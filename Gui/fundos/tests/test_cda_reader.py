import hashlib

import pytest

from apoio import FAKE_CPF
from apoio import FAKE_CPF_MASKED
from apoio import make_test_cnpj
from apoio_cadastro import csv_bytes
from apoio_cadastro import masked
from apoio_cda import COMPETENCE
from apoio_cda import CONFIDENTIAL_HOLDER
from apoio_cda import CONFIDENTIAL_UNTIL
from apoio_cda import HOLDER
from apoio_cda import HOLDER_NAME
from apoio_cda import INVESTEE_NAME
from apoio_cda import INVESTEES
from apoio_cda import OTHER_HOLDER
from apoio_cda import PERSON_NAME
from apoio_cda import ZIP_NAME
from apoio_cda import build_cda_zip
from apoio_cda import confid_row
from apoio_cda import fic_fidc_rows
from apoio_cda import fie_row
from apoio_cda import investee_name
from apoio_cda import other_row
from apoio_informe_fidc import ambiguous_cpf
from apoio_informe_fidc import cnpj_with_two_leading_zeros
from fundos.cda import columns
from fundos.cda.reader import CONFIDENTIAL
from fundos.cda.reader import IDENTIFIED
from fundos.cda.reader import REFUSED_DV
from fundos.cda.reader import REFUSED_EMPTY
from fundos.cda.reader import REFUSED_FORMAT
from fundos.cda.reader import REFUSED_PERSON_TYPE
from fundos.cda.reader import REFUSED_PF
from fundos.cda.reader import CdaFormatError
from fundos.cda.reader import check_investee
from fundos.cda.reader import read_cda_bytes
from fundos.cda.reader import read_cda_zip
from fundos.cda.report import format_read_report
from fundos.cnpj import is_valid_cnpj


# CPF ficticio completado com zeros ate 14 caracteres, nos dois casos da
# secao 12.6: o DV de CNPJ falha, ou fecha por acaso.
PADDED_CPF_DV_FAILS = "000" + FAKE_CPF
PADDED_CPF_DV_PASSES = "000" + ambiguous_cpf()


def read(data=None, **options):
    return read_cda_bytes(build_cda_zip() if data is None else data, ZIP_NAME, **options)


def read_rows(fie_rows=None, confid_rows=None):
    return read(build_cda_zip(fie_rows, confid_rows))


def refused(cda, reason):
    return cda.counts[(IDENTIFIED, "identificador_recusado", reason)]


def wrong_dv(cnpj):
    return cnpj[:13] + str((int(cnpj[13]) + 1) % 10)


def sensitive_texts():
    """Tudo o que nunca pode sair em repr, mensagem ou relatorio."""

    cnpjs = (HOLDER, OTHER_HOLDER, CONFIDENTIAL_HOLDER) + INVESTEES
    return (
        cnpjs
        + tuple(masked(cnpj) for cnpj in cnpjs)
        + (FAKE_CPF, FAKE_CPF_MASKED, PADDED_CPF_DV_FAILS, PADDED_CPF_DV_PASSES)
        + (HOLDER_NAME, INVESTEE_NAME, PERSON_NAME, "Investido 1")
        + ("1234.56", "100.5", "200.5", "300.5", "4321.25", "10.5")
    )


def assert_hidden(text):
    for value in sensitive_texts():
        assert value not in text


def test_column_lists_follow_section_12_2():
    assert len(columns.TABLES) == 12
    assert len(columns.HEADERS[columns.FIE]) == 31
    assert len(columns.HEADERS[columns.FIE_CONFID]) == 11
    assert columns.READ_TABLES == ("cda_fie", "cda_fie_CONFID")
    assert len(columns.IGNORED_TABLES) == 10
    assert columns.member_name("cda_fie_CONFID", "202609") == "cda_fie_CONFID_202609.csv"
    assert columns.zip_name("202609") == "cda_fi_202609.zip"
    assert columns.INVESTEE_FIELD == "cda_fie.CPF_CNPJ_EMISSOR"
    assert columns.CONFIDENTIAL_UNTIL_FIELD == "cda_fie_CONFID.DT_CONFID_APLIC"


def test_fic_fidc_with_three_positions():
    cda = read()
    holdings = list(cda.holdings())

    assert cda.competence == COMPETENCE
    assert cda.zip.period == "202609"
    assert [h.holder_cnpj for h in holdings] == [HOLDER] * 3
    assert [h.investee_cnpj for h in holdings] == list(INVESTEES)
    assert [h.investee_name for h in holdings] == [investee_name(n) for n in (1, 2, 3)]
    assert [h.market_value for h in holdings] == ["100.5", "200.5", "300.5"]
    assert {h.quantity for h in holdings} == {"10.5"}
    assert {h.holder_type for h in holdings} == {"CLASSES - FIDC"}
    assert [h.line for h in holdings] == [2, 3, 4]
    assert cda.counts[(IDENTIFIED, "linhas")] == 3
    assert cda.counts[(IDENTIFIED, "posicoes")] == 3
    assert cda.counts[(IDENTIFIED, "identificador_aceito")] == 3
    assert cda.counts[(IDENTIFIED, "detentores")] == 1
    assert cda.counts[(IDENTIFIED, "investidos")] == 3
    assert cda.counts[(IDENTIFIED, "tipo_detentor", "CLASSES - FIDC")] == 3
    assert cda.counts[(IDENTIFIED, "chave_repetida", "chaves")] == 0


def test_manifest_has_the_zip_and_the_12_members():
    data = build_cda_zip()
    cda = read(data)
    fie = cda.member("cda_fie")
    ignored = cda.member("cda_fi_BLC_2")

    assert cda.zip.sha256 == hashlib.sha256(data).hexdigest()
    assert cda.zip.size_bytes == len(data)
    assert cda.zip.member_dates == ("2026-10-29",)
    assert [m.file_name for m in cda.members] == [
        columns.member_name(table, "202609") for table in columns.TABLES
    ]
    assert (fie.line_count, fie.column_count) == (3, 31)
    assert (ignored.line_count, ignored.column_count) == (None, None)
    assert ignored.size_bytes > 0 and len(ignored.sha256) == 64
    assert set(cda.contents) == {"cda_fie", "cda_fie_CONFID"}


def test_confidential_row():
    cda = read()
    confidential = list(cda.confidential_holdings())

    assert len(confidential) == 1
    assert confidential[0].holder_cnpj == CONFIDENTIAL_HOLDER
    assert confidential[0].market_value == "4321.25"
    assert confidential[0].confidential_until == CONFIDENTIAL_UNTIL
    assert confidential[0].competence == COMPETENCE
    assert cda.counts[(CONFIDENTIAL, "linhas")] == 1
    assert cda.counts[(CONFIDENTIAL, "posicoes")] == 1
    assert cda.counts[(CONFIDENTIAL, "mes_confidencial", "2026-12")] == 1
    assert cda.counts[("detentores_nas_duas",)] == 0


def test_confidential_needs_quotas_date_and_value():
    cda = read_rows(
        confid_rows=[
            confid_row(),
            confid_row(OTHER_HOLDER, TP_APLIC="Disponibilidades"),
            confid_row(make_test_cnpj(7), DT_CONFID_APLIC=""),
            confid_row(make_test_cnpj(8), VL_MERC_POS_FINAL=""),
            confid_row(CNPJ_FUNDO_CLASSE=wrong_dv(make_test_cnpj(9))),
        ]
    )

    assert len(list(cda.confidential_holdings())) == 1
    assert cda.counts[(CONFIDENTIAL, "linhas")] == 4
    assert cda.counts[("tp_aplic", "cda_fie_CONFID", "Disponibilidades")] == 1
    assert cda.counts[(CONFIDENTIAL, "sem_data_confidencial")] == 1
    assert cda.counts[(CONFIDENTIAL, "sem_valor_de_mercado")] == 1
    assert cda.counts[(CONFIDENTIAL, "detentor_invalido")] == 1


def test_holder_with_both_kinds_is_counted():
    cda = read_rows(confid_rows=[confid_row(HOLDER), confid_row(HOLDER, VL_MERC_POS_FINAL="1")])

    assert cda.counts[("detentores_nas_duas",)] == 1
    assert cda.counts[(CONFIDENTIAL, "detentor_repetido")] == 1


def test_other_applications_are_only_counted():
    # Linha que nao e de cotas: valor fora do formato e data invalida nao
    # sao lidos nem conferidos.
    rows = fic_fidc_rows() + [
        other_row(),
        other_row(VL_MERC_POS_FINAL="1,5", DT_COMPTC="ontem", TP_APLIC="Ações"),
    ]
    cda = read_rows(rows)

    assert len(list(cda.holdings())) == 3
    assert cda.counts[("tp_aplic", "cda_fie", columns.FUND_QUOTAS)] == 3
    assert cda.counts[("tp_aplic", "cda_fie", "Outras aplicações")] == 1
    assert cda.counts[("tp_aplic", "cda_fie", "Ações")] == 1
    assert cda.member("cda_fie").line_count == 5


def test_cpf_in_pf_quota_line_is_never_kept():
    for identifier in (FAKE_CPF, FAKE_CPF_MASKED):
        cda = read_rows([fie_row(PF_PJ_EMISSOR="PF", CPF_CNPJ_EMISSOR=identifier, EMISSOR=PERSON_NAME)])

        assert list(cda.holdings()) == []
        assert refused(cda, REFUSED_PF) == 1
        assert cda.counts[(IDENTIFIED, "emissor_descartado")] == 1
        assert_hidden(repr(cda) + "\n".join(format_read_report(cda)))


def test_cpf_padded_with_zeros_in_pf_line_is_refused_in_both_dv_cases():
    # A fixture forca os dois casos: o DV de CNPJ falha e fecha por acaso.
    assert not is_valid_cnpj(PADDED_CPF_DV_FAILS)
    assert is_valid_cnpj(PADDED_CPF_DV_PASSES)
    assert len(PADDED_CPF_DV_PASSES) == len(PADDED_CPF_DV_FAILS) == 14

    rows = [
        fie_row(PF_PJ_EMISSOR="PF", CPF_CNPJ_EMISSOR=PADDED_CPF_DV_FAILS, EMISSOR=PERSON_NAME),
        fie_row(PF_PJ_EMISSOR="PF", CPF_CNPJ_EMISSOR=PADDED_CPF_DV_PASSES, EMISSOR=PERSON_NAME),
    ]
    cda = read_rows(rows)
    output = repr(cda) + repr(cda.counts) + "\n".join(format_read_report(cda))

    assert list(cda.holdings()) == []
    assert refused(cda, REFUSED_PF) == 2
    assert cda.counts[(IDENTIFIED, "emissor_descartado")] == 2
    assert cda.counts[(IDENTIFIED, "investidos")] == 0
    assert PADDED_CPF_DV_FAILS not in output
    assert PADDED_CPF_DV_PASSES not in output
    assert PERSON_NAME not in output


@pytest.mark.parametrize(
    "person_type, identifier, reason",
    [
        ("PF", INVESTEES[0], REFUSED_PF),
        ("PF", "", REFUSED_PF),
        ("PJ", "", REFUSED_EMPTY),
        ("PJ", "   ", REFUSED_EMPTY),
        ("", "", REFUSED_EMPTY),
        ("", INVESTEES[0], REFUSED_PERSON_TYPE),
        ("pj", INVESTEES[0], REFUSED_PERSON_TYPE),
        ("PJ", FAKE_CPF, REFUSED_FORMAT),
        ("PJ", FAKE_CPF_MASKED, REFUSED_FORMAT),
        ("PJ", cnpj_with_two_leading_zeros()[1:], REFUSED_FORMAT),
        ("PJ", cnpj_with_two_leading_zeros()[2:], REFUSED_FORMAT),
        ("PJ", INVESTEES[0] + "0", REFUSED_FORMAT),
        ("PJ", INVESTEES[0][:2] + "." + INVESTEES[0][2:], REFUSED_FORMAT),
        ("PJ", wrong_dv(INVESTEES[0]), REFUSED_DV),
        ("PJ", PADDED_CPF_DV_FAILS, REFUSED_DV),
        ("PJ", "0" * 14, REFUSED_DV),
    ],
)
def test_guard_a_refuses_by_reason(person_type, identifier, reason):
    assert check_investee(person_type, identifier) == (None, reason)

    cda = read_rows([fie_row(PF_PJ_EMISSOR=person_type, CPF_CNPJ_EMISSOR=identifier)])

    assert list(cda.holdings()) == []
    assert refused(cda, reason) == 1
    assert cda.counts[(IDENTIFIED, "identificador_aceito")] == 0


def test_twelve_or_thirteen_digits_are_not_padded():
    # classify_identifier completaria com zeros; a guarda do CDA nao.
    cnpj = cnpj_with_two_leading_zeros()
    cda = read_rows([fie_row(CPF_CNPJ_EMISSOR=cnpj[2:]), fie_row(CPF_CNPJ_EMISSOR=cnpj[1:])])

    assert list(cda.holdings()) == []
    assert refused(cda, REFUSED_FORMAT) == 2


@pytest.mark.parametrize(
    "identifier",
    [INVESTEES[0], masked(INVESTEES[0]), " " + INVESTEES[0] + " "],
)
def test_guard_a_accepts_14_characters_or_the_full_mask(identifier):
    assert check_investee("PJ", identifier) == (INVESTEES[0], None)


def test_alphanumeric_investee_is_accepted():
    investee = make_test_cnpj(5, alphanumeric=True)
    cda = read_rows([fie_row(CPF_CNPJ_EMISSOR=investee)])

    assert [h.investee_cnpj for h in cda.holdings()] == [investee]


def test_guard_b_drops_emissor_from_refused_lines():
    rows = [
        fie_row(PF_PJ_EMISSOR="PF", CPF_CNPJ_EMISSOR=FAKE_CPF, EMISSOR=PERSON_NAME),
        fie_row(CPF_CNPJ_EMISSOR=wrong_dv(INVESTEES[1]), EMISSOR=PERSON_NAME),
        fie_row(EMISSOR=""),
    ]
    cda = read_rows(rows)
    holdings = list(cda.holdings())

    assert len(holdings) == 1
    assert holdings[0].investee_name is None
    assert cda.counts[(IDENTIFIED, "emissor_descartado")] == 2
    assert cda.counts[(IDENTIFIED, "sem_emissor")] == 1


def test_holder_must_be_a_valid_cnpj_without_padding():
    rows = fic_fidc_rows() + [
        fie_row(CNPJ_FUNDO_CLASSE=wrong_dv(OTHER_HOLDER)),
        fie_row(CNPJ_FUNDO_CLASSE=cnpj_with_two_leading_zeros()[2:]),
        fie_row(CNPJ_FUNDO_CLASSE=OTHER_HOLDER),
    ]
    cda = read_rows(rows)

    assert [h.holder_cnpj for h in cda.holdings()] == [HOLDER] * 3 + [OTHER_HOLDER]
    assert cda.counts[(IDENTIFIED, "detentor_invalido")] == 2
    assert cda.counts[(IDENTIFIED, "detentores")] == 2


def test_position_without_market_value_is_counted_and_not_kept():
    cda = read_rows([fie_row(VL_MERC_POS_FINAL=""), fie_row(QT_POS_FINAL="")])
    holdings = list(cda.holdings())

    assert len(holdings) == 1
    assert holdings[0].quantity is None
    assert cda.counts[(IDENTIFIED, "sem_valor_de_mercado")] == 1
    assert cda.counts[(IDENTIFIED, "sem_quantidade")] == 1


def test_repeated_key_is_counted():
    rows = [
        fie_row(),
        fie_row(),
        fie_row(investee=INVESTEES[1]),
        fie_row(investee=INVESTEES[1], VL_MERC_POS_FINAL="1"),
        fie_row(investee=INVESTEES[1], QT_POS_FINAL="2"),
        fie_row(investee=INVESTEES[2]),
        fie_row(OTHER_HOLDER),
    ]
    cda = read_rows(rows)

    assert cda.counts[(IDENTIFIED, "posicoes")] == 7
    assert cda.counts[(IDENTIFIED, "chave_repetida", "linhas")] == 5
    assert cda.counts[(IDENTIFIED, "chave_repetida", "chaves")] == 2
    assert cda.counts[(IDENTIFIED, "chave_repetida", "valores_diferentes")] == 1


def test_values_are_exact_decimals():
    cda = read_rows([fie_row(QT_POS_FINAL="0001.500", VL_MERC_POS_FINAL="-12.30")])
    holding = next(cda.holdings())

    assert (holding.quantity, holding.market_value) == ("1.5", "-12.3")


@pytest.mark.parametrize(
    "table, column, value",
    [
        ("cda_fie", "VL_MERC_POS_FINAL", "1,5"),
        ("cda_fie", "QT_POS_FINAL", "1e3"),
        ("cda_fie", "DT_COMPTC", "30/09/2026"),
        ("cda_fie_CONFID", "VL_MERC_POS_FINAL", "abc"),
        ("cda_fie_CONFID", "DT_CONFID_APLIC", "2026-13-01"),
    ],
)
def test_invalid_value_in_a_quota_line_aborts_citing_the_column(table, column, value):
    if table == "cda_fie":
        data = build_cda_zip([fie_row(**{column: value})])
    else:
        data = build_cda_zip(None, [confid_row(**{column: value})])

    with pytest.raises(CdaFormatError) as error:
        read(data)

    assert table + "_202609.csv, linha 2, coluna " + column in str(error.value)
    assert value not in str(error.value)


def test_invalid_value_in_a_refused_line_still_aborts():
    with pytest.raises(CdaFormatError, match="coluna VL_MERC_POS_FINAL"):
        read_rows([fie_row(PF_PJ_EMISSOR="PF", CPF_CNPJ_EMISSOR=FAKE_CPF, VL_MERC_POS_FINAL="1,5")])


def test_wrong_header_is_refused():
    header = list(columns.HEADERS["cda_fie"])
    header[21], header[22] = header[22], header[21]
    data = build_cda_zip(members={"cda_fie": csv_bytes(header, [])})

    with pytest.raises(CdaFormatError, match="Cabecalho de cda_fie_202609.csv"):
        read(data)


@pytest.mark.parametrize(
    "options, message",
    [
        ({"drop": ("cda_fi_PL",)}, "faltam cda_fi_PL"),
        ({"drop": ("cda_fie_CONFID",)}, "faltam cda_fie_CONFID"),
        ({"extra": {"leia-me.txt": b"x"}}, "1 membro\\(s\\) inesperado"),
        ({"extra": {"cda_fi_BLC_9_202609.csv": b"x"}}, "1 membro\\(s\\) inesperado"),
        ({"extra": {"cda_fie_202608.csv": b"x"}}, "tabela repetida: cda_fie"),
    ],
)
def test_members_must_be_exactly_the_12(options, message):
    with pytest.raises(CdaFormatError, match=message):
        read(build_cda_zip(**options))


def test_members_with_different_periods_are_refused():
    data = build_cda_zip(drop=("cda_fi_PL",), extra={"cda_fi_PL_202608.csv": b"x"})

    with pytest.raises(CdaFormatError, match="AAAAMM diferente"):
        read(data)


def test_zip_name_must_match_the_members():
    with pytest.raises(CdaFormatError, match="nao bate com o AAAAMM"):
        read_cda_bytes(build_cda_zip(), "cda_fi_202608.zip")


def test_invalid_cp1252_in_a_read_member_is_refused():
    data = build_cda_zip(members={"cda_fie": csv_bytes(columns.HEADERS["cda_fie"], []) + b"\x81"})

    with pytest.raises(CdaFormatError, match="nao decodifica como cp1252"):
        read(data)


def test_ignored_members_are_not_decoded():
    # IGNORED_CONTENT tem um byte invalido em cp1252.
    assert read().member("cda_fi_BLC_8").line_count is None


def test_not_a_zip_is_refused():
    with pytest.raises(CdaFormatError, match="nao e um ZIP valido"):
        read(b"nao e zip")


@pytest.mark.parametrize(
    "fie_rows, confid_rows, message",
    [
        ([fie_row(DT_COMPTC="2026-08-31")], [], "nao e do mes do AAAAMM"),
        (fic_fidc_rows(), [confid_row(DT_COMPTC="2026-09-29")], "2 valores diferentes"),
        ([other_row()], [], "0 valores diferentes"),
    ],
)
def test_competence_must_be_one_date_of_the_month(fie_rows, confid_rows, message):
    with pytest.raises(CdaFormatError, match=message):
        read_rows(fie_rows, confid_rows)


def test_refused_quota_lines_also_count_for_the_competence():
    rows = fic_fidc_rows() + [fie_row(PF_PJ_EMISSOR="PF", CPF_CNPJ_EMISSOR=FAKE_CPF, DT_COMPTC="2026-09-29")]

    with pytest.raises(CdaFormatError, match="2 valores diferentes"):
        read_rows(rows)


def test_future_competence_is_refused():
    period = "209912"
    rows = [fie_row(DT_COMPTC="2099-12-31")]
    data = build_cda_zip(rows, [], period=period)

    with pytest.raises(CdaFormatError, match="posterior a hoje"):
        read_cda_bytes(data, columns.zip_name(period))


def test_member_size_limit():
    with pytest.raises(CdaFormatError, match="passa do limite"):
        read(max_member_bytes=10)


def test_repr_and_report_show_no_cnpj_name_or_value():
    rows = fic_fidc_rows() + [
        fie_row(OTHER_HOLDER, INVESTEES[1]),
        fie_row(PF_PJ_EMISSOR="PF", CPF_CNPJ_EMISSOR=PADDED_CPF_DV_PASSES, EMISSOR=PERSON_NAME),
    ]
    cda = read_rows(rows, [confid_row(), confid_row(OTHER_HOLDER)])
    texts = [repr(cda), "\n".join(format_read_report(cda))]
    texts.extend(repr(h) for h in cda.holdings())
    texts.extend(repr(c) for c in cda.confidential_holdings())

    for text in texts:
        assert_hidden(text)


def test_report_has_the_aggregates():
    rows = fic_fidc_rows() + [
        fie_row(PF_PJ_EMISSOR="PF", CPF_CNPJ_EMISSOR=FAKE_CPF, EMISSOR=PERSON_NAME),
        fie_row(),
        other_row(),
    ]
    report = "\n".join(format_read_report(read_rows(rows)))

    assert "Competencia (DT_COMPTC das linhas de cotas): " + COMPETENCE in report
    assert "cda_fi_BLC_1_202609.csv" in report and "so manifesto, nao lido" in report
    assert "Cotas identificadas (cda_fie, TP_APLIC Cotas de Fundos): 5 linha(s)" in report
    assert "recusado 1 (PF 1; vazio 0;" in report
    assert "EMISSOR descartado (linha com identificador recusado): 1" in report
    assert "posicoes: 4" in report
    # fie_row() repete a chave do primeiro investido, com outro valor.
    assert "repetida: 2 linha(s) em 1 chave(s); com quantidade ou valor diferentes: 1" in report
    assert "mes de DT_CONFID_APLIC: 2026-12 1" in report
    assert "identificadas e confidenciais ao mesmo tempo: 0" in report


def test_report_hides_domain_labels_with_digits():
    cda = read_rows([fie_row(TP_FUNDO_CLASSE=OTHER_HOLDER)])
    report = "\n".join(format_read_report(cda))

    assert OTHER_HOLDER not in report
    assert "(valor com digito, nao exibido) 1" in report


def test_read_cda_zip_from_disk(tmp_path):
    path = tmp_path / ZIP_NAME
    path.write_bytes(build_cda_zip())

    assert len(list(read_cda_zip(path).holdings())) == 3

    with pytest.raises(FileNotFoundError):
        read_cda_zip(tmp_path / "nao_existe.zip")
