"""Lista fechada das colunas do cadastro de fundos da CVM.

Tirada do dicionario (meta_registro_fundo_classe.zip) e do cabecalho real do
arquivo de 27/10/2026 (docs/fundos-descoberta.md, secoes 10.2 e 10.3). A
ordem e a do cabecalho: se a CVM mudar uma coluna, a leitura falha em vez de
ler torto.

Tipos:
- text, date, numeric, boolean: viram observacao (tabela.coluna da CVM).
- identity: CNPJ do assunto (fundo ou classe); vira a identidade, nao
  observacao.
- party_id e party_name: identificador e nome de um papel (gestor,
  administrador, custodiante, controlador, auditor). Viram papel, nunca
  observacao; o CPF e descartado na leitura.
- excluded: pessoa natural; o valor nunca e guardado (personal_data).

Identificadores internos da CVM (ID_Registro_*, Codigo_CVM) sao texto: sao
codigos, nao quantidades. Tributacao_Longo_Prazo e texto, porque traz S, N e
N/A.
"""

from fundos.personal_data import FORBIDDEN_COLUMNS


TEXT = "text"
DATE = "date"
NUMERIC = "numeric"
BOOLEAN = "boolean"
IDENTITY = "identity"
PARTY_ID = "party_id"
PARTY_NAME = "party_name"
EXCLUDED = "excluded"

VALUE_KINDS = (TEXT, DATE, NUMERIC, BOOLEAN)
TYPED_KINDS = (DATE, NUMERIC, BOOLEAN)

FUND_TABLE = "registro_fundo"
CLASS_TABLE = "registro_classe"
SUBCLASS_TABLE = "registro_subclasse"

FUND_COLUMNS = (
    ("ID_Registro_Fundo", TEXT),
    ("CNPJ_Fundo", IDENTITY),
    ("Codigo_CVM", TEXT),
    ("Data_Registro", DATE),
    ("Data_Constituicao", DATE),
    ("Tipo_Fundo", TEXT),
    ("Denominacao_Social", TEXT),
    ("Data_Cancelamento", DATE),
    ("Situacao", TEXT),
    ("Data_Inicio_Situacao", DATE),
    ("Data_Adaptacao_RCVM175", DATE),
    ("Data_Inicio_Exercicio_Social", DATE),
    ("Data_Fim_Exercicio_Social", DATE),
    ("Patrimonio_Liquido", NUMERIC),
    ("Data_Patrimonio_Liquido", DATE),
    ("Diretor", EXCLUDED),
    ("CNPJ_Administrador", PARTY_ID),
    ("Administrador", PARTY_NAME),
    ("Tipo_Pessoa_Gestor", TEXT),
    ("CPF_CNPJ_Gestor", PARTY_ID),
    ("Gestor", PARTY_NAME),
)

CLASS_COLUMNS = (
    ("ID_Registro_Fundo", TEXT),
    ("ID_Registro_Classe", TEXT),
    ("CNPJ_Classe", IDENTITY),
    ("Codigo_CVM", TEXT),
    ("Data_Registro", DATE),
    ("Data_Constituicao", DATE),
    ("Data_Inicio", DATE),
    ("Tipo_Classe", TEXT),
    ("Denominacao_Social", TEXT),
    ("Situacao", TEXT),
    ("Data_Inicio_Situacao", DATE),
    ("Classificacao", TEXT),
    ("Indicador_Desempenho", TEXT),
    ("Classe_Cotas", BOOLEAN),
    ("Classificacao_Anbima", TEXT),
    ("Tributacao_Longo_Prazo", TEXT),
    ("Entidade_Investimento", BOOLEAN),
    ("Permitido_Aplicacao_CemPorCento_Exterior", BOOLEAN),
    ("Classe_ESG", BOOLEAN),
    ("Forma_Condominio", TEXT),
    ("Exclusivo", BOOLEAN),
    ("Publico_Alvo", TEXT),
    ("Patrimonio_Liquido", NUMERIC),
    ("Data_Patrimonio_Liquido", DATE),
    ("CNPJ_Auditor", PARTY_ID),
    ("Auditor", PARTY_NAME),
    ("CNPJ_Custodiante", PARTY_ID),
    ("Custodiante", PARTY_NAME),
    ("CNPJ_Controlador", PARTY_ID),
    ("Controlador", PARTY_NAME),
)

