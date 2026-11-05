"""ZIP ficticio do CDA (cda_fi_AAAAMM.zip, 12 membros), montado em memoria, e cadastro ficticio.

Nada aqui e dado real: CNPJs ficticios de apoio.make_test_cnpj (o detentor
com mascara e o investido sem, como no CDA), nomes marcados como ficticios,
CPF ficticio (apoio.FAKE_CPF, DV invalido) e o CPF ficticio completado com
zeros. Os 10 membros cda_fi_* tem um conteudo ficticio minimo: o leitor nao
os decodifica.
"""

import io
import zipfile

from apoio import make_test_cnpj
from apoio_cadastro import FIAGRO_CLASS
from apoio_cadastro import build_zip
from apoio_cadastro import class_row
from apoio_cadastro import csv_bytes
from apoio_cadastro import fund_row
from apoio_cadastro import masked
from fundos.cadastro.loader import load_cadastro
from fundos.cadastro.reader import read_cadastro_bytes
from fundos.cadastro.selection import select_fidc_fiagro
from fundos.cda import columns as spec


PERIOD = "202609"
COMPETENCE = "2026-09-30"
CONFIDENTIAL_UNTIL = "2026-12-31"
MEMBER_DATE = (2026, 10, 29, 3, 58, 52)
ZIP_NAME = spec.zip_name(PERIOD)

HOLDER = make_test_cnpj(1)
OTHER_HOLDER = make_test_cnpj(2)
CONFIDENTIAL_HOLDER = make_test_cnpj(3)
INVESTEES = (make_test_cnpj(4), make_test_cnpj(5), make_test_cnpj(6))

HOLDER_NAME = "FIDC Detentor (ficticio)"
INVESTEE_NAME = "FIDC Investido (ficticio)"
PERSON_NAME = "Pessoa Natural (ficticia)"

# Conteudo dos membros que o leitor so manifesta. O byte 0x81 nao existe em
# cp1252: se o leitor decodificasse, a leitura falharia.
IGNORED_CONTENT = b"CAMPO_FICTICIO\r\n\x81\r\n"


FUND_ONLY = make_test_cnpj(7)
UNKNOWN_HOLDER = make_test_cnpj(8)
MIXED = make_test_cnpj(9)


def load_fictitious_cadastro(db, fidc=(1, 2, 3, 4), fiagro=(5,), funds_without_class=(7,), mixed=(9,)):
    """Carrega um cadastro ficticio (CNPJ make_test_cnpj(n)) pelo carregador do cadastro.

    fidc e fiagro: fundo e classe do tipo, com o mesmo CNPJ n.
    funds_without_class: fundo FIDC sem classe. mixed: fundo FIAGRO com
    classe FIDC de mesmo CNPJ (tipo misto). Padrao: o detentor 1, o outro
    detentor 2, o confidencial 3 e os investidos 4 (FIDC) e 5 (FIAGRO); o
    investido 6 e o detentor 8 ficam fora do cadastro.
    """

    def fund(n, tipo):
        return fund_row(ID_Registro_Fundo=str(n), CNPJ_Fundo=make_test_cnpj(n), Tipo_Fundo=tipo)

    def klass(n, **changes):
        return class_row(
            ID_Registro_Fundo=str(n), ID_Registro_Classe=str(n), CNPJ_Classe=make_test_cnpj(n), **changes
        )

    fund_rows = [fund(n, "FIDC") for n in tuple(fidc) + tuple(funds_without_class)]
    fund_rows += [fund(n, "FIAGRO") for n in tuple(fiagro) + tuple(mixed)]
    class_rows = [klass(n) for n in tuple(fidc) + tuple(mixed)]
    class_rows += [klass(n, Tipo_Classe=FIAGRO_CLASS) for n in fiagro]
    cadastro = read_cadastro_bytes(build_zip(fund_rows, class_rows), "registro_fundo_classe.zip")

    with db.transaction() as connection:
        load_cadastro(connection, cadastro, select_fidc_fiagro(cadastro), "2026-10-27")


