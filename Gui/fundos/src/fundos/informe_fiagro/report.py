"""Relatorio do informe de FIAGRO so com agregados.

Nunca imprime CNPJ, nome, ISIN nem valor de campo: so contagens, nomes de
arquivo e de coluna, o SHA-256 do arquivo, a competencia e os rotulos fixos
do codigo.
"""

from fundos.cvm_csv import IDENTIFIER_STATUSES
from fundos.informe_fiagro import columns as spec
from fundos.informe_fiagro.loader import LOADED
from fundos.informe_fiagro.loader import PARSER_VERSION
from fundos.informe_fiagro.loader import REASONS
from fundos.informe_fiagro.loader import SUBCLASS_REASONS
from fundos.informe_fiagro.reader import VERSION_EMPTY
from fundos.informe_fiagro.reader import VERSION_ONE
from fundos.informe_fiagro.reader import VERSION_OTHER


EXCLUDED_COLUMNS = tuple(
    column
    for column, kind in spec.CLASS_COLUMNS
    if kind == spec.EXCLUDED
)
VALUE_TYPES = ("text", "numeric", "date", "boolean")
ROLES = tuple(role for role, _, _ in spec.PARTIES)
TABLE_REASONS = {spec.CLASS_TABLE: REASONS, spec.SUBCLASS_TABLE: SUBCLASS_REASONS}


def _statuses(counts, prefix):
    return " / ".join(str(counts[prefix + (status,)]) for status in IDENTIFIER_STATUSES)


def format_read_report(informe):
    """Linhas do relatorio da leitura (ZIP, arquivos, chaves, papeis, subclasses)."""

    counts = informe.counts
    statuses = " / ".join(IDENTIFIER_STATUSES)
    lines = [
        "ZIP: " + informe.zip.file_name + " (" + str(informe.zip.size_bytes) + " bytes)",
        "  sha256: " + informe.zip.sha256,
        "  data dos membros no ZIP: " + (", ".join(informe.zip.member_dates) or "nenhuma"),
        "Competencia: AAAAMM "
        + informe.zip.period
        + "; Data_Referencia "
        + informe.reference
        + " (dia 1, nos 2 arquivos); gravada como "
        + informe.competence
        + " (ultimo dia do mes, como o DT_COMPTC do FIDC)",
        "Linhas lidas ("
        + str(len(informe.members))
        + " arquivos, "
        + str(sum(m.column_count for m in informe.members))
        + " campos, "
        + str(sum(m.line_count for m in informe.members))
        + " linhas):",
    ]

    for table in spec.TABLES:
        member = informe.member(table)
        lines.append(
            "  "
            + table
            + ": "
            + str(member.line_count)
            + " linha(s), "
            + str(member.column_count)
            + " coluna(s)"
        )

    lines.append(
        "CNPJ_Classe ("
        + statuses
        + "): "
        + "; ".join(
            table + " " + _statuses(counts, ("cnpj_classe", table))
            for table in spec.TABLES
        )
    )
    lines.append(
        "Chave CNPJ_Classe no arquivo de classe: "
        + str(counts[("chaves", "distintas")])
        + " distintos; repetidos "
        + str(counts[("chaves", "repetidas")])
        + " ("
        + str(counts[("chaves", "linhas_repetidas")])
        + " linhas; com Versao diferente "
        + str(counts[("chaves", "repetidas_com_versao_diferente")])
        + "): nenhuma linha nem subclasse de chave repetida e carregada"
    )
    lines.append(
        "Versao: igual a 1 em "
        + str(counts[("versao", VERSION_ONE)])
        + " linha(s), diferente de 1 em "
        + str(counts[("versao", VERSION_OTHER)])
        + ", vazia em "
        + str(counts[("versao", VERSION_EMPTY)])
        + "; Data_Entrega: "
        + str(counts[("data_entrega", "distintas")])
        + " data(s) distinta(s)"
    )
    lines.append(
        "Codigo_ISIN (nao e chave): preenchido em "
        + str(counts[("isin", "preenchido")])
        + " linha(s), vazio em "
        + str(counts[("isin", "vazio")])
        + "; distintos "
        + str(counts[("isin", "distintos")])
        + ", em mais de uma classe "
        + str(counts[("isin", "em_varias_classes")])
    )

    scientific = sorted(
        (key[1], total) for key, total in counts.items() if key[0] == "notacao_cientifica"
    )
    lines.append("Notacao cientifica convertida (exata, sem expoente), por coluna:")

    if scientific:
        lines.extend("  " + column + ": " + str(total) for column, total in scientific)
        lines.append("  total: " + str(sum(total for _, total in scientific)))
    else:
        lines.append("  nenhuma")

    for role, id_column, name_column in spec.PARTIES:
        id_field = spec.field_name(spec.CLASS_TABLE, id_column)
        lines.append(
            "Papel "
            + role
            + " "
            + id_field
            + " ("
            + statuses
            + "): "
            + _statuses(counts, ("identificador", id_field))
            + "; nomes descartados (sem CNPJ valido): "
            + str(counts[("nome_descartado", spec.field_name(spec.CLASS_TABLE, name_column))])
        )

    lines.append(
        "Subclasse: "
        + str(informe.member(spec.SUBCLASS_TABLE).line_count)
        + " linha(s); de chave repetida "
        + str(counts[("subclasse", "de_chave_repetida")])
        + ", sem linha no arquivo de classe "
        + str(counts[("subclasse", "sem_classe_no_arquivo")])
        + ", rotulo vazio "
        + str(counts[("rotulo_vazio", spec.SUBCLASS_TABLE)])
        + "; Nome_Classe diferente do arquivo de classe (conferido, nao gravado) "
        + str(counts[("subclasse", "nome_classe_divergente")])
    )
    lines.append(
        "  pares (CNPJ_Classe, rotulo normalizado) repetidos: "
        + str(counts[("subclasse", "pares_repetidos")])
        + " ("
        + str(counts[("subclasse", "linhas_de_pares_repetidos")])
        + " linhas), fora das chaves repetidas "
        + str(counts[("subclasse", "pares_repetidos_fora_das_chaves_repetidas")])
        + " ("
        + str(counts[("subclasse", "linhas_de_pares_repetidos_fora_das_chaves_repetidas")])
        + " linhas); nenhuma dessas linhas e carregada"
    )
    lines.append(
        "  rotulos distintos: "
        + str(counts[("rotulos", "distintos")])
        + " (normalizados: "
        + str(counts[("rotulos", "normalizados_distintos")])
        + ")"
    )
    lines.append(
        "Colunas exigidas no cabecalho e descartadas sem guardar (contato e"
        " Entidade_Administradora): "
        + ", ".join(EXCLUDED_COLUMNS)
    )

    return lines