# So o cabecalho e o numero de linhas: o arquivo de subclasse entra apenas
# no manifesto (FU4.1 ou FU6.2).
SUBCLASS_COLUMNS = (
    "ID_Registro_Classe",
    "ID_Subclasse",
    "Codigo_CVM",
    "Data_Constituicao",
    "Data_Inicio",
    "Denominacao_Social",
    "Situacao",
    "Data_Inicio_Situacao",
    "Forma_Condominio",
    "Exclusivo",
    "Publico_Alvo",
    "Previdenciario",
    "Exclusivo_INR",
    "Exclusivo_Previdencia_Complementar",
)

COLUMNS = {
    FUND_TABLE: FUND_COLUMNS,
    CLASS_TABLE: CLASS_COLUMNS,
}

KINDS = {
    table: dict(columns)
    for table, columns in COLUMNS.items()
}

HEADERS = {
    FUND_TABLE: tuple(name for name, _ in FUND_COLUMNS),
    CLASS_TABLE: tuple(name for name, _ in CLASS_COLUMNS),
    SUBCLASS_TABLE: SUBCLASS_COLUMNS,
}

# Membros do ZIP, na ordem do manifesto.
MEMBERS = (
    FUND_TABLE + ".csv",
    CLASS_TABLE + ".csv",
    SUBCLASS_TABLE + ".csv",
)

IDENTITY_COLUMN = {
    FUND_TABLE: "CNPJ_Fundo",
    CLASS_TABLE: "CNPJ_Classe",
}

REGISTRO_COLUMN = {
    FUND_TABLE: "ID_Registro_Fundo",
    CLASS_TABLE: "ID_Registro_Classe",
}

# (papel, coluna do identificador, coluna do nome). Uma linha por papel; o
# cadastro repete a linha do registro quando ha mais de um gestor,
# custodiante ou controlador.
PARTIES = {
    FUND_TABLE: (
        ("administrador", "CNPJ_Administrador", "Administrador"),
        ("gestor", "CPF_CNPJ_Gestor", "Gestor"),
    ),
    CLASS_TABLE: (
        ("auditor", "CNPJ_Auditor", "Auditor"),
        ("custodiante", "CNPJ_Custodiante", "Custodiante"),
        ("controlador", "CNPJ_Controlador", "Controlador"),
    ),
}

# Gestor pessoa fisica: o identificador e o nome sao descartados, mesmo que o
# identificador tenha formato de CNPJ. So a observacao do tipo fica.
PERSON_TYPE_COLUMN = "Tipo_Pessoa_Gestor"
PERSON_TYPE_ROLE = "gestor"
NATURAL_PERSON = "PF"

# Colunas que variam de uma linha para outra do mesmo registro (uma linha
# por papel). As demais tem de ser iguais em todas as linhas do registro.
ROW_VARYING = {
    FUND_TABLE: frozenset(
        {PERSON_TYPE_COLUMN}
        | {column for _, ident, name in PARTIES[FUND_TABLE] for column in (ident, name)}
    ),
    CLASS_TABLE: frozenset(
        column for _, ident, name in PARTIES[CLASS_TABLE] for column in (ident, name)
    ),
}

# Escopo: o par Tipo_Fundo e Tipo_Classe. Nunca pelo nome.
TYPE_COLUMN = {
    FUND_TABLE: "Tipo_Fundo",
    CLASS_TABLE: "Tipo_Classe",
}

SCOPE = {
    FUND_TABLE: {
        "FIDC": "FIDC",
        "FIAGRO": "FIAGRO",
    },
    CLASS_TABLE: {
        "Classes de Cotas de Fundos FIDC": "FIDC",
        "Classes de Cotas de Fundos FIAGRO": "FIAGRO",
    },
}

SCOPE_LABELS = ("FIDC", "FIAGRO")

# Colunas que o leitor guarda tambem nas linhas fora do escopo: as que a
# escolha do registro vigente precisa e a data de registro, que limita a
# competencia.
SELECTION_COLUMNS = {
    FUND_TABLE: frozenset(
        {"ID_Registro_Fundo", "Tipo_Fundo", "Situacao", "Data_Inicio_Situacao", "Data_Registro"}
    ),
    CLASS_TABLE: frozenset(
        {
            "ID_Registro_Fundo",
            "ID_Registro_Classe",
            "Tipo_Classe",
            "Situacao",
            "Data_Inicio_Situacao",
            "Data_Registro",
        }
    ),
}

YES_NO = {
    "S": True,
    "N": False,
}


def field_name(table, column):
    """tabela.coluna da CVM, sem renomear."""

    return table + "." + column


def _check_excluded():
    for table, columns in COLUMNS.items():
        for name, kind in columns:
            if name in FORBIDDEN_COLUMNS and kind != EXCLUDED:
                raise RuntimeError(
                    "Coluna proibida fora da lista de excluidas: "
                    + field_name(table, name)
                    + "."
                )


_check_excluded()
