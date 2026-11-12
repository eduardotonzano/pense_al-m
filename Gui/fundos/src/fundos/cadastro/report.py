"""Relatorio do cadastro so com agregados.

Nunca imprime CNPJ, nome nem valor de campo: so contagens, nomes de arquivo
e de coluna, o SHA-256 do arquivo e os rotulos fixos do codigo (FIDC,
FIAGRO, outros).
"""

from fundos.cadastro import columns as spec
from fundos.cadastro.reader import IDENTIFIER_STATUSES
from fundos.cadastro.reader import OUT_OF_SCOPE
from fundos.cadastro.selection import EXCLUSION_REASONS


SCOPE_KEYS = spec.SCOPE_LABELS + (OUT_OF_SCOPE,)
ROLES = ("administrador", "gestor", "auditor", "custodiante", "controlador")
TABLES = (spec.FUND_TABLE, spec.CLASS_TABLE)


def _per_scope(counts, prefix):
    """(arquivo inteiro, FIDC, FIAGRO) de uma contagem por escopo."""

    by_scope = {key: counts[prefix + (key,)] for key in SCOPE_KEYS}

    return (
        sum(by_scope.values()),
        by_scope["FIDC"],
        by_scope["FIAGRO"],
    )


def _scope_text(totals):
    whole, fidc, fiagro = totals

    return (
        "arquivo inteiro "
        + str(whole)
        + "; FIDC "
        + str(fidc)
        + "; FIAGRO "
        + str(fiagro)
    )


def _identifier_fields():
    for table in (spec.FUND_TABLE, spec.CLASS_TABLE):
        yield spec.field_name(table, spec.IDENTITY_COLUMN[table])

        for _, id_column, _ in spec.PARTIES[table]:
            yield spec.field_name(table, id_column)


def _name_fields():
    for table in (spec.FUND_TABLE, spec.CLASS_TABLE):
        for _, _, name_column in spec.PARTIES[table]:
            yield spec.field_name(table, name_column)


def format_read_report(cadastro):
    """Linhas do relatorio da leitura (ZIP, linhas, identificadores)."""

    counts = cadastro.counts
    lines = [
        "ZIP: "
        + cadastro.zip.file_name
        + " ("
        + str(cadastro.zip.size_bytes)
        + " bytes)",
        "  sha256: " + cadastro.zip.sha256,
        "  data dos membros no ZIP: "
        + (", ".join(cadastro.zip.member_dates) or "nenhuma"),
        "Linhas lidas:",
    ]

    for member in cadastro.members:
        line = (
            "  "
            + member.file_name
            + ": "
            + str(member.line_count)
            + " linha(s), "
            + str(member.column_count)
            + " coluna(s)"
        )

        if member.file_name == spec.SUBCLASS_TABLE + ".csv":
            line += ", so manifesto"

        lines.append(line)

    lines.append("Linhas por tipo:")

    for table in (spec.FUND_TABLE, spec.CLASS_TABLE):
        lines.append(
            "  "
            + spec.field_name(table, spec.TYPE_COLUMN[table])
            + ": "
            + ", ".join(
                key + " " + str(counts[("linhas_por_tipo", table, key)])
                for key in SCOPE_KEYS
            )
        )

    lines.append(
        "Identificadores (" + " / ".join(IDENTIFIER_STATUSES) + "):"
    )

    for field in _identifier_fields():
        lines.append("  " + field)

        for label, keys in (
            ("arquivo inteiro", SCOPE_KEYS),
            ("FIDC", ("FIDC",)),
            ("FIAGRO", ("FIAGRO",)),
        ):
            lines.append(
                "    "
                + label
                + ": "
                + " / ".join(
                    str(
                        sum(
                            counts[("identificador", field, status, key)]
                            for key in keys
                        )
                    )
                    for status in IDENTIFIER_STATUSES
                )
            )

    person_field = spec.field_name(spec.FUND_TABLE, spec.PERSON_TYPE_COLUMN)
    gestor_field = spec.field_name(
        spec.FUND_TABLE,
        next(
            id_column
            for role, id_column, _ in spec.PARTIES[spec.FUND_TABLE]
            if role == spec.PERSON_TYPE_ROLE
        ),
    )
    lines.append("Gestor pessoa fisica (" + person_field + " PF), linhas:")
    lines.append("  " + _scope_text(_per_scope(counts, ("pf", person_field))))
    lines.append(
        "  identificador em formato de CNPJ descartado por PF: "
        + _scope_text(_per_scope(counts, ("pf_cnpj", gestor_field)))
    )
    lines.append(
        "Nomes descartados (identificador nao e CNPJ valido, ou gestor PF):"
    )

    for field in _name_fields():
        lines.append(
            "  "
            + field
            + ": "
            + _scope_text(_per_scope(counts, ("nome_descartado", field)))
        )

    invalid = sorted(
        (key[1], total)
        for key, total in counts.items()
        if key[0] == "fora_do_formato" and total
    )
    lines.append("Valores fora do formato em linhas fora do escopo (descartados):")

    if invalid:
        lines.extend("  " + field + ": " + str(total) for field, total in invalid)
    else:
        lines.append("  nenhum")

    lines.append(
        "Colunas excluidas (nunca guardadas): "
        + ", ".join(
            spec.field_name(table, column)
            for table, columns in spec.COLUMNS.items()
            for column, kind in columns
            if kind == spec.EXCLUDED
        )
    )

    return lines


