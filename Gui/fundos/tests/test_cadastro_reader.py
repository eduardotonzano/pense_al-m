import hashlib
import io
import zipfile

import pytest

from apoio import FAKE_CPF
from apoio import FAKE_CPF_MASKED
from apoio_cadastro import CLASS_HEADER
from apoio_cadastro import DIRECTOR_NAME
from apoio_cadastro import FIAGRO_CLASS
from apoio_cadastro import FUND_HEADER
from apoio_cadastro import PF_AUDITOR_NAME
from apoio_cadastro import PF_MANAGER_NAME
from apoio_cadastro import SUBCLASS_HEADER
from apoio_cadastro import build_zip
from apoio_cadastro import class_row
from apoio_cadastro import csv_bytes
from apoio_cadastro import fake_cnpj
from apoio_cadastro import fake_cnpj_with_leading_zero
from apoio_cadastro import fund_row
from apoio_cadastro import masked
from apoio_cadastro import pf_manager_row
from apoio_cadastro import write_zip
from fundos.cadastro import columns
from fundos.cadastro.reader import CadastroFormatError
from fundos.cadastro.reader import read_cadastro_bytes
from fundos.cadastro.reader import read_cadastro_zip
from fundos.cadastro.report import format_read_report


def read(data=None, **options):
    return read_cadastro_bytes(
        build_zip() if data is None else data,
        "registro_fundo_classe.zip",
        **options,
    )


def gestor(row):
    return [party for party in row.parties if party.role == "gestor"]


def test_column_list_matches_the_cvm_header():
    assert columns.HEADERS["registro_fundo"] == FUND_HEADER
    assert columns.HEADERS["registro_classe"] == CLASS_HEADER
    assert columns.HEADERS["registro_subclasse"] == SUBCLASS_HEADER
    assert (len(FUND_HEADER), len(CLASS_HEADER), len(SUBCLASS_HEADER)) == (21, 30, 14)


def test_reads_members_lines_and_manifests():
    data = build_zip(
        [fund_row(), fund_row(ID_Registro_Fundo="2", CNPJ_Fundo=fake_cnpj(2))],
        [class_row()],
    )

    cadastro = read(data)

    assert cadastro.zip.sha256 == hashlib.sha256(data).hexdigest()
    assert cadastro.zip.size_bytes == len(data)
    assert cadastro.zip.member_dates == ("2026-10-27",)
    assert [m.file_name for m in cadastro.members] == list(columns.MEMBERS)
    assert [m.line_count for m in cadastro.members] == [2, 1, 1]
    assert [m.column_count for m in cadastro.members] == [21, 30, 14]

    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for member in cadastro.members:
            raw = archive.read(member.file_name)
            assert member.size_bytes == len(raw)
            assert member.sha256 == hashlib.sha256(raw).hexdigest()

    assert len(cadastro.fund_rows) == 2
    assert len(cadastro.class_rows) == 1
    assert cadastro.max_registration_date == "2020-01-02"


def test_normalizes_values_by_type():
    cadastro = read()
    fund = cadastro.fund_rows[0]
    fund_class = cadastro.class_rows[0]

    assert fund.scope == "FIDC"
    assert fund.cnpj == fake_cnpj(1)
    assert fund.values["Data_Registro"] == "2020-01-02"
    assert fund.values["Patrimonio_Liquido"] == "1000.5"
    assert fund.values["Tipo_Pessoa_Gestor"] == "PJ"
    assert "Data_Cancelamento" not in fund.values
    assert fund_class.values["Classe_ESG"] is False
    assert fund_class.values["Exclusivo"] is True
    assert fund_class.values["Tributacao_Longo_Prazo"] == "N/A"
    assert "Classe_Cotas" not in fund_class.values
    assert "CNPJ_Classe" not in fund_class.values
    assert "CNPJ_Auditor" not in fund_class.values


def test_decodes_cp1252():
    name = "Fundo Ficticio A\u00e7\u00e3o \u00danica"
    cadastro = read(build_zip([fund_row(Denominacao_Social=name)]))

    assert cadastro.fund_rows[0].values["Denominacao_Social"] == name


def test_byte_undefined_in_cp1252_fails():
    content = csv_bytes(FUND_HEADER, [fund_row()]).replace(b"Alfa", b"Al\x81a")

    with pytest.raises(CadastroFormatError, match="nao decodifica como cp1252"):
        read(build_zip(members={"registro_fundo.csv": content}))