def _outcomes(counts, prefix, reasons):
    out = "; ".join(reason + " " + str(counts[prefix + (reason,)]) for reason in reasons)
    total_out = sum(counts[prefix + (reason,)] for reason in reasons)

    return (
        "entram "
        + str(counts[prefix + (LOADED,)])
        + "; fora "
        + str(total_out)
        + " ("
        + out
        + ")"
    )


def format_match_report(counts):
    """Linhas do casamento com o cadastro carregado, por arquivo e por classe."""

    lines = ["Casamento com o cadastro carregado (linhas por arquivo):"]
    lines.extend(
        "  " + table + ": " + _outcomes(counts, ("casamento", table), TABLE_REASONS[table])
        for table in spec.TABLES
    )
    lines.append(
        "Classes (CNPJ_Classe distintos do arquivo de classe): "
        + _outcomes(counts, ("classes",), REASONS)
    )

    return lines


def format_candidates_report(counts):
    """Linhas dos candidatos a gravar (dry-run com banco)."""

    lines = ["Candidatos a gravar (competencia ainda nao carregada; todos novos):"]

    for table in spec.TABLES:
        lines.append(
            "  observations "
            + table
            + ": "
            + ", ".join(
                value_type + " " + str(counts[("candidatas", table, value_type)])
                for value_type in VALUE_TYPES
            )
        )

    total = sum(n for key, n in counts.items() if key[0] == "candidatas")
    lines.append(
        "  observations total: "
        + str(total)
        + " (das quais com valor zero: "
        + str(counts[("candidatas_zero",)])
        + ")"
    )
    lines.append("  series (classe e rotulo da subclasse): " + str(counts[("series_candidatas",)]))
    lines.append(
        "  party_observations: "
        + ", ".join(role + " " + str(counts[("papeis_candidatos", role)]) for role in ROLES)
    )

    return lines


def format_load_report(result):
    """Linhas do relatorio da carga gravada."""

    counts = result.counts
    lines = ["Gravado (coleta " + str(result.run_id) + ", status " + result.status + "):"]

    for table in spec.TABLES:
        created = sum(counts[("observacoes", table, t, "criadas")] for t in VALUE_TYPES)
        existing = sum(counts[("observacoes", table, t, "existentes")] for t in VALUE_TYPES)
        lines.append(
            "  observations "
            + table
            + ": criadas "
            + str(created)
            + ", existentes "
            + str(existing)
        )

    lines.append(
        "  observations total criadas: "
        + str(sum(n for key, n in counts.items() if key[0] == "observacoes" and key[3] == "criadas"))
    )
    lines.append(
        "  series: criadas "
        + str(counts[("series", "criadas")])
        + ", existentes "
        + str(counts[("series", "existentes")])
    )

    for role in ROLES:
        lines.append(
            "  party_observations "
            + role
            + ": criados "
            + str(counts[("papeis", role, "criados")])
            + ", existentes "
            + str(counts[("papeis", role, "existentes")])
        )

    lines.append(
        "  conflitos abertos: data_conflicts "
        + str(counts[("conflitos", "data_conflicts")])
        + ", party_conflicts "
        + str(counts[("conflitos", "party_conflicts")])
    )
    lines.append(
        "  manifesto: o ZIP e os 2 CSV em raw_records (" + PARSER_VERSION + ")"
    )
    lines.append(
        "  varredura de CPF (texto inteiro com 11 digitos ou mascara): observations "
        + str(counts[("varredura_cpf", "observations")])
        + ", party_observations "
        + str(counts[("varredura_cpf", "party_observations")])
        + " (nome e CNPJ)"
    )

    return lines
