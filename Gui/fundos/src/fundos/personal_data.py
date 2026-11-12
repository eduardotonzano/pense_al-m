"""Guarda de dados pessoais do modulo de Fundos.

O CPF nunca e gravado, so CNPJ, e os campos de pessoa natural e de contato
nao sao carregados (docs/decisoes-em-aberto.md, decisao 3 de Fundos). A
guarda roda antes de qualquer SQL; o trigger trg_observations_personal_data
da migration 001 repete a regra de formato no banco.

O nome de gestor ou auditor pessoa fisica depende de outra coluna da mesma
linha e fica com o leitor do cadastro (fundos.cadastro.reader), que o
descarta antes de chegar aqui.

As mensagens citam o campo, nunca o valor.
"""

from fundos.cnpj import is_valid_cnpj
from fundos.cnpj import looks_like_cpf


FORBIDDEN_COLUMNS = frozenset(
    {
        "Diretor",
        "Email_Administrador",
        "Site",
        "Servico_Atendimento_Cotista",
        "Entidade_Administradora",
    }
)

_FORBIDDEN_LOWER = frozenset(column.lower() for column in FORBIDDEN_COLUMNS)


class PersonalDataError(ValueError):
    """O campo ou o valor nao pode ser gravado (dado pessoal)."""


def column_of(field_name):
    """Parte da coluna em 'tabela.coluna' (o nome inteiro se nao houver ponto)."""

    return field_name.partition(".")[2] or field_name


def is_identification_column(column):
    """Coluna com 'cpf' ou 'cnpj' no nome."""

    lowered = column.lower()
    return "cpf" in lowered or "cnpj" in lowered


def check_observation(field_name, value_type, value):
    """Recusa campo proibido e valor que nao seja CNPJ em campo de identificacao."""

    if not isinstance(field_name, str):
        raise PersonalDataError("O nome do campo deve ser texto.")

    column = column_of(field_name)

    if column.lower() in _FORBIDDEN_LOWER:
        raise PersonalDataError(
            "Campo de pessoa natural ou de contato nao e carregado: "
            + field_name
            + "."
        )

    if not is_identification_column(column):
        return

    if value_type == "text" and is_valid_cnpj(value):
        return

    if looks_like_cpf(value):
        reason = "valor com formato de CPF"
    else:
        reason = "valor que nao e CNPJ valido e normalizado"

    raise PersonalDataError(
        "Campo de identificacao so aceita CNPJ: "
        + field_name
        + " recebeu "
        + reason
        + ". Nada foi gravado."
    )


def find_cpf_columns(connection):
    """Lista 'objeto.coluna' de tabelas e views com 'cpf' no nome.

    Tambem lista o objeto cujo proprio nome tenha 'cpf'.
    """

    objects = [
        row[0]
        for row in connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type IN ('table', 'view')
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        )
    ]

    found = []

    for name in objects:
        if "cpf" in name.lower():
            found.append(name)

        quoted = '"' + name.replace('"', '""') + '"'

        for column in connection.execute("PRAGMA table_info(" + quoted + ")"):
            if "cpf" in str(column[1]).lower():
                found.append(name + "." + str(column[1]))

    return found
