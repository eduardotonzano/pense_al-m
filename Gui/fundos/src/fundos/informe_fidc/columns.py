"""Lista fechada das colunas do informe mensal de FIDC (18 tabelas, 461 campos).

Montada a partir do CABECALHO DO DADO de 09/2026, nao do dicionario: os dois
divergem nas tabelas X.1, X.2, X.3, X.4 e X.6 (docs/fundos-descoberta.md,
secao 10.2). A ordem e a do cabecalho: se a CVM mudar uma coluna, a leitura
falha em vez de ler torto.

Tipos:
- key: TP_FUNDO_CLASSE, CNPJ_FUNDO_CLASSE e DT_COMPTC identificam o assunto
  e a competencia; nao viram observacao.
- name: DENOM_SOCIAL, igual nas 18 tabelas; so a da tab_I e gravada.
- text, numeric, boolean: viram observacao (tab_X.COLUNA da CVM).
- series_label: TAB_X_CLASSE_SERIE; o rotulo original e observacao da serie
  e o rotulo normalizado e a chave da serie.
- subclass: ID_SUBCLASSE (so tab_X_1); observacao da serie e, quando so
  aparece num assunto e rotulo, chave da serie.
- cnpj_text: CNPJ_CLASSE da tab_I; vira observacao so com CNPJ valido.
- party_id e party_name: CNPJ_ADMIN e ADMIN, papel administrador.
- cedente_id e cedente_share: CPF ou CNPJ e percentual dos 9 maiores
  cedentes de cada grupo (TAB_I2A12, com risco; TAB_I2B12, sem risco),
  pareados por grupo e posicao. So o cedente com CNPJ valido vira papel
  cedente, com o percentual da mesma posicao; o CPF nunca e guardado
  (decisao 3 de Fundos).
"""

from fundos.cvm_csv import BOOLEAN
from fundos.cvm_csv import NUMERIC
from fundos.cvm_csv import TEXT


KEY = "key"
NAME = "name"
SERIES_LABEL = "series_label"
SUBCLASS = "subclass"
CNPJ_TEXT = "cnpj_text"
PARTY_ID = "party_id"
PARTY_NAME = "party_name"
CEDENTE_ID = "cedente_id"
CEDENTE_SHARE = "cedente_share"

SUBJECT_TYPE_COLUMN = "TP_FUNDO_CLASSE"
SUBJECT_COLUMN = "CNPJ_FUNDO_CLASSE"
NAME_COLUMN = "DENOM_SOCIAL"
COMPETENCE_COLUMN = "DT_COMPTC"
SERIES_LABEL_COLUMN = "TAB_X_CLASSE_SERIE"
SUBCLASS_COLUMN = "ID_SUBCLASSE"

# TP_FUNDO_CLASSE: o assunto e a classe ou o fundo do cadastro.
CLASS_SUBJECT = "Classe"
FUND_SUBJECT = "Fundo"
SUBJECT_TYPES = (CLASS_SUBJECT, FUND_SUBJECT)

# So a DENOM_SOCIAL desta tabela e gravada; nas outras 17 ela e conferida.
NAME_TABLE = "tab_I"

ADMIN_ROLE = "administrador"
ADMIN_ID_COLUMN = "CNPJ_ADMIN"
ADMIN_NAME_COLUMN = "ADMIN"

CEDENTE_ROLE = "cedente"

# Grupos de cedentes da tab_I: (prefixo, rotulo do relatorio).
CEDENTE_GROUPS = (("TAB_I2A12", "com risco"), ("TAB_I2B12", "sem risco"))
CEDENTE_POSITIONS = tuple(range(1, 10))

LEADING = (SUBJECT_TYPE_COLUMN, SUBJECT_COLUMN, NAME_COLUMN, COMPETENCE_COLUMN)

_DAYS = ("30", "60", "90", "120", "150", "180", "360", "720", "1080")


def cedente_columns(prefix, position):
    """(coluna do identificador, coluna do percentual) do grupo e da posicao."""

    return (
        prefix + "_CPF_CNPJ_CEDENTE_" + str(position),
        prefix + "_PR_CEDENTE_" + str(position),
    )