@pytest.mark.parametrize(
    "header, message",
    [
        (FUND_HEADER[:-1], "faltam Gestor"),
        (FUND_HEADER + ("Coluna_Nova",), "1 coluna\\(s\\) desconhecida\\(s\\)"),
        (
            ("CNPJ_Fundo", "ID_Registro_Fundo") + FUND_HEADER[2:],
            "a posicao 1 deveria ser ID_Registro_Fundo",
        ),
    ],
)
def test_different_header_fails(header, message):
    row = dict(fund_row(), Coluna_Nova="x")
    content = csv_bytes(header, [row])

    with pytest.raises(CadastroFormatError, match=message):
        read(build_zip(members={"registro_fundo.csv": content}))


def test_header_error_never_repeats_unknown_names():
    content = csv_bytes(FUND_HEADER[:-1] + (FAKE_CPF,), [dict(fund_row(), **{FAKE_CPF: "x"})])

    with pytest.raises(CadastroFormatError) as error:
        read(build_zip(members={"registro_fundo.csv": content}))

    assert FAKE_CPF not in str(error.value)


def test_missing_or_extra_member_fails():
    with pytest.raises(CadastroFormatError, match="faltam registro_classe.csv"):
        read(build_zip(drop=("registro_classe.csv",)))

    with pytest.raises(CadastroFormatError, match="1 membro\\(s\\) inesperado\\(s\\)"):
        read(build_zip(extra={"outro.csv": b"a;b\r\n"}))


def test_row_with_wrong_width_fails_citing_the_line():
    content = csv_bytes(FUND_HEADER, [fund_row()]) + b"1;2;3\r\n"

    with pytest.raises(CadastroFormatError, match="registro_fundo.csv, linha 3: 3 campo"):
        read(build_zip(members={"registro_fundo.csv": content}))


def test_member_over_the_limit_fails():
    with pytest.raises(CadastroFormatError, match="passa do limite"):
        read(max_member_bytes=100)


def test_not_a_zip_fails():
    with pytest.raises(CadastroFormatError, match="nao e um ZIP valido"):
        read(b"isto nao e um zip")


def test_mask_and_missing_leading_zeros_are_normalized():
    leading = fake_cnpj_with_leading_zero(5)
    cadastro = read(
        build_zip(
            [
                fund_row(
                    CNPJ_Fundo=masked(fake_cnpj(3)),
                    CNPJ_Administrador=leading[1:],
                )
            ],
            [class_row(CNPJ_Classe=leading[1:], CNPJ_Custodiante=masked(fake_cnpj(4)))],
        )
    )
    fund = cadastro.fund_rows[0]
    fund_class = cadastro.class_rows[0]
    administrator = [p for p in fund.parties if p.role == "administrador"][0]
    custodian = [p for p in fund_class.parties if p.role == "custodiante"][0]

    assert leading.startswith("0")
    assert fund.cnpj == fake_cnpj(3)
    assert administrator.cnpj == leading
    assert fund_class.cnpj == leading
    assert custodian.cnpj == fake_cnpj(4)


def test_invalid_identity_cnpj_is_counted():
    wrong_dv = fake_cnpj(1)[:12] + ("00" if fake_cnpj(1)[12:] != "00" else "11")
    cadastro = read(build_zip([fund_row(CNPJ_Fundo=wrong_dv)]))

    assert cadastro.fund_rows[0].cnpj is None
    assert cadastro.counts[("identificador", "registro_fundo.CNPJ_Fundo", "invalido", "FIDC")] == 1


@pytest.mark.parametrize(
    "table, column, value, kind",
    [
        ("fund", "Data_Registro", "02/01/2020", "date"),
        ("fund", "Patrimonio_Liquido", "1.000,50", "numeric"),
        ("class", "Exclusivo", "X", "boolean"),
    ],
)
def test_value_out_of_format_in_scope_fails(table, column, value, kind):
    if table == "fund":
        data = build_zip([fund_row(**{column: value})])
        member = "registro_fundo.csv"
    else:
        data = build_zip(class_rows=[class_row(**{column: value})])
        member = "registro_classe.csv"

    with pytest.raises(CadastroFormatError) as error:
        read(data)

    message = str(error.value)
    assert member + ", linha 2, coluna " + column in message
    assert "fora do formato " + kind in message
    assert value not in message


