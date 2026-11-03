"""Lista fechada das colunas do informe mensal de FIAGRO (2 arquivos, 133 + 6 campos).

Montada a partir do CABECALHO DO DADO de 09/2026, nao do dicionario: o
dicionario descreve so 13 dos 133 campos, nao segue a ordem das colunas e
trunca um nome (docs/fundos-descoberta.md, secao 9.2). A ordem e a do
cabecalho: se a CVM mudar uma coluna, a leitura falha em vez de ler torto.

Tipos:
- key: CNPJ_Classe e Data_Referencia identificam a classe e a competencia;
  nao viram observacao.
- name: Nome_Classe. No arquivo de classe vira observacao da classe, como
  vem (nunca identidade); no de subclasse so e conferido com o do arquivo de
  classe.
- text, date, numeric, boolean: viram observacao (arquivo.coluna da CVM).
- series_label: Nome_Subclasse; o rotulo original e observacao da serie e o
  rotulo normalizado e a chave da serie.
- party_id e party_name: CNPJ e nome do administrador e do gestor; viram
  papel so com CNPJ valido, nunca observacao.
- excluded: Email_Administrador, Site e Servico_Atendimento_Cotista (contato,
  decisao 3 de Fundos) e Entidade_Administradora (traz telefone em parte das
  linhas). Exigidas no cabecalho e descartadas sem serem guardadas nem
  contadas.
"""

from fundos.cvm_csv import BOOLEAN
from fundos.cvm_csv import DATE
from fundos.cvm_csv import NUMERIC
from fundos.cvm_csv import TEXT
from fundos.personal_data import FORBIDDEN_COLUMNS


KEY = "key"
NAME = "name"
SERIES_LABEL = "series_label"
PARTY_ID = "party_id"
PARTY_NAME = "party_name"
EXCLUDED = "excluded"

# Tabela = nome do CSV sem o _AAAAMM; vai na parte "tabela" do field_name.
CLASS_TABLE = "inf_mensal_fiagro"
SUBCLASS_TABLE = "inf_mensal_fiagro_subclasse"

SUBJECT_COLUMN = "CNPJ_Classe"
NAME_COLUMN = "Nome_Classe"
REFERENCE_COLUMN = "Data_Referencia"
VERSION_COLUMN = "Versao"
DELIVERY_COLUMN = "Data_Entrega"
ISIN_COLUMN = "Codigo_ISIN"
SERIES_LABEL_COLUMN = "Nome_Subclasse"

# (papel, coluna do identificador, coluna do nome).
PARTIES = (
    ("administrador", "CNPJ_Administrador", "Nome_Administrador"),
    ("gestor", "CNPJ_Gestor", "Nome_Gestor"),
)