def _cedentes(prefix):
    """CPF ou CNPJ e percentual dos 9 maiores cedentes, na ordem do arquivo."""

    return tuple(
        column
        for position in CEDENTE_POSITIONS
        for column in cedente_columns(prefix, position)
    )


def _deadlines(table):
    """Prazos, inadimplencia e antecipados das tabelas V e VI."""

    names = []

    for letter, total, item in (
        ("A", "VL_DIRCRED_PRAZO", "VL_PRAZO_VENC_"),
        ("B", "VL_DIRCRED_INAD", "VL_INAD_"),
        ("C", "VL_DIRCRED_ANTECIPADO", "VL_ANTECIPADO_"),
    ):
        names.append(table + "_" + letter + "_" + total)
        names.extend(
            table + "_" + letter + str(index) + "_" + item + days
            for index, days in enumerate(_DAYS, start=1)
        )
        names.append(table + "_" + letter + "10_" + item + "MAIOR_1080")

    return tuple(names)


def _trades():
    """Minimo, medio e maximo de compra e venda da tabela IX."""

    return tuple(
        "TAB_IX_" + group + "_" + side
        for group in ("A1", "A2", "B1", "B2", "C1", "C2", "D1", "D2", "E1", "E2", "F1", "F2")
        for side in (
            "1_1_COMPRA_MIN",
            "1_2_COMPRA_MEDIA",
            "1_3_COMPRA_MAX",
            "2_1_VENDA_MIN",
            "2_2_VENDA_MEDIA",
            "2_3_VENDA_MAX",
        )
    )


_RATINGS = ("AA", "A", "B", "C", "D", "E", "F", "G", "H")

_HOLDERS = (
    "PF", "PJ_NAO_FINANC", "BANCO", "CORRETORA_DISTRIB", "PJ_FINANC",
    "INVNR", "EAPC", "EFPC", "RPPS", "SEGUR", "CAPITALIZ", "COTA_FIDC",
    "FII", "OUTRO_FI", "CLUBE", "OUTRO",
)

CEDENTE_COLUMNS = _cedentes("TAB_I2A12") + _cedentes("TAB_I2B12")

