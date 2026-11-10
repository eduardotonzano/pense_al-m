"""ZIP ficticio do informe mensal de FIAGRO (2 arquivos), montado em memoria.

Nada aqui e dado real: CNPJs ficticios de apoio_cadastro (sem mascara, como
no informe de FIAGRO), nomes e ISIN marcados como ficticios, contatos com
dominio .invalid. Os nomes das colunas vem da lista fechada de
fundos.informe_fiagro.columns; a contagem por arquivo e conferida nos testes
contra a secao 9.2 de docs/fundos-descoberta.md.
"""

import io
import zipfile

from apoio_cadastro import FIAGRO_CLASS
from apoio_cadastro import build_zip
from apoio_cadastro import class_row as cadastro_class_row
from apoio_cadastro import csv_bytes
from apoio_cadastro import fake_cnpj
from apoio_cadastro import fund_row
from fundos.cadastro.loader import load_cadastro
from fundos.cadastro.reader import read_cadastro_bytes
from fundos.cadastro.selection import select_fidc_fiagro
from fundos.informe_fiagro import columns as spec


PERIOD = "202609"
DATA_REFERENCIA = "2026-09-01"
COMPETENCE = "2026-09-30"
MEMBER_DATE = (2026, 10, 24, 8, 34, 6)
ZIP_NAME = "inf_mensal_fiagro_" + PERIOD + ".zip"

ADMIN_CNPJ = fake_cnpj(901)
ADMIN_NAME = "Administradora Ficticia SA"
MANAGER_CNPJ = fake_cnpj(802)
MANAGER_NAME = "Gestora Ficticia do Informe Ltda"

# As duas grafias da primeira subclasse (docs/fundos-descoberta.md, 9.3).
FIRST_SUBCLASS = "Subclasse 1 (ou classe \u00fanica)"
FIRST_SUBCLASS_NO_SPACE = "Subclasse 1(ou classe \u00fanica)"
SECOND_SUBCLASS = "Subclasse 2"

# Contato ficticio: nunca pode chegar ao banco nem a saida.
CONTACTS = {
    "Entidade_Administradora": "Entidade Ficticia Contato",
    "Email_Administrador": "contato.ficticio@exemplo.invalid",
    "Servico_Atendimento_Cotista": "Atendimento Ficticio fone 0000-0000",
    "Site": "https://fiagro-ficticio.exemplo.invalid",
}

_DEFAULTS = {
    "Data_Entrega": "2026-10-15",
    "Versao": "1",
    "Classe_Unica": "N",
    "CNPJ_Administrador": ADMIN_CNPJ,
    "Nome_Administrador": ADMIN_NAME,
    "Data_Registro": "2020-01-02",
    "Publico_Alvo": "INVESTIDOR PROFISSIONAL",
    "Cotistas_Vinculo_Familiar": "N",
    "Regra_Anexo": "Anexo Normativo Ficticio",
    "Classificacao_Autorregulada": "",
    "Prazo_Duracao": "99 ANOS",
    "Encerramento_Exercicio_Social": "31/12",
    "Mercado_Negociacao": "BOLSA",
    "Nome_Gestor": MANAGER_NAME,
    "CNPJ_Gestor": MANAGER_CNPJ,
    "Numero_Cotistas": "10",
    "Valor_Ativo": "1200.00",
    "Patrimonio_Liquido": "1000.50",
    "Valor_Patrimonial_Cotas": "1.234567",
    **CONTACTS,
}


def subject_name(n):
    return "FIAGRO Exemplo " + str(n) + " (ficticio)"


def fake_isin(n):
    """ISIN ficticio (prefixo XX, nao e pais) com 12 caracteres."""

    return "XXFICTCTF" + format(n, "03d")


def class_row(n=1, **changes):
    """Linha ficticia do arquivo de classe para a classe n (CNPJ ficticio n)."""

    values = {
        spec.SUBJECT_COLUMN: fake_cnpj(n),
        spec.NAME_COLUMN: subject_name(n),
        spec.REFERENCE_COLUMN: DATA_REFERENCIA,
        spec.ISIN_COLUMN: fake_isin(n),
    }

    for column in spec.HEADERS[spec.CLASS_TABLE]:
        if column not in values:
            values[column] = _DEFAULTS.get(column, "0")

    values.update(changes)
    return values


def subclass_row(n=1, label=FIRST_SUBCLASS, **changes):
    """Linha ficticia do arquivo de subclasse da classe n."""

    values = {
        spec.SUBJECT_COLUMN: fake_cnpj(n),
        spec.NAME_COLUMN: subject_name(n),
        spec.REFERENCE_COLUMN: DATA_REFERENCIA,
        spec.SERIES_LABEL_COLUMN: label,
        "Numero_Cotas": "100",
        "Valor_Patrimonial_Cota": "10.005",
    }
    values.update(changes)
    return values


def subject_rows(n=1, labels=(FIRST_SUBCLASS, SECOND_SUBCLASS), **changes):
    """Linha de classe e linhas de subclasse da classe n."""

    return {
        spec.CLASS_TABLE: [class_row(n, **changes)],
        spec.SUBCLASS_TABLE: [subclass_row(n, label) for label in labels],
    }


def merge(*parts):
    """Junta as linhas de varias classes, arquivo por arquivo."""

    merged = {table: [] for table in spec.TABLES}

    for part in parts:
        for table, rows in part.items():
            merged[table].extend(rows)

    return merged


def load_fictitious_cadastro(db, classes=(1,), funds_without_class=()):
    """Carrega um cadastro ficticio de FIAGRO pelo carregador do cadastro.

    classes: para cada n, fundo e classe FIAGRO com o CNPJ ficticio n.
    funds_without_class: fundos FIAGRO com o CNPJ n, sem classe.
    """

    fund_rows = [
        fund_row(ID_Registro_Fundo=str(n), CNPJ_Fundo=fake_cnpj(n), Tipo_Fundo="FIAGRO")
        for n in tuple(classes) + tuple(funds_without_class)
    ]
    class_rows = [
        cadastro_class_row(
            ID_Registro_Fundo=str(n),
            ID_Registro_Classe=str(n),
            CNPJ_Classe=fake_cnpj(n),
            Tipo_Classe=FIAGRO_CLASS,
        )
        for n in classes
    ]
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
    """Bytes de um inf_mensal_fiagro_AAAAMM.zip ficticio.

    tables: {arquivo: linhas} (padrao: a classe 1); members substitui o
    conteudo (bytes) de um membro pelo arquivo; drop tira arquivos; extra
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