CLASS_COLUMNS = (
    ("CNPJ_Classe", KEY),
    ("Nome_Classe", NAME),
    ("Data_Referencia", KEY),
    ("Data_Entrega", DATE),
    ("Versao", NUMERIC),
    ("Classe_Unica", BOOLEAN),
    ("CNPJ_Administrador", PARTY_ID),
    ("Nome_Administrador", PARTY_NAME),
    ("Data_Registro", DATE),
    ("Publico_Alvo", TEXT),
    ("Codigo_ISIN", TEXT),
    ("Cotistas_Vinculo_Familiar", BOOLEAN),
    ("Regra_Anexo", TEXT),
    ("Classificacao_Autorregulada", TEXT),
    ("Prazo_Duracao", TEXT),
    ("Encerramento_Exercicio_Social", TEXT),
    ("Mercado_Negociacao", TEXT),
    ("Entidade_Administradora", EXCLUDED),
    ("Email_Administrador", EXCLUDED),
    ("Servico_Atendimento_Cotista", EXCLUDED),
    ("Site", EXCLUDED),
    ("Nome_Gestor", PARTY_NAME),
    ("CNPJ_Gestor", PARTY_ID),
) + tuple(
    (column, NUMERIC)
    for column in (
        "Numero_Cotistas",
        "Numero_Cotistas_Pessoa_Natural",
        "Numero_Cotistas_Pessoa_Juridica_Nao_Financeira",
        "Numero_Cotistas_Pessoa_Juridica_Financeira",
        "Numero_Cotistas_Investidor_Nao_Residente",
        "Numero_Cotistas_Entidade_Previdencia_Complementar_Exceto_RPPS",
        "Numero_Cotistas_Entidade_RPPS",
        "Numero_Cotistas_Sociedade_Seguradora_Resseguradora",
        "Numero_Cotistas_Fundos_Investimento",
        "Numero_Cotistas_Distribuidos_Conta_Ordem",
        "Numero_Cotistas_Outros_Tipos",
        "Valor_Ativo",
        "Patrimonio_Liquido",
        "Cotas_Emitidas",
        "Valor_Patrimonial_Cotas",
        "Percentual_Despesas_Taxa_Administracao",
        "Percentual_Despesas_Taxa_Gestao",
        "Percentual_Despesas_Taxa_Distribuicao",
        "Rentabilidade_Efetiva_Mes",
        "Rentabilidade_Patrimonial_Mes",
        "Dividend_Yield_Mes",
        "Percentual_Amortizacao_Cotas_Mes",
        "Total_Necessidades_Liquidez",
        "Fundos_Renda_Fixa",
        "Titulos_Renda_Fixa",
        "Total_Investido",
        "Imoveis_Rurais",
        "Participacoes_Societarias",
        "Ativos_Financeiros_Lato_Sensu",
        "Ativos_Financeiros",
        "Ativos_Financeiros_Emissao_IF",
        "LCA",
        "LCI",
        "Outros_Ativos_Emissao_IF",
        "Outros_Ativos_Financeiros",
        "Valores_Mobiliarios",
        "Titulos_Participacoes_Societarias",
        "Acoes_Certificados_Deposito",
        "Outros_Titulos_Participacao",
        "Titulos_Divida_Corporativa",
        "Debentures",
        "Debentures_Conversiveis",
        "Debentures_Nao_Conversiveis",
        "Notas_Comerciais",
        "Notas_Comerciais_Curto_Prazo",
        "Notas_Comerciais_Longo_Prazo",
        "Outros_Titulos_Divida_Corporativa",
        "Valor_Titulos_Credito",
        "CPR",
        "CPR_Financeira",
        "CPR_Fisica",
        "CDCA",
        "CDA_WA",
        "Outros_Titulos_Credito_Agronegocio",
        "Titulos_Credito_Liquidacao_Financeira",
        "Devedor_Pessoa_Juridica_Liquidacao_Financeira",
        "Devedor_Pessoa_Natural_Liquidacao_Financeira",
        "Titulos_Credito_Liquidacao_Fisica",
        "Devedor_Pessoa_Juridica_Liquidacao_Fisica",
        "Devedor_Pessoa_Natural_Liquidacao_Fisica",
        "Demais_Direitos_Creditorios",
        "Direitos_Creditorios_Agronegocio",
        "Direitos_Creditorios_Imoveis_Rurais",
        "Titulos_Securitizacao",
        "CRA",
        "CRI",
        "Outros_Titulos_Securitizacao",
        "Cotas_Fundos_Investimento",
        "FIF",
        "FIDC",
        "FII",
        "FIP",
        "FIIM",
        "FIAGRO",
        "Creditos_Carbono_Agronegocio",
        "Creditos_Descarbonizacao",
        "Valores_Receber",
        "Total_Ativos_Prazo_Vencimento",
        "A_Vencer",
        "A_Vencer_Ate30Dias",
        "A_Vencer_31a60Dias",
        "A_Vencer_61a90Dias",
        "A_Vencer_91a120Dias",
        "A_Vencer_121a180Dias",
        "A_Vencer_181a360Dias",
        "A_Vencer_361a720Dias",
        "A_Vencer_721a1080Dias",
        "A_Vencer_Acima1080_Dias",
        "Vencidos",
        "Vencidos_Ate30Dias",
        "Vencidos_31a60Dias",
        "Vencidos_61a90Dias",
        "Vencidos_91a120Dias",
        "Vencidos_121a180Dias",
        "Vencidos_181a360Dias",
        "Vencidos_361a720Dias",
        "Vencidos_721a1080Dias",
        "Vencidos_Acima1080Dias",
        "Rendimentos_Distribuir",
        "Taxa_Administracao_Pagar",
        "Taxa_Gestao_Pagar",
        "Taxa_Performance_Pagar",
        "Taxa_Distribuicao_Pagar",
        "Obrigacoes_Aquisicao_Ativos",
        "Adiantamento_Venda_Ativos",
        "Adiantamento_Valores_Receber",
        "Instrumentos_Financeiros_Derivativos",
        "Provisoes_Contigencias",
        "Outros_Valores_Pagar",
        "Total_Passivo",
    )
)

SUBCLASS_COLUMNS = (
    ("CNPJ_Classe", KEY),
    ("Nome_Classe", NAME),
    ("Data_Referencia", KEY),
    ("Nome_Subclasse", SERIES_LABEL),
    ("Numero_Cotas", NUMERIC),
    ("Valor_Patrimonial_Cota", NUMERIC),
)

COLUMNS = {
    CLASS_TABLE: CLASS_COLUMNS,
    SUBCLASS_TABLE: SUBCLASS_COLUMNS,
}

# Ordem de leitura e de gravacao: o arquivo de classe primeiro (chaves
# repetidas e nomes, que a subclasse confere).
TABLES = tuple(COLUMNS)

HEADERS = {
    table: tuple(name for name, _ in columns)
    for table, columns in COLUMNS.items()
}

KINDS = {
    table: dict(columns)
    for table, columns in COLUMNS.items()
}

# Tipo gravado em observations para cada tipo de coluna que vira observacao.
VALUE_TYPE = {
    TEXT: TEXT,
    DATE: DATE,
    NUMERIC: NUMERIC,
    BOOLEAN: BOOLEAN,
    NAME: TEXT,
    SERIES_LABEL: TEXT,
}


def member_name(table, period):
    """<tabela>_AAAAMM.csv (inf_mensal_fiagro_AAAAMM.csv e o da subclasse)."""

    return table + "_" + period + ".csv"


def field_name(table, column):
    """tabela.coluna da CVM, sem renomear (por exemplo inf_mensal_fiagro.Patrimonio_Liquido)."""

    return table + "." + column


def _check_excluded():
    for table, columns in COLUMNS.items():
        for name, kind in columns:
            if (name in FORBIDDEN_COLUMNS) != (kind == EXCLUDED):
                raise RuntimeError(
                    "Coluna proibida fora da lista de excluidas (ou excluida sem ser"
                    " proibida): " + field_name(table, name) + "."
                )


_check_excluded()
