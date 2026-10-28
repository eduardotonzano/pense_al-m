"""Relatorio do cadastro so com agregados.

Nunca imprime CNPJ, nome nem valor de campo: so contagens, nomes de arquivo
e de coluna, o SHA-256 do arquivo e os rotulos fixos do codigo (FIDC,
FIAGRO, outros).
"""

from fundos.cadastro import columns as spec
from fundos.cadastro.reader import IDENTIFIER_STATUSES
from fundos.cadastro.reader import OUT_OF_SCOPE


SCOPE_KEYS = spec.SCOPE_LABELS + (OUT_OF_SCOPE,)


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