def _by_kind(counts, prefix):
    totals = [(kind, counts[prefix + (kind,)]) for kind in spec.VALUE_KINDS]

    return (
        ", ".join(kind + " " + str(total) for kind, total in totals)
        + " (total "
        + str(sum(total for _, total in totals))
        + ")"
    )


def _current(counts, table, label=None):
    """Vigentes que entram, de um tipo ou dos dois."""

    labels = spec.SCOPE_LABELS if label is None else (label,)

    return sum(
        counts[("vigentes", table, each, status)]
        for each in labels
        for status in ("cancelado", "nao cancelado")
    )


def format_selection_report(selection):
    """Linhas do relatorio da escolha do vigente e do que seria gravado."""

    counts = selection.counts
    lines = [
        "Registro vigente por CNPJ (prefere Situacao diferente de Cancelado;"
        " depois Data_Inicio_Situacao mais recente; empate nao entra):",
    ]

    for table in TABLES:
        lines.append("  " + table + ":")
        lines.append(
            "    registros FIDC ou FIAGRO: "
            + str(sum(counts[("registros", table, label)] for label in spec.SCOPE_LABELS))
            + " (com mais de uma linha: "
            + str(
                sum(
                    counts[("registros_com_varias_linhas", table, label)]
                    for label in spec.SCOPE_LABELS
                )
            )
            + ")"
        )
        lines.append(
            "    CNPJs com algum registro FIDC ou FIAGRO: "
            + str(counts[("cnpjs_candidatos", table)])
        )
        lines.append(
            "    vigentes que entram: "
            + "; ".join(
                label
                + " "
                + str(_current(counts, table, label))
                + " (cancelados "
                + str(counts[("vigentes", table, label, "cancelado")])
                + ")"
                for label in spec.SCOPE_LABELS
            )
        )
        lines.append(
            "    fora: "
            + "; ".join(
                reason + " " + str(counts[("fora", table, reason)])
                for reason in EXCLUSION_REASONS[table]
            )
        )

    lines.append(
        "  Tipo_Pessoa_Gestor com mais de um valor no registro (nao gravado): "
        + str(sum(counts[("tipo_pessoa_misturado", label)] for label in spec.SCOPE_LABELS))
    )
    lines.append(
        "  par Tipo_Fundo e Tipo_Classe divergente (carregado assim mesmo): "
        + str(counts[("par_divergente",)])
    )
    lines.append("Candidatos a gravar (num banco vazio, todos novos):")
    lines.append("  funds: " + str(_current(counts, spec.FUND_TABLE)))
    lines.append("  fund_classes: " + str(_current(counts, spec.CLASS_TABLE)))

    for table in TABLES:
        lines.append(
            "  observations " + table + ": " + _by_kind(counts, ("observacoes", table))
        )

    lines.append(
        "  party_observations: "
        + ", ".join(role + " " + str(counts[("papeis", role)]) for role in ROLES)
        + " (total "
        + str(sum(counts[("papeis", role)] for role in ROLES))
        + ")"
    )

    return lines


def _created_existing(counts, prefix, created, existing):
    return (
        created
        + " "
        + str(counts[prefix + (created,)])
        + ", "
        + existing
        + " "
        + str(counts[prefix + (existing,)])
    )


def format_load_report(result):
    """Linhas do relatorio da carga gravada."""

    counts = result.counts
    lines = [
        "Gravado (coleta " + str(result.run_id) + ", status " + result.status + "):",
        "  funds: " + _created_existing(counts, ("funds",), "criados", "existentes"),
        "  fund_classes: "
        + _created_existing(counts, ("fund_classes",), "criadas", "existentes")
        + ", bloqueadas por vinculo com outro fundo "
        + str(counts[("fund_classes", "bloqueadas")]),
    ]

    for table in TABLES:
        lines.append(
            "  observations "
            + table
            + ": "
            + "; ".join(
                kind
                + " "
                + _created_existing(counts, ("observacoes", table, kind), "criadas", "existentes")
                for kind in spec.VALUE_KINDS
            )
        )

    lines.append(
        "  party_observations: "
        + "; ".join(
            role + " " + _created_existing(counts, ("papeis", role), "criados", "existentes")
            for role in ROLES
        )
    )
    lines.append(
        "  conflitos abertos: data_conflicts "
        + str(counts[("conflitos", "data_conflicts")])
        + ", party_conflicts "
        + str(counts[("conflitos", "party_conflicts")])
    )
    lines.append("  manifesto: o ZIP e os 3 CSV em raw_records (subclasse como ignored)")
    lines.append(
        "  varredura de CPF (texto inteiro com 11 digitos ou mascara): observations "
        + str(counts[("varredura_cpf", "observations")])
        + ", party_observations "
        + str(counts[("varredura_cpf", "party_observations")])
    )

    return lines
