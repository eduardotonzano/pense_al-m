"""ZIP ficticio do cadastro de fundos da CVM, montado em memoria.

Nada aqui e dado real. Os CNPJs tem DV valido calculado aqui, sobre raizes
97nnnnnn9999 que nao parecem de empresa; os nomes sao marcados como
ficticios; o CPF (apoio.FAKE_CPF) tem DV invalido.

Os cabecalhos sao escritos aqui de proposito, sem importar
fundos.cadastro.columns: os testes conferem um contra o outro.
"""

import io
import zipfile

from apoio import FAKE_CPF


FUND_HEADER = (
    "ID_Registro_Fundo", "CNPJ_Fundo", "Codigo_CVM", "Data_Registro",
    "Data_Constituicao", "Tipo_Fundo", "Denominacao_Social",
    "Data_Cancelamento", "Situacao", "Data_Inicio_Situacao",
    "Data_Adaptacao_RCVM175", "Data_Inicio_Exercicio_Social",
    "Data_Fim_Exercicio_Social", "Patrimonio_Liquido",
    "Data_Patrimonio_Liquido", "Diretor", "CNPJ_Administrador",
    "Administrador", "Tipo_Pessoa_Gestor", "CPF_CNPJ_Gestor", "Gestor",
)

CLASS_HEADER = (
    "ID_Registro_Fundo", "ID_Registro_Classe", "CNPJ_Classe", "Codigo_CVM",
    "Data_Registro", "Data_Constituicao", "Data_Inicio", "Tipo_Classe",
    "Denominacao_Social", "Situacao", "Data_Inicio_Situacao",
    "Classificacao", "Indicador_Desempenho", "Classe_Cotas",
    "Classificacao_Anbima", "Tributacao_Longo_Prazo",
    "Entidade_Investimento", "Permitido_Aplicacao_CemPorCento_Exterior",
    "Classe_ESG", "Forma_Condominio", "Exclusivo", "Publico_Alvo",
    "Patrimonio_Liquido", "Data_Patrimonio_Liquido", "CNPJ_Auditor",
    "Auditor", "CNPJ_Custodiante", "Custodiante", "CNPJ_Controlador",
    "Controlador",
)

SUBCLASS_HEADER = (
    "ID_Registro_Classe", "ID_Subclasse", "Codigo_CVM", "Data_Constituicao",
    "Data_Inicio", "Denominacao_Social", "Situacao", "Data_Inicio_Situacao",
    "Forma_Condominio", "Exclusivo", "Publico_Alvo", "Previdenciario",
    "Exclusivo_INR", "Exclusivo_Previdencia_Complementar",
)

FIDC_CLASS = "Classes de Cotas de Fundos FIDC"
FIAGRO_CLASS = "Classes de Cotas de Fundos FIAGRO"

MEMBER_DATE = (2026, 10, 27, 1, 26, 8)
REFERENCE_DATE = "2026-10-27"

# Nomes de pessoa natural ficticios: nunca podem chegar ao banco nem a saida.
DIRECTOR_NAME = "Diretor Ficticio Responsavel"
PF_MANAGER_NAME = "Pessoa Fisica Ficticia Gestora"
PF_AUDITOR_NAME = "Pessoa Fisica Ficticia Auditora"

_WEIGHTS_FIRST = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
_WEIGHTS_SECOND = (6,) + _WEIGHTS_FIRST


def _check_digit(values, weights):
    remainder = sum(v * w for v, w in zip(values, weights)) % 11
    return 0 if remainder < 2 else 11 - remainder


def cnpj_with_dv(base12):
    values = [ord(char) - 48 for char in base12]
    first = _check_digit(values, _WEIGHTS_FIRST)
    second = _check_digit(values + [first], _WEIGHTS_SECOND)
    return base12 + str(first) + str(second)


def fake_cnpj(n):
    """CNPJ ficticio numerico, sem mascara, com DV valido (n de 0 a 999999)."""

    return cnpj_with_dv("97" + format(n, "06d") + "9999")


def fake_cnpj_with_leading_zero(n):
    """CNPJ ficticio que comeca com zero (para testar a restauracao)."""

    return cnpj_with_dv("0" + format(n, "07d") + "9999")


def masked(cnpj):
    return cnpj[:2] + "." + cnpj[2:5] + "." + cnpj[5:8] + "/" + cnpj[8:12] + "-" + cnpj[12:]


def fund_row(**changes):
    """Linha ficticia de registro_fundo (FIDC em funcionamento, gestor PJ)."""

    row = {
        "ID_Registro_Fundo": "1",
        "CNPJ_Fundo": fake_cnpj(1),
        "Codigo_CVM": "9000001",
        "Data_Registro": "2020-01-02",
        "Data_Constituicao": "2019-12-01",
        "Tipo_Fundo": "FIDC",
        "Denominacao_Social": "FIDC Exemplo Alfa (ficticio)",
        "Data_Cancelamento": "",
        "Situacao": "Em Funcionamento Normal",
        "Data_Inicio_Situacao": "2020-01-02",
        "Data_Adaptacao_RCVM175": "2025-06-30",
        "Data_Inicio_Exercicio_Social": "2026-01-01",
        "Data_Fim_Exercicio_Social": "2026-12-31",
        "Patrimonio_Liquido": "1000.50",
        "Data_Patrimonio_Liquido": "2026-10-22",
        "Diretor": DIRECTOR_NAME,
        "CNPJ_Administrador": fake_cnpj(901),
        "Administrador": "Administradora Ficticia SA",
        "Tipo_Pessoa_Gestor": "PJ",
        "CPF_CNPJ_Gestor": fake_cnpj(801),
        "Gestor": "Gestora Ficticia Ltda",
    }
    row.update(changes)
    return row