def test_value_out_of_format_out_of_scope_is_counted_and_dropped():
    cadastro = read(
        build_zip(
            [
                fund_row(),
                fund_row(
                    ID_Registro_Fundo="2",
                    CNPJ_Fundo=fake_cnpj(2),
                    Tipo_Fundo="FII",
                    Data_Inicio_Situacao="02/01/2020",
                    Patrimonio_Liquido="1.000,50",
                ),
            ],
            [class_row(), class_row(ID_Registro_Classe="2", Tipo_Classe="Classes de Cotas de Fundos FII", Exclusivo="X")],
        )
    )
    other = cadastro.fund_rows[1]

    assert other.scope is None
    assert "Data_Inicio_Situacao" not in other.values
    assert other.invalid_columns == frozenset({"Data_Inicio_Situacao", "Patrimonio_Liquido"})
    assert cadastro.counts[("fora_do_formato", "registro_fundo.Data_Inicio_Situacao", "outros")] == 1
    assert cadastro.counts[("fora_do_formato", "registro_fundo.Patrimonio_Liquido", "outros")] == 1
    assert cadastro.counts[("fora_do_formato", "registro_classe.Exclusivo", "outros")] == 1


def test_out_of_scope_rows_keep_only_the_selection_columns():
    cadastro = read(build_zip([fund_row(Tipo_Fundo="FI")]))
    row = cadastro.fund_rows[0]

    assert set(row.values) <= columns.SELECTION_COLUMNS["registro_fundo"]
    assert row.parties == ()
    assert row.cnpj == fake_cnpj(1)


def test_cpf_of_a_natural_person_manager_is_discarded_with_the_name():
    cadastro = read(build_zip([pf_manager_row()]))
    row = cadastro.fund_rows[0]
    counts = cadastro.counts

    assert gestor(row) == []
    assert row.values["Tipo_Pessoa_Gestor"] == "PF"
    assert counts[("identificador", "registro_fundo.CPF_CNPJ_Gestor", "cpf", "FIDC")] == 1
    assert counts[("pf", "registro_fundo.Tipo_Pessoa_Gestor", "FIDC")] == 1
    assert counts[("nome_descartado", "registro_fundo.Gestor", "FIDC")] == 1
    assert FAKE_CPF not in repr(cadastro)
    assert PF_MANAGER_NAME not in repr(cadastro)


def test_natural_person_manager_with_cnpj_format_is_also_discarded():
    cadastro = read(build_zip([pf_manager_row(CPF_CNPJ_Gestor=fake_cnpj(802))]))

    assert gestor(cadastro.fund_rows[0]) == []
    assert cadastro.counts[("pf_cnpj", "registro_fundo.CPF_CNPJ_Gestor", "FIDC")] == 1
    assert PF_MANAGER_NAME not in repr(cadastro)


def test_masked_cpf_counts_as_cpf_even_with_legal_person_type():
    cadastro = read(build_zip([fund_row(CPF_CNPJ_Gestor=FAKE_CPF_MASKED, Gestor=PF_MANAGER_NAME)]))

    assert gestor(cadastro.fund_rows[0]) == []
    assert cadastro.counts[("identificador", "registro_fundo.CPF_CNPJ_Gestor", "cpf", "FIDC")] == 1
    assert PF_MANAGER_NAME not in repr(cadastro)


def test_cpf_of_an_auditor_is_discarded_with_the_name():
    cadastro = read(
        build_zip(class_rows=[class_row(CNPJ_Auditor=FAKE_CPF, Auditor=PF_AUDITOR_NAME)])
    )
    row = cadastro.class_rows[0]

    assert [p.role for p in row.parties] == ["custodiante"]
    assert cadastro.counts[("identificador", "registro_classe.CNPJ_Auditor", "cpf", "FIDC")] == 1
    assert cadastro.counts[("nome_descartado", "registro_classe.Auditor", "FIDC")] == 1
    assert FAKE_CPF not in repr(cadastro)
    assert PF_AUDITOR_NAME not in repr(cadastro)