HEADERS = {
    "tab_I": LEADING + (
        "CLASSE_UNICA", "CNPJ_ADMIN", "ADMIN", "CLASSE", "CNPJ_CLASSE",
        "CONDOM", "FUNDO_EXCLUSIVO", "COTST_INTERESSE",
        "PRAZO_CONVERSAO_COTA", "TP_PRAZO_CONVERSAO_COTA",
        "PRAZO_PAGTO_RESGATE", "TP_PRAZO_PAGTO_RESGATE",
        "TAB_I_VL_ATIVO", "TAB_I1_VL_DISP", "TAB_I2_VL_CARTEIRA",
        "TAB_I2A_VL_DIRCRED_RISCO", "TAB_I2A1_VL_CRED_VENC_AD",
        "TAB_I2A2_VL_CRED_VENC_INAD", "TAB_I2A21_VL_TOTAL_PARCELA_INAD",
        "TAB_I2A3_VL_CRED_INAD", "TAB_I2A4_VL_CRED_DIRCRED_PERFM",
        "TAB_I2A5_VL_CRED_VENCIDO_PENDENTE", "TAB_I2A6_VL_CRED_EMP_RECUP",
        "TAB_I2A7_VL_CRED_RECEITA_PUBLICA", "TAB_I2A8_VL_CRED_ACAO_JUDIC",
        "TAB_I2A9_VL_CRED_FATOR_RISCO", "TAB_I2A10_VL_CRED_DIVERSO",
        "TAB_I2A11_VL_REDUCAO_RECUP",
    ) + _cedentes("TAB_I2A12") + (
        "TAB_I2B_VL_DIRCRED_SEM_RISCO", "TAB_I2B1_VL_CRED_VENC_AD",
        "TAB_I2B2_VL_CRED_VENC_INAD", "TAB_I2B21_VL_TOTAL_PARCELA_INAD",
        "TAB_I2B3_VL_CRED_INAD", "TAB_I2B4_VL_CRED_DIRCRED_PERFM",
        "TAB_I2B5_VL_CRED_VENCIDO_PENDENTE", "TAB_I2B6_VL_CRED_EMP_RECUP",
        "TAB_I2B7_VL_CRED_RECEITA_PUBLICA", "TAB_I2B8_VL_CRED_ACAO_JUDIC",
        "TAB_I2B9_VL_CRED_FATOR_RISCO", "TAB_I2B10_VL_CRED_DIVERSO",
        "TAB_I2B11_VL_REDUCAO_RECUP",
    ) + _cedentes("TAB_I2B12") + (
        "TAB_I2C_VL_VLMOB", "TAB_I2C1_VL_DEBENTURE", "TAB_I2C2_VL_CRI",
        "TAB_I2C3_VL_NP_COMERC", "TAB_I2C4_VL_LETRA_FINANC",
        "TAB_I2C5_VL_COTA_FUNDO_ICVM555", "TAB_I2C5_VL_COTA_FIF",
        "TAB_I2C6_VL_OUTRO", "TAB_I2D_VL_TITPUB_FED", "TAB_I2E_VL_CDB",
        "TAB_I2F_VL_OPER_COMPROM", "TAB_I2G_VL_OUTRO_RF",
        "TAB_I2H_VL_COTA_FIDC", "TAB_I2I_VL_COTA_FIDC_NP",
        "TAB_I2J_VL_CONTRATO_FUTURO", "TAB_I2_DEBENTURE_CRI",
        "TAB_I2_COTA_FIDC", "TAB_I2_VL_OUTRO_ATIVO",
        "TAB_I3_VL_POSICAO_DERIV", "TAB_I3A_VL_MERCADO_TERMO",
        "TAB_I3B_VL_MERCADO_OPCAO", "TAB_I3C_VL_MERCADO_FUTURO",
        "TAB_I3D_VL_DIFER_SWAP", "TAB_I3E_VL_COBERTURA",
        "TAB_I3F_VL_DEPOSITO_MARGEM", "TAB_I4_VL_OUTRO_ATIVO",
        "TAB_I4A_VL_CPRAZO", "TAB_I4B_VL_LPRAZO",
    ),
    "tab_II": LEADING + (
        "TAB_II_VL_CARTEIRA", "TAB_II_A_VL_INDUST", "TAB_II_B_VL_IMOBIL",
        "TAB_II_C_VL_COMERC", "TAB_II_C1_VL_COMERC", "TAB_II_C2_VL_VAREJO",
        "TAB_II_C3_VL_ARREND", "TAB_II_D_VL_SERV", "TAB_II_D1_VL_SERV",
        "TAB_II_D2_VL_SERV_PUBLICO", "TAB_II_D3_VL_SERV_EDUC",
        "TAB_II_D4_VL_ENTRET", "TAB_II_E_VL_AGRONEG", "TAB_II_F_VL_FINANC",
        "TAB_II_F1_VL_CRED_PESSOA", "TAB_II_F2_VL_CRED_PESSOA_CONSIG",
        "TAB_II_F3_VL_CRED_CORP", "TAB_II_F4_VL_MIDMARKET",
        "TAB_II_F5_VL_VEICULO", "TAB_II_F6_VL_IMOBIL_EMPRESA",
        "TAB_II_F7_VL_IMOBIL_RESID", "TAB_II_F8_VL_OUTRO",
        "TAB_II_G_VL_CREDITO", "TAB_II_H_VL_FACTOR", "TAB_II_H1_VL_PESSOA",
        "TAB_II_H2_VL_CORP", "TAB_II_I_VL_SETOR_PUBLICO",
        "TAB_II_I1_VL_PRECAT", "TAB_II_I2_VL_TRIBUT",
        "TAB_II_I3_VL_ROYALTIES", "TAB_II_I4_VL_OUTRO",
        "TAB_II_J_VL_JUDICIAL", "TAB_II_K_VL_MARCA",
    ),
    "tab_III": LEADING + (
        "TAB_III_VL_PASSIVO", "TAB_III_A_VL_PAGAR", "TAB_III_A1_VL_CPRAZO",
        "TAB_III_A2_VL_LPRAZO", "TAB_III_B_VL_POSICAO_DERIV",
        "TAB_III_B1_VL_TERMO", "TAB_III_B2_VL_OPCAO", "TAB_III_B3_VL_FUTURO",
        "TAB_III_B4_VL_SWAP_PAGAR",
    ),
    "tab_IV": LEADING + ("TAB_IV_A_VL_PL", "TAB_IV_B_VL_PL_MEDIO"),
    "tab_V": LEADING + _deadlines("TAB_V"),
    "tab_VI": LEADING + _deadlines("TAB_VI"),
    "tab_VII": LEADING + (
        "TAB_VII_A1_1_QT_DIRCRED_RISCO", "TAB_VII_A1_2_VL_DIRCRED_RISCO",
        "TAB_VII_A2_1_QT_DIRCRED_SEM_RISCO", "TAB_VII_A2_2_VL_DIRCRED_SEM_RISCO",
        "TAB_VII_A3_1_QT_DIRCRED_VENC_AD", "TAB_VII_A3_2_VL_DIRCRED_VENC_AD",
        "TAB_VII_A4_1_QT_DIRCRED_VENC_INAD", "TAB_VII_A4_2_VL_DIRCRED_VENC_INAD",
        "TAB_VII_A5_1_QT_DIRCRED_INAD", "TAB_VII_A5_2_VL_DIRCRED_INAD",
        "TAB_VII_B1_1_QT_CEDENTE", "TAB_VII_B1_2_VL_CEDENTE",
        "TAB_VII_B1_3_VL_CONTAB_CEDENTE", "TAB_VII_B2_1_QT_PREST",
        "TAB_VII_B2_2_VL_PREST", "TAB_VII_B2_3_VL_CONTAB_PREST",
        "TAB_VII_B3_1_QT_TERCEIRO", "TAB_VII_B3_2_VL_TERCEIRO",
        "TAB_VII_B3_3_VL_CONTAB_TERCEIRO", "TAB_VII_C_1_QT_SUBST",
        "TAB_VII_C_2_VL_SUBST", "TAB_VII_C_3_VL_CONTAB_SUBST",
        "TAB_VII_D_1_QT_RECOMPRA", "TAB_VII_D_2_VL_RECOMPRA",
        "TAB_VII_D_3_VL_CONTAB_RECOMPRA",
    ),
    "tab_VIII": LEADING + ("SEQUENCIAL", "VALOR"),
    "tab_IX": LEADING + _trades(),
    "tab_X": LEADING
    + tuple("TAB_X_SCR_RISCO_DEVEDOR_" + rating for rating in _RATINGS)
    + tuple("TAB_X_SCR_RISCO_OPER_" + rating for rating in _RATINGS)
    + ("TAB_X_DEBITO_TRIBUT",),
    "tab_X_1": LEADING + (SERIES_LABEL_COLUMN, SUBCLASS_COLUMN, "TAB_X_NR_COTST"),
    "tab_X_1_1": LEADING
    + tuple("TAB_X_NR_COTST_SENIOR_" + holder for holder in _HOLDERS)
    + tuple("TAB_X_NR_COTST_SUBORD_" + holder for holder in _HOLDERS),
    "tab_X_2": LEADING + (SERIES_LABEL_COLUMN, "TAB_X_QT_COTA", "TAB_X_VL_COTA"),
    "tab_X_3": LEADING + (SERIES_LABEL_COLUMN, "TAB_X_VL_RENTAB_MES"),
    "tab_X_4": LEADING + (
        "TAB_X_TP_OPER", SERIES_LABEL_COLUMN, "TAB_X_VL_TOTAL", "TAB_X_QT_COTA",
    ),
    "tab_X_5": LEADING + tuple(
        "TAB_X_VL_LIQUIDEZ_" + days
        for days in ("0", "30", "60", "90", "180", "360", "MAIOR_360")
    ),
    "tab_X_6": LEADING + (
        SERIES_LABEL_COLUMN, "TAB_X_PR_DESEMP_ESPERADO", "TAB_X_PR_DESEMP_REAL",
    ),
    "tab_X_7": LEADING + ("TAB_X_VL_GARANTIA_DIRCRED", "TAB_X_PR_GARANTIA_DIRCRED"),
}