def investee_name(n):
    return "FIDC Investido " + str(n) + " (ficticio)"


def fie_row(holder=HOLDER, investee=INVESTEES[0], **changes):
    """Linha ficticia de cotas do cda_fie (PJ, investido com 14 digitos)."""

    row = {column: "" for column in spec.HEADERS[spec.FIE]}
    row.update(
        {
            "TP_FUNDO_CLASSE": "CLASSES - FIDC",
            "CNPJ_FUNDO_CLASSE": masked(holder),
            "DENOM_SOCIAL": HOLDER_NAME,
            "DT_COMPTC": COMPETENCE,
            "ID_DOC": "900001",
            "VL_PATRIM_LIQ": "5000.75",
            "TP_APLIC": spec.FUND_QUOTAS,
            "QT_POS_FINAL": "10.5",
            "VL_MERC_POS_FINAL": "1234.56",
            "PF_PJ_EMISSOR": "PJ",
            "CPF_CNPJ_EMISSOR": investee,
            "EMISSOR": INVESTEE_NAME,
        }
    )
    row.update(changes)
    return row


def other_row(holder=HOLDER, **changes):
    """Linha ficticia do cda_fie que nao e de cotas (so contada)."""

    values = {
        "TP_APLIC": "Outras aplicações",
        "PF_PJ_EMISSOR": "",
        "EMISSOR": "",
        "QT_POS_FINAL": "",
        "VL_MERC_POS_FINAL": "7.5",
    }
    values.update(changes)
    return fie_row(holder, "", **values)


def confid_row(holder=CONFIDENTIAL_HOLDER, **changes):
    """Linha ficticia de cotas do cda_fie_CONFID."""

    row = {column: "" for column in spec.HEADERS[spec.FIE_CONFID]}
    row.update(
        {
            "TP_FUNDO_CLASSE": "CLASSES - FIDC",
            "CNPJ_FUNDO_CLASSE": masked(holder),
            "DENOM_SOCIAL": HOLDER_NAME,
            "DT_COMPTC": COMPETENCE,
            "ID_DOC": "900002",
            "TP_APLIC": spec.FUND_QUOTAS,
            "VL_MERC_POS_FINAL": "4321.25",
            "DT_CONFID_APLIC": CONFIDENTIAL_UNTIL,
        }
    )
    row.update(changes)
    return row


def fic_fidc_rows():
    """FIC-FIDC ficticio: o detentor com 3 posicoes, em 3 investidos."""

    return [
        fie_row(investee=investee, EMISSOR=investee_name(n), VL_MERC_POS_FINAL=str(100 * n) + ".5")
        for n, investee in enumerate(INVESTEES, start=1)
    ]


def build_cda_zip(
    fie_rows=None,
    confid_rows=None,
    *,
    period=PERIOD,
    members=None,
    drop=(),
    extra=None,
    date_time=MEMBER_DATE,
):
    """Bytes de um cda_fi_AAAAMM.zip ficticio.

    fie_rows e confid_rows: linhas (padrao: o FIC-FIDC e uma confidencial);
    members substitui o conteudo (bytes) de um membro pela tabela; drop tira
    tabelas; extra acrescenta membros pelo nome.
    """

    rows = {
        spec.FIE: fic_fidc_rows() if fie_rows is None else fie_rows,
        spec.FIE_CONFID: [confid_row()] if confid_rows is None else confid_rows,
    }
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for table in spec.TABLES:
            if table in drop:
                continue

            data = (members or {}).get(table)

            if data is None:
                if table in spec.READ_TABLES:
                    data = csv_bytes(spec.HEADERS[table], rows[table])
                else:
                    data = IGNORED_CONTENT

            info = zipfile.ZipInfo(spec.member_name(table, period), date_time=date_time)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)

        for name, data in (extra or {}).items():
            archive.writestr(zipfile.ZipInfo(name, date_time=date_time), data)

    return buffer.getvalue()