def test_name_without_a_valid_cnpj_is_discarded():
    wrong_dv = fake_cnpj(601)[:12] + ("00" if fake_cnpj(601)[12:] != "00" else "11")
    cadastro = read(
        build_zip(
            class_rows=[
                class_row(CNPJ_Custodiante=wrong_dv, CNPJ_Controlador="", Controlador="Controlador Ficticio")
            ]
        )
    )
    row = cadastro.class_rows[0]

    assert [p.role for p in row.parties] == ["auditor"]
    assert cadastro.counts[("identificador", "registro_classe.CNPJ_Custodiante", "invalido", "FIDC")] == 1
    assert cadastro.counts[("nome_descartado", "registro_classe.Custodiante", "FIDC")] == 1
    assert cadastro.counts[("nome_descartado", "registro_classe.Controlador", "FIDC")] == 1
    assert "Controlador Ficticio" not in repr(cadastro)


def test_party_keeps_the_cnpj_and_the_name():
    row = read().fund_rows[0]

    assert [(p.role, p.field_name, p.cnpj, p.name_field_name, p.name) for p in row.parties] == [
        ("administrador", "registro_fundo.CNPJ_Administrador", fake_cnpj(901), "registro_fundo.Administrador", "Administradora Ficticia SA"),
        ("gestor", "registro_fundo.CPF_CNPJ_Gestor", fake_cnpj(801), "registro_fundo.Gestor", "Gestora Ficticia Ltda"),
    ]


def test_director_is_never_kept():
    cadastro = read()

    assert all("Diretor" not in row.values for row in cadastro.fund_rows)
    assert DIRECTOR_NAME not in repr(cadastro)
    assert DIRECTOR_NAME not in "\n".join(format_read_report(cadastro))


def test_scope_counts_by_type():
    cadastro = read(
        build_zip(
            [
                fund_row(),
                fund_row(ID_Registro_Fundo="2", CNPJ_Fundo=fake_cnpj(2), Tipo_Fundo="FIAGRO"),
                fund_row(ID_Registro_Fundo="3", CNPJ_Fundo=fake_cnpj(3), Tipo_Fundo="FI"),
            ],
            [class_row(), class_row(ID_Registro_Classe="2", Tipo_Classe=FIAGRO_CLASS)],
        )
    )
    counts = cadastro.counts

    assert counts[("linhas_por_tipo", "registro_fundo", "FIDC")] == 1
    assert counts[("linhas_por_tipo", "registro_fundo", "FIAGRO")] == 1
    assert counts[("linhas_por_tipo", "registro_fundo", "outros")] == 1
    assert counts[("linhas_por_tipo", "registro_classe", "FIAGRO")] == 1
    assert [row.scope for row in cadastro.fund_rows] == ["FIDC", "FIAGRO", None]


def test_report_has_only_aggregates():
    cadastro = read(
        build_zip(
            [fund_row(), pf_manager_row(ID_Registro_Fundo="2", CNPJ_Fundo=fake_cnpj(2))],
            [class_row(CNPJ_Auditor=FAKE_CPF, Auditor=PF_AUDITOR_NAME)],
        )
    )

    text = "\n".join(format_read_report(cadastro))

    assert "registro_fundo.csv: 2 linha(s), 21 coluna(s)" in text
    assert "registro_subclasse.csv: 1 linha(s), 14 coluna(s), so manifesto" in text
    assert "registro_fundo.Tipo_Fundo: FIDC 2, FIAGRO 0, outros 0" in text
    assert "Colunas excluidas (nunca guardadas): registro_fundo.Diretor" in text

    for secret in (
        FAKE_CPF,
        PF_MANAGER_NAME,
        PF_AUDITOR_NAME,
        DIRECTOR_NAME,
        fake_cnpj(1),
        fake_cnpj(2),
        fake_cnpj(801),
        fake_cnpj(901),
        "Gestora Ficticia",
        "Administradora Ficticia",
        "Exemplo Alfa",
    ):
        assert secret not in text


def test_reads_from_disk_without_extracting_anything(tmp_path):
    path = write_zip(tmp_path, build_zip())
    before = sorted(p.name for p in tmp_path.iterdir())

    cadastro = read_cadastro_zip(path)

    assert cadastro.zip.file_name == "registro_fundo_classe.zip"
    assert sorted(p.name for p in tmp_path.iterdir()) == before


def test_missing_zip_is_refused(tmp_path):
    with pytest.raises(FileNotFoundError, match="ZIP nao encontrado"):
        read_cadastro_zip(tmp_path / "inexistente.zip")
