"""ZIP ficticio do informe mensal de FIDC (18 tabelas), montado em memoria.

Nada aqui e dado real: CNPJs ficticios de apoio_cadastro (com mascara, como
no informe), nomes marcados como ficticios, CPF de DV invalido
(apoio.FAKE_CPF) na coluna de cedente. Os nomes das colunas vem da lista
fechada de fundos.informe_fidc.columns; a contagem por tabela e conferida
nos testes contra a secao 10.2 de docs/fundos-descoberta.md.
"""

import io
import zipfile

from apoio import FAKE_CPF
from apoio_cadastro import build_zip
from apoio_cadastro import class_row
from apoio_cadastro import csv_bytes
from apoio_cadastro import fake_cnpj
from apoio_cadastro import fund_row
from apoio_cadastro import masked
from fundos.cadastro.loader import load_cadastro
from fundos.cadastro.reader import read_cadastro_bytes
from fundos.cadastro.selection import select_fidc_fiagro
from fundos.informe_fidc import columns as spec


PERIOD = "202609"
COMPETENCE = "2026-09-30"
MEMBER_DATE = (2026, 10, 24, 8, 34, 6)
ZIP_NAME = "inf_mensal_fidc_" + PERIOD + ".zip"

ADMIN_NAME = "Administradora Ficticia SA"
SENIOR = "Subclasse Senior Serie 1"
# O mesmo rotulo vem com espacos e '|' diferentes na X_1 e nas outras.
SUBORDINATE_X1 = "Subclasse  Subordinada Subordinada 1"
SUBORDINATE = "Subclasse Subordinada Subordinada 1 |"
OPERATIONS = ("Amortiza\u00e7\u00f5es", "Capta\u00e7\u00f5es no M\u00eas")

# Cedentes ficticios: um CPF (DV invalido) e um CNPJ, com percentuais.
CEDENTES = {
    "TAB_I2A12_CPF_CNPJ_CEDENTE_1": FAKE_CPF,
    "TAB_I2A12_PR_CEDENTE_1": "60.5",
    "TAB_I2B12_CPF_CNPJ_CEDENTE_1": fake_cnpj(555),
    "TAB_I2B12_PR_CEDENTE_1": "10",
}

_DEFAULTS = {
    "CLASSE_UNICA": "S",
    "FUNDO_EXCLUSIVO": "N",
    "COTST_INTERESSE": "N",
    "CNPJ_ADMIN": masked(fake_cnpj(901)),
    "ADMIN": ADMIN_NAME,
    "CLASSE": "Classe Ficticia Unica",
    "CONDOM": "FECHADO",
    "PRAZO_CONVERSAO_COTA": "",
    "TP_PRAZO_CONVERSAO_COTA": "",
    "PRAZO_PAGTO_RESGATE": "",
    "TP_PRAZO_PAGTO_RESGATE": "",
    "TAB_I_VL_ATIVO": "1200.00",
    "TAB_IV_A_VL_PL": "1000.50",
    "TAB_X_VL_COTA": "1.234567",
    **CEDENTES,
}


def subject_name(n):
    return "FIDC Exemplo " + str(n) + " (ficticio)"


def row(table, n=1, subject_type="Classe", **changes):
    """Linha ficticia de uma tabela para o assunto n (CNPJ ficticio n)."""

    values = {
        spec.SUBJECT_TYPE_COLUMN: subject_type,
        spec.SUBJECT_COLUMN: masked(fake_cnpj(n)),
        spec.NAME_COLUMN: subject_name(n),
        spec.COMPETENCE_COLUMN: COMPETENCE,
    }

    for column in spec.HEADERS[table][4:]:
        if column in _DEFAULTS:
            values[column] = _DEFAULTS[column]
        elif spec.KINDS[table][column] == spec.EXCLUDED:
            values[column] = ""
        elif column == "CNPJ_CLASSE":
            values[column] = fake_cnpj(n)
        else:
            values[column] = "0"

    values.update(changes)
    return values


