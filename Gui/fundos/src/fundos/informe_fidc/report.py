"""Relatorio do informe de FIDC so com agregados.

Nunca imprime CNPJ, nome nem valor de campo: so contagens, nomes de arquivo,
de tabela e de coluna, o SHA-256 do arquivo, a competencia e os rotulos fixos
do codigo.
"""

from collections import Counter

from fundos.cvm_csv import CNPJ
from fundos.cvm_csv import CPF
from fundos.cvm_csv import IDENTIFIER_STATUSES
from fundos.cvm_csv import INVALID
from fundos.informe_fidc import columns as spec
from fundos.informe_fidc.loader import CLASS_SUBJECT
from fundos.informe_fidc.loader import FUND_SUBJECT
from fundos.informe_fidc.loader import REASONS
from fundos.informe_fidc.reader import OTHER_SUBJECT


SUBJECT_KEYS = spec.SUBJECT_TYPES + (OTHER_SUBJECT,)
VALUE_TYPES = ("text", "numeric", "boolean")
LOADED_TABLES = tuple(table for table in spec.TABLES if table not in spec.NOT_LOADED)


def _statuses(counts, prefix):
    return " / ".join(str(counts[prefix + (status,)]) for status in IDENTIFIER_STATUSES)


def _cedente_lines(counts):
    """Secao Cedentes da leitura: so contagens, por grupo."""

    lines = [
        "Cedentes ("
        + str(len(spec.CEDENTE_COLUMNS))
        + " colunas da tab_I, "
        + str(len(spec.CEDENTE_POSITIONS))
        + " posicoes por grupo; so CNPJ valido vira papel cedente, sem nome;"
        " CPF descartado junto com o percentual da posicao):"
    ]

    for prefix, label in spec.CEDENTE_GROUPS:
        lines.append(
            "  "
            + label
            + " ("
            + prefix
            + "): identificador CNPJ "
            + str(counts[("cedente_identificador", prefix, CNPJ)])
            + " (zeros restaurados "
            + str(counts[("cedente_zeros_restaurados", prefix)])
            + "), CPF descartado "
            + str(counts[("cedente_identificador", prefix, CPF)])
            + ", invalido "
            + str(counts[("cedente_identificador", prefix, INVALID)])
        )
        lines.append(
            "    percentual com identificador "
            + str(counts[("cedente_percentual", prefix, "com_identificador")])
            + ", sem identificador (so contado) "
            + str(counts[("cedente_percentual", prefix, "sem_identificador")])
            + "; identificador sem percentual "
            + str(counts[("cedente_sem_percentual", prefix)])
            + "; percentual gravado negativo "
            + str(counts[("cedente_percentual_negativo", prefix)])
            + ", acima de 100 "
            + str(counts[("cedente_percentual_acima_de_100", prefix)])
            + "; mesmo CNPJ repetido no grupo "
            + str(counts[("cedente_repetido_no_grupo", prefix)])
        )

    identifiers = sum(n for key, n in counts.items() if key[0] == "cedente_identificador")
    shares = sum(n for key, n in counts.items() if key[0] == "cedente_percentual")
    lines.append(
        "  mesmo CNPJ nos dois grupos do mesmo assunto: "
        + str(counts[("cedente_nos_dois_grupos",)])
        + "; assuntos com cedente de CNPJ valido: "
        + str(counts[("cedente_assuntos_com_gravavel",)])
    )
    lines.append(
        "  celulas preenchidas: "
        + str(counts[("cedentes_preenchidas",)])
        + " (identificadores "
        + str(identifiers)
        + " + percentuais "
        + str(shares)
        + ")"
    )

    return lines