def pf_manager_row(**changes):
    """Linha de fundo com gestor pessoa fisica (CPF ficticio)."""

    values = {
        "Tipo_Pessoa_Gestor": "PF",
        "CPF_CNPJ_Gestor": FAKE_CPF,
        "Gestor": PF_MANAGER_NAME,
    }
    values.update(changes)
    return fund_row(**values)


def class_row(**changes):
    """Linha ficticia de registro_classe (classe FIDC do fundo 1)."""

    row = {
        "ID_Registro_Fundo": "1",
        "ID_Registro_Classe": "1",
        "CNPJ_Classe": fake_cnpj(1),
        "Codigo_CVM": "9100001",
        "Data_Registro": "2020-01-02",
        "Data_Constituicao": "2019-12-01",
        "Data_Inicio": "2020-01-02",
        "Tipo_Classe": FIDC_CLASS,
        "Denominacao_Social": "Classe Exemplo Alfa (ficticia)",
        "Situacao": "Em Funcionamento Normal",
        "Data_Inicio_Situacao": "2020-01-02",
        "Classificacao": "",
        "Indicador_Desempenho": "",
        "Classe_Cotas": "",
        "Classificacao_Anbima": "",
        "Tributacao_Longo_Prazo": "N/A",
        "Entidade_Investimento": "",
        "Permitido_Aplicacao_CemPorCento_Exterior": "",
        "Classe_ESG": "N",
        "Forma_Condominio": "Fechado",
        "Exclusivo": "S",
        "Publico_Alvo": "Profissional",
        "Patrimonio_Liquido": "2000.25",
        "Data_Patrimonio_Liquido": "2026-10-26",
        "CNPJ_Auditor": fake_cnpj(701),
        "Auditor": "Auditoria Ficticia",
        "CNPJ_Custodiante": fake_cnpj(601),
        "Custodiante": "Custodiante Ficticio SA",
        "CNPJ_Controlador": "",
        "Controlador": "",
    }
    row.update(changes)
    return row


def subclass_row(**changes):
    """Linha ficticia de registro_subclasse (so vai para o manifesto)."""

    row = {
        "ID_Registro_Classe": "1",
        "ID_Subclasse": "SUBFICTICIA0001",
        "Codigo_CVM": "",
        "Data_Constituicao": "2019-12-01",
        "Data_Inicio": "2020-01-02",
        "Denominacao_Social": "Subclasse Ficticia",
        "Situacao": "Em Funcionamento Normal",
        "Data_Inicio_Situacao": "2020-01-02",
        "Forma_Condominio": "Fechado",
        "Exclusivo": "N",
        "Publico_Alvo": "Profissional",
        "Previdenciario": "N",
        "Exclusivo_INR": "N",
        "Exclusivo_Previdencia_Complementar": "N",
    }
    row.update(changes)
    return row


def csv_bytes(header, rows, encoding="cp1252"):
    """CSV no formato da CVM: ';', CRLF, cabecalho na primeira linha."""

    lines = [";".join(header)]
    lines.extend(";".join(row[column] for column in header) for row in rows)
    return ("\r\n".join(lines) + "\r\n").encode(encoding)


def build_zip(
    fund_rows=None,
    class_rows=None,
    subclass_rows=None,
    *,
    members=None,
    drop=(),
    extra=None,
    date_time=MEMBER_DATE,
):
    """Bytes de um registro_fundo_classe.zip ficticio.

    members substitui o conteudo (bytes) de um membro; drop tira membros;
    extra acrescenta membros.
    """

    content = {
        "registro_fundo.csv": csv_bytes(
            FUND_HEADER,
            [fund_row()] if fund_rows is None else fund_rows,
        ),
        "registro_classe.csv": csv_bytes(
            CLASS_HEADER,
            [class_row()] if class_rows is None else class_rows,
        ),
        "registro_subclasse.csv": csv_bytes(
            SUBCLASS_HEADER,
            [subclass_row()] if subclass_rows is None else subclass_rows,
        ),
    }
    content.update(members or {})
    content.update(extra or {})

    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in content.items():
            if name in drop:
                continue

            info = zipfile.ZipInfo(name, date_time=date_time)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)

    return buffer.getvalue()


def write_zip(directory, data, name="registro_fundo_classe.zip"):
    """Grava o ZIP ficticio numa pasta temporaria do teste."""

    path = directory / name
    path.write_bytes(data)
    return path