def subject_rows(n=1, subject_type="Classe", subclass_ids=("SUBFICTICIA0001", "")):
    """Linhas do assunto n nas 18 tabelas: duas series, senior e subordinada."""

    rows = {}

    for table in spec.TABLES:
        if table == "tab_VIII":
            rows[table] = [
                row(table, n, subject_type, SEQUENCIAL=str(position), VALOR="5.5")
                for position in (1, 2)
            ]
        elif table == "tab_X_1":
            rows[table] = [
                row(table, n, subject_type, TAB_X_CLASSE_SERIE=label, ID_SUBCLASSE=sid, TAB_X_NR_COTST="3")
                for label, sid in zip((SENIOR, SUBORDINATE_X1), subclass_ids)
            ]
        elif table == "tab_X_4":
            rows[table] = [
                row(table, n, subject_type, TAB_X_CLASSE_SERIE=label, TAB_X_TP_OPER=operation)
                for label in (SENIOR, SUBORDINATE)
                for operation in OPERATIONS
            ]
        elif table in spec.SERIES_TABLES:
            rows[table] = [
                row(table, n, subject_type, TAB_X_CLASSE_SERIE=label)
                for label in (SENIOR, SUBORDINATE)
            ]
        else:
            rows[table] = [row(table, n, subject_type)]

    return rows


def merge(*parts):
    """Junta as linhas de varios assuntos, tabela por tabela."""

    merged = {table: [] for table in spec.TABLES}

    for part in parts:
        for table, rows in part.items():
            merged[table].extend(rows)

    return merged


def load_fictitious_cadastro(db, classes=(1,), funds_without_class=(), extra_classes=()):
    """Carrega um cadastro ficticio pelo carregador do cadastro.

    classes: para cada n, fundo e classe FIDC com o CNPJ ficticio n.
    funds_without_class: fundos com o CNPJ n, sem classe.
    extra_classes: pares (n, m), classe com o CNPJ n do fundo m.
    """

    fund_rows = [
        fund_row(ID_Registro_Fundo=str(n), CNPJ_Fundo=fake_cnpj(n))
        for n in tuple(classes) + tuple(funds_without_class)
    ]
    class_rows = [
        class_row(ID_Registro_Fundo=str(n), ID_Registro_Classe=str(n), CNPJ_Classe=fake_cnpj(n))
        for n in classes
    ]
    class_rows.extend(
        class_row(ID_Registro_Fundo=str(m), ID_Registro_Classe=str(100000 + n), CNPJ_Classe=fake_cnpj(n))
        for n, m in extra_classes
    )
    cadastro = read_cadastro_bytes(build_zip(fund_rows, class_rows), "registro_fundo_classe.zip")

    with db.transaction() as connection:
        load_cadastro(connection, cadastro, select_fidc_fiagro(cadastro), "2026-10-27")


def build_informe_zip(
    tables=None,
    *,
    period=PERIOD,
    members=None,
    drop=(),
    extra=None,
    date_time=MEMBER_DATE,
):
    """Bytes de um inf_mensal_fidc_AAAAMM.zip ficticio.

    tables: {tabela: linhas} (padrao: o assunto 1); members substitui o
    conteudo (bytes) de um membro pela tabela; drop tira tabelas; extra
    acrescenta membros pelo nome.
    """

    tables = subject_rows() if tables is None else tables
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for table in spec.TABLES:
            if table in drop:
                continue

            data = (members or {}).get(table)

            if data is None:
                data = csv_bytes(spec.HEADERS[table], tables.get(table, []))

            info = zipfile.ZipInfo(spec.member_name(table, period), date_time=date_time)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)

        for name, data in (extra or {}).items():
            archive.writestr(zipfile.ZipInfo(name, date_time=date_time), data)

    return buffer.getvalue()
