"""Lista fechada do CDA: os 12 membros do ZIP e o cabecalho dos dois lidos.

Montada a partir do CABECALHO DO DADO de 09/2026 (docs/fundos-descoberta.md,
secao 12.2), que bate com o dicionario. A ordem e a do cabecalho: se a CVM
mudar uma coluna, a leitura falha em vez de ler torto.

So o cda_fie e o cda_fie_CONFID sao lidos: neles estao as posicoes de FIDC
e FIAGRO. Os 10 membros cda_fi_* (outros fundos) so entram no manifesto.
Das linhas lidas, so as de TP_APLIC "Cotas de Fundos" viram posicao.
"""


FIE = "cda_fie"
FIE_CONFID = "cda_fie_CONFID"

# Os 12 membros cda_*_AAAAMM.csv, na ordem da secao 12.2.
TABLES = (
    FIE,
    FIE_CONFID,
    "cda_fi_BLC_1",
    "cda_fi_BLC_2",
    "cda_fi_BLC_3",
    "cda_fi_BLC_4",
    "cda_fi_BLC_5",
    "cda_fi_BLC_6",
    "cda_fi_BLC_7",
    "cda_fi_BLC_8",
    "cda_fi_CONFID",
    "cda_fi_PL",
)

READ_TABLES = (FIE, FIE_CONFID)
IGNORED_TABLES = tuple(table for table in TABLES if table not in READ_TABLES)

HEADERS = {
    FIE: (
        "TP_FUNDO_CLASSE",
        "CNPJ_FUNDO_CLASSE",
        "DENOM_SOCIAL",
        "DT_COMPTC",
        "ID_DOC",
        "VL_PATRIM_LIQ",
        "TP_APLIC",
        "TP_ATIVO",
        "EMISSOR_LIGADO",
        "TP_NEGOC",
        "QT_VENDA_NEGOC",
        "VL_VENDA_NEGOC",
        "QT_AQUIS_NEGOC",
        "VL_AQUIS_NEGOC",
        "QT_POS_FINAL",
        "VL_MERC_POS_FINAL",
        "VL_CUSTO_POS_FINAL",
        "DT_CONFID_APLIC",
        "CD_ATIVO",
        "DS_ATIVO",
        "DT_VENC",
        "PF_PJ_EMISSOR",
        "CPF_CNPJ_EMISSOR",
        "EMISSOR",
        "RISCO_EMISSOR",
        "CD_SELIC",
        "DT_INI_VIGENCIA",
        "CD_PAIS",
        "PAIS",
        "CD_BV_MERC",
        "BV_MERC",
    ),
    FIE_CONFID: (
        "TP_FUNDO_CLASSE",
        "CNPJ_FUNDO_CLASSE",
        "DENOM_SOCIAL",
        "DT_COMPTC",
        "ID_DOC",
        "TP_APLIC",
        "VL_VENDA_NEGOC",
        "VL_AQUIS_NEGOC",
        "VL_MERC_POS_FINAL",
        "VL_CUSTO_POS_FINAL",
        "DT_CONFID_APLIC",
    ),
}

HOLDER_TYPE_COLUMN = "TP_FUNDO_CLASSE"
HOLDER_COLUMN = "CNPJ_FUNDO_CLASSE"
COMPETENCE_COLUMN = "DT_COMPTC"
APPLICATION_COLUMN = "TP_APLIC"
PERSON_TYPE_COLUMN = "PF_PJ_EMISSOR"
INVESTEE_COLUMN = "CPF_CNPJ_EMISSOR"
INVESTEE_NAME_COLUMN = "EMISSOR"
QUANTITY_COLUMN = "QT_POS_FINAL"
VALUE_COLUMN = "VL_MERC_POS_FINAL"
CONFIDENTIAL_UNTIL_COLUMN = "DT_CONFID_APLIC"

# TP_APLIC das posicoes em cotas de fundos.
FUND_QUOTAS = "Cotas de Fundos"

# PF_PJ_EMISSOR: so PJ deixa o identificador valer como CNPJ.
LEGAL_PERSON = "PJ"
NATURAL_PERSON = "PF"


def member_name(table, period):
    """<tabela>_AAAAMM.csv (por exemplo cda_fie_202609.csv)."""

    return table + "_" + period + ".csv"


def zip_name(period):
    """cda_fi_AAAAMM.zip"""

    return "cda_fi_" + period + ".zip"


def field_name(table, column):
    """tabela.coluna da CVM, sem renomear (por exemplo cda_fie.VL_MERC_POS_FINAL)."""

    return table + "." + column


INVESTEE_FIELD = field_name(FIE, INVESTEE_COLUMN)
INVESTEE_NAME_FIELD = field_name(FIE, INVESTEE_NAME_COLUMN)
QUANTITY_FIELD = field_name(FIE, QUANTITY_COLUMN)
VALUE_FIELD = field_name(FIE, VALUE_COLUMN)
CONFIDENTIAL_VALUE_FIELD = field_name(FIE_CONFID, VALUE_COLUMN)
CONFIDENTIAL_UNTIL_FIELD = field_name(FIE_CONFID, CONFIDENTIAL_UNTIL_COLUMN)
