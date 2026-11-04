"""Relatorio da leitura do CDA so com agregados.

Nunca imprime CNPJ, nome nem valor de campo: so contagens, nomes de arquivo
e de coluna, o SHA-256 do arquivo, a competencia, os meses de
DT_CONFID_APLIC e os rotulos de dominio da CVM (TP_APLIC, TP_FUNDO_CLASSE).
"""

from fundos.cda import columns as spec
from fundos.cda.reader import CONFIDENTIAL
from fundos.cda.reader import IDENTIFIED
from fundos.cda.reader import REFUSAL_REASONS


EMPTY_LABEL = "(vazio)"
# Rotulo de dominio com digito pode ser um identificador fora de lugar: so
# o total e impresso.
HIDDEN_LABEL = "(valor com digito, nao exibido)"


def _by_label(counts, prefix, *, show_digits=False):
    """'rotulo n' de cada contagem com o prefixo, do maior para o menor."""

    totals = {}

    for key, total in counts.items():
        if key[: len(prefix)] != prefix:
            continue

        label = key[len(prefix)] or EMPTY_LABEL

        if not show_digits and any(char.isdigit() for char in label):
            label = HIDDEN_LABEL

        totals[label] = totals.get(label, 0) + total

    found = sorted(totals.items(), key=lambda item: (-item[1], item[0]))

    return ", ".join(label + " " + str(total) for label, total in found) or "nenhum"


def format_read_report(cda):
    """Linhas do relatorio da leitura (ZIP, membros, cotas e confidenciais)."""

    counts = cda.counts
    lines = [
        "ZIP: " + cda.zip.file_name + " (" + str(cda.zip.size_bytes) + " bytes)",
        "  sha256: " + cda.zip.sha256,
        "  data dos membros no ZIP: " + (", ".join(cda.zip.member_dates) or "nenhuma"),
        "Competencia (DT_COMPTC das linhas de cotas): "
        + cda.competence
        + " (AAAAMM "
        + cda.zip.period
        + ")",
        "Membros (" + str(len(cda.members)) + "):",
    ]

    for table in spec.TABLES:
        member = cda.member(table)
        line = "  " + member.file_name + ": " + str(member.size_bytes) + " bytes"

        if table in spec.READ_TABLES:
            line += ", " + str(member.line_count) + " linha(s), " + str(member.column_count) + " coluna(s)"
        else:
            line += "; so manifesto, nao lido"

        lines.append(line)

    for table in spec.READ_TABLES:
        lines.append("TP_APLIC em " + table + ": " + _by_label(counts, ("tp_aplic", table)))

    lines.append(
        "Cotas identificadas (cda_fie, TP_APLIC " + spec.FUND_QUOTAS + "): "
        + str(counts[(IDENTIFIED, "linhas")])
        + " linha(s); tipo do detentor: "
        + _by_label(counts, (IDENTIFIED, "tipo_detentor"))
    )
    lines.append(
        "  CPF_CNPJ_EMISSOR aceito como CNPJ (PJ, 14 caracteres ou mascara, DV): "
        + str(counts[(IDENTIFIED, "identificador_aceito")])
        + "; recusado "
        + str(sum(counts[(IDENTIFIED, "identificador_recusado", r)] for r in REFUSAL_REASONS))
        + " ("
        + "; ".join(
            reason + " " + str(counts[(IDENTIFIED, "identificador_recusado", reason)])
            for reason in REFUSAL_REASONS
        )
        + ")"
    )
    lines.append(
        "  EMISSOR descartado (linha com identificador recusado): "
        + str(counts[(IDENTIFIED, "emissor_descartado")])
        + "; CNPJ_FUNDO_CLASSE invalido: "
        + str(counts[(IDENTIFIED, "detentor_invalido")])
        + "; sem VL_MERC_POS_FINAL: "
        + str(counts[(IDENTIFIED, "sem_valor_de_mercado")])
    )
    lines.append(
        "  posicoes: "
        + str(counts[(IDENTIFIED, "posicoes")])
        + " (sem QT_POS_FINAL "
        + str(counts[(IDENTIFIED, "sem_quantidade")])
        + ", sem EMISSOR "
        + str(counts[(IDENTIFIED, "sem_emissor")])
        + "); detentores distintos "
        + str(counts[(IDENTIFIED, "detentores")])
        + ", investidos distintos "
        + str(counts[(IDENTIFIED, "investidos")])
    )
    lines.append(
        "  chave (detentor, investido, DT_COMPTC) repetida: "
        + str(counts[(IDENTIFIED, "chave_repetida", "linhas")])
        + " linha(s) em "
        + str(counts[(IDENTIFIED, "chave_repetida", "chaves")])
        + " chave(s); com quantidade ou valor diferentes: "
        + str(counts[(IDENTIFIED, "chave_repetida", "valores_diferentes")])
    )
    lines.append(
        "Cotas confidenciais (cda_fie_CONFID): "
        + str(counts[(CONFIDENTIAL, "linhas")])
        + " linha(s); tipo do detentor: "
        + _by_label(counts, (CONFIDENTIAL, "tipo_detentor"))
    )
    lines.append(
        "  mes de DT_CONFID_APLIC: "
        + _by_label(counts, (CONFIDENTIAL, "mes_confidencial"), show_digits=True)
        + "; sem DT_CONFID_APLIC "
        + str(counts[(CONFIDENTIAL, "sem_data_confidencial")])
        + "; CNPJ_FUNDO_CLASSE invalido "
        + str(counts[(CONFIDENTIAL, "detentor_invalido")])
        + "; sem VL_MERC_POS_FINAL "
        + str(counts[(CONFIDENTIAL, "sem_valor_de_mercado")])
    )
    lines.append(
        "  posicoes: "
        + str(counts[(CONFIDENTIAL, "posicoes")])
        + "; detentores distintos "
        + str(counts[(CONFIDENTIAL, "detentores")])
        + " (com mais de uma linha "
        + str(counts[(CONFIDENTIAL, "detentor_repetido")])
        + ")"
    )
    lines.append(
        "Detentores com cotas identificadas e confidenciais ao mesmo tempo: "
        + str(counts[("detentores_nas_duas",)])
    )

    return lines