# Ordem de leitura e de gravacao: a tab_I primeiro (DENOM_SOCIAL e
# administradora); a tab_X_1 antes das outras de serie (ID_SUBCLASSE).
TABLES = tuple(HEADERS)

SERIES_TABLES = ("tab_X_1", "tab_X_2", "tab_X_3", "tab_X_4", "tab_X_6")

# Lidas e conferidas, mas nao carregadas: varias linhas para o mesmo assunto
# e campo (SEQUENCIAL na VIII; tipo de operacao na X_4). Sem decisao, viram
# conflito falso ou nome inventado. A X_4 (captacoes, resgates e amortizacoes
# por serie) fica indisponivel ate uma tarefa propria, com ADR.
NOT_LOADED = ("tab_VIII", "tab_X_4")

# Tipo das colunas que nao sao numericas; as demais sao numeric.
_KIND_EXCEPTIONS = {
    "tab_I": {
        "CLASSE_UNICA": BOOLEAN,
        "FUNDO_EXCLUSIVO": BOOLEAN,
        "COTST_INTERESSE": BOOLEAN,
        "CNPJ_ADMIN": PARTY_ID,
        "ADMIN": PARTY_NAME,
        "CLASSE": TEXT,
        "CNPJ_CLASSE": CNPJ_TEXT,
        "CONDOM": TEXT,
        "TP_PRAZO_CONVERSAO_COTA": TEXT,
        "TP_PRAZO_PAGTO_RESGATE": TEXT,
        **{
            column: kind
            for prefix, _ in CEDENTE_GROUPS
            for position in CEDENTE_POSITIONS
            for column, kind in zip(
                cedente_columns(prefix, position), (CEDENTE_ID, CEDENTE_SHARE)
            )
        },
    },
    "tab_X_1": {SERIES_LABEL_COLUMN: SERIES_LABEL, SUBCLASS_COLUMN: SUBCLASS},
    "tab_X_2": {SERIES_LABEL_COLUMN: SERIES_LABEL},
    "tab_X_3": {SERIES_LABEL_COLUMN: SERIES_LABEL},
    "tab_X_4": {"TAB_X_TP_OPER": TEXT, SERIES_LABEL_COLUMN: SERIES_LABEL},
    "tab_X_6": {SERIES_LABEL_COLUMN: SERIES_LABEL},
}

_LEADING_KINDS = {
    SUBJECT_TYPE_COLUMN: KEY,
    SUBJECT_COLUMN: KEY,
    NAME_COLUMN: NAME,
    COMPETENCE_COLUMN: KEY,
}

KINDS = {
    table: {
        column: _LEADING_KINDS.get(
            column,
            _KIND_EXCEPTIONS.get(table, {}).get(column, NUMERIC),
        )
        for column in header
    }
    for table, header in HEADERS.items()
}

# Tipo gravado em observations para cada tipo de coluna que vira observacao.
VALUE_TYPE = {
    TEXT: TEXT,
    NUMERIC: NUMERIC,
    BOOLEAN: BOOLEAN,
    NAME: TEXT,
    SERIES_LABEL: TEXT,
    SUBCLASS: TEXT,
    CNPJ_TEXT: TEXT,
}


def member_name(table, period):
    """inf_mensal_fidc_<tabela>_AAAAMM.csv"""

    return "inf_mensal_fidc_" + table + "_" + period + ".csv"


def field_name(table, column):
    """tabela.coluna da CVM, sem renomear (por exemplo tab_IV.TAB_IV_A_VL_PL)."""

    return table + "." + column
