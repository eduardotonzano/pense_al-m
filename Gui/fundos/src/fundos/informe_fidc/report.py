"""Relatorio do informe de FIDC so com agregados.

Nunca imprime CNPJ, nome nem valor de campo: so contagens, nomes de arquivo,
de tabela e de coluna, o SHA-256 do arquivo, a competencia e os rotulos fixos
do codigo.
"""

from fundos.cvm_csv import IDENTIFIER_STATUSES
from fundos.informe_fidc import columns as spec
from fundos.informe_fidc.reader import OTHER_SUBJECT


SUBJECT_KEYS = spec.SUBJECT_TYPES + (OTHER_SUBJECT,)


def _statuses(counts, prefix):
    return " / ".join(str(counts[prefix + (status,)]) for status in IDENTIFIER_STATUSES)


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
    lines.append(
        "Cedentes ("
        + str(len(spec.CEDENTE_COLUMNS))
        + " colunas da tab_I, nao lidas; FU4.3): celulas preenchidas "
        + str(counts[("cedentes_preenchidas",)])
    )
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