def format_read_report(informe):
    """Linhas do relatorio da leitura (ZIP, tabelas, descartes, series)."""

    counts = informe.counts
    lines = [
        "ZIP: " + informe.zip.file_name + " (" + str(informe.zip.size_bytes) + " bytes)",
        "  sha256: " + informe.zip.sha256,
        "  data dos membros no ZIP: " + (", ".join(informe.zip.member_dates) or "nenhuma"),
        "Competencia (DT_COMPTC): " + informe.competence + " (AAAAMM " + informe.zip.period + ")",
        "Linhas lidas ("
        + str(len(informe.members))
        + " tabelas, "
        + str(sum(m.column_count for m in informe.members))
        + " campos, "
        + str(sum(m.line_count for m in informe.members))
        + " linhas):",
    ]

    for table in spec.TABLES:
        member = informe.member(table)
        line = (
            "  "
            + table
            + ": "
            + str(member.line_count)
            + " linha(s), "
            + str(member.column_count)
            + " coluna(s); "
            + ", ".join(
                key + " " + str(counts[("linhas_por_tipo", table, key)])
                for key in SUBJECT_KEYS
            )
        )

        if table in spec.NOT_LOADED:
            line += "; lida, nao carregada"

        lines.append(line)

    lines.append(
        "Assuntos na tab_I: "
        + ", ".join(key + " " + str(counts[("assuntos", key)]) for key in SUBJECT_KEYS)
        + "; CNPJ_FUNDO_CLASSE invalido em "
        + str(sum(n for key, n in counts.items() if key[0] == "cnpj_assunto_invalido"))
        + " linha(s)"
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

    statuses = " / ".join(IDENTIFIER_STATUSES)
    lines.append(
        "tab_I.CNPJ_CLASSE ("
        + statuses
        + "): "
        + _statuses(counts, ("cnpj_classe",))
        + "; so CNPJ valido e gravado"
    )
    lines.append(
        "Administradora tab_I.CNPJ_ADMIN ("
        + statuses
        + "): "
        + _statuses(counts, ("administradora",))
        + "; nomes descartados (sem CNPJ valido): "
        + str(counts[("nome_descartado", spec.field_name("tab_I", spec.ADMIN_NAME_COLUMN))])
    )
    lines.append(
        "DENOM_SOCIAL: so a da tab_I e gravada; assuntos com nome diferente"
        " (ou ausentes da tab_I) nas outras tabelas: "
        + str(counts[("denom_divergente",)])
    )
    lines.extend(_cedente_lines(counts))
    lines.append(
        "Series (assunto e rotulo normalizado distintos): "
        + ", ".join(table + " " + str(counts[("series", table)]) for table in spec.SERIES_TABLES)
        + "; rotulo vazio "
        + str(sum(counts[("rotulo_vazio", table)] for table in spec.SERIES_TABLES))
    )
    lines.append(
        "ID_SUBCLASSE (tab_X_1): "
        + str(counts[("id_subclasse", "linhas")])
        + " linha(s), "
        + str(counts[("id_subclasse", "distintos")])
        + " distintos; repetidos entre assuntos (nao viram chave): "
        + str(counts[("id_subclasse", "repetidos")])
        + " em "
        + str(counts[("id_subclasse", "linhas_repetidos")])
        + " linha(s)"
    )
    lines.append(
        "Tabelas lidas e nao carregadas: "
        + ", ".join(
            table + " (" + str(informe.member(table).line_count) + " linhas)"
            for table in spec.NOT_LOADED
        )
    )

    return lines


def _outcomes(counts, prefix):
    loaded = (
        CLASS_SUBJECT
        + " "
        + str(counts[prefix + (CLASS_SUBJECT,)])
        + ", "
        + FUND_SUBJECT
        + " "
        + str(counts[prefix + (FUND_SUBJECT,)])
    )
    out = "; ".join(reason + " " + str(counts[prefix + (reason,)]) for reason in REASONS)
    total_out = sum(counts[prefix + (reason,)] for reason in REASONS)

    return loaded + "; fora " + str(total_out) + " (" + out + ")"


def format_match_report(counts):
    """Linhas do casamento com o cadastro carregado, por tabela e por assunto."""

    lines = ["Casamento com o cadastro carregado (linhas por tabela):"]
    lines.extend(
        "  " + table + ": " + _outcomes(counts, ("casamento", table))
        for table in spec.TABLES
    )
    totals = Counter()

    for key, total in counts.items():
        if key[0] == "casamento":
            totals[("total", key[2])] += total

    lines.append("  total: " + _outcomes(totals, ("total",)))
    lines.append("Assuntos (TP_FUNDO_CLASSE e CNPJ): " + _outcomes(counts, ("assuntos",)))

    return lines


def format_candidates_report(counts):
    """Linhas dos candidatos a gravar (dry-run com banco)."""

    lines = ["Candidatos a gravar (competencia ainda nao carregada; todos novos):"]

    for table in LOADED_TABLES:
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
    lines.append("  series (assunto e rotulo): " + str(counts[("series_candidatas",)]))
    lines.append(
        "  party_observations: administrador "
        + str(counts[("papeis_candidatos", spec.ADMIN_ROLE)])
        + ", cedente "
        + str(counts[("papeis_candidatos", spec.CEDENTE_ROLE)])
        + " (com percentual "
        + str(counts[("percentuais_candidatos",)])
        + ")"
    )

    return lines


def format_load_report(result):
    """Linhas do relatorio da carga gravada."""

    counts = result.counts
    lines = ["Gravado (coleta " + str(result.run_id) + ", status " + result.status + "):"]

    for table in LOADED_TABLES:
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
        + "; ID_SUBCLASSE como chave "
        + str(counts[("id_subclasse", "chave")])
        + ", recusado pelo banco "
        + str(counts[("id_subclasse", "recusado")])
    )
    for role in (spec.ADMIN_ROLE, spec.CEDENTE_ROLE):
        lines.append(
            "  party_observations "
            + role
            + ": criados "
            + str(counts[("papeis", role, "criados")])
            + ", existentes "
            + str(counts[("papeis", role, "existentes")])
        )

    lines.append(
        "  party_observation_shares (percentual do cedente): criados "
        + str(counts[("percentuais", "criados")])
        + ", existentes "
        + str(counts[("percentuais", "existentes")])
    )
    lines.append(
        "  conflitos abertos: data_conflicts "
        + str(counts[("conflitos", "data_conflicts")])
        + ", party_conflicts "
        + str(counts[("conflitos", "party_conflicts")])
    )
    lines.append(
        "  manifesto: o ZIP e os 18 CSV em raw_records ("
        + ", ".join(spec.NOT_LOADED)
        + " como ignored)"
    )
    lines.append(
        "  varredura de CPF (texto inteiro com 11 digitos ou mascara): observations "
        + str(counts[("varredura_cpf", "observations")])
        + ", party_observations "
        + str(counts[("varredura_cpf", "party_observations")])
        + " (nome, CNPJ e percentual do cedente)"
    )

    return lines
