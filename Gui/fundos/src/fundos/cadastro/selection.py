"""Filtro de FIDC e FIAGRO e escolha do registro vigente, sem banco.

Registro = ID_Registro_Fundo (ou ID_Registro_Classe). O cadastro repete a
linha do registro por gestor, custodiante ou controlador: as linhas do mesmo
ID viram um registro com o conjunto de papeis. Fora das colunas de papel,
todas as linhas do registro tem de ser iguais; se nao forem, o registro e
inconsistente e o CNPJ nao entra.

Vigente, por CNPJ, entre todos os registros do CNPJ (de qualquer tipo):
prefere Situacao diferente de Cancelado; depois, o Data_Inicio_Situacao mais
recente. Empate que sobrar nao entra. Se o vigente nao for FIDC ou FIAGRO,
o CNPJ nao entra. A classe so entra se o vigente dela for FIDC ou FIAGRO e o
registro de fundo dela for o vigente de um fundo que entrou. O escopo vem
do par Tipo_Fundo e Tipo_Classe, nunca do nome.
"""

from collections import Counter
from collections import defaultdict
from dataclasses import dataclass
from types import MappingProxyType

from fundos.cadastro import columns as spec
from fundos.cadastro.reader import OUT_OF_SCOPE


CANCELLED = "Cancelado"
SITUATION = "Situacao"
SITUATION_DATE = "Data_Inicio_Situacao"
FUND_LINK = "ID_Registro_Fundo"

# Motivos para um CNPJ (ou registro) com algum registro FIDC ou FIAGRO nao
# entrar.
OTHER_TYPE = "vigente de outro tipo"
TIE = "empate"
INVALID_DATE = "data invalida"
INCONSISTENT = "registro inconsistente"
INVALID_CNPJ = "CNPJ invalido"
FUND_NOT_LOADED = "fundo fora da carga"

EXCLUSION_REASONS = {
    spec.FUND_TABLE: (OTHER_TYPE, TIE, INVALID_DATE, INCONSISTENT, INVALID_CNPJ),
    spec.CLASS_TABLE: (
        OTHER_TYPE,
        TIE,
        INVALID_DATE,
        INCONSISTENT,
        INVALID_CNPJ,
        FUND_NOT_LOADED,
    ),
}


@dataclass(frozen=True)
class Registro:
    """As linhas de um ID de registro, juntas."""

    table: str
    registro_id: str
    cnpj: str | None
    scope: str | None
    values: MappingProxyType
    parties: tuple
    invalid_columns: frozenset[str]
    consistent: bool
    mixed_person_type: bool
    line_count: int


@dataclass(frozen=True)
class SelectedRegistro:
    """Registro vigente que entra na carga."""

    table: str
    registro_id: str
    cnpj: str
    scope: str
    cancelled: bool
    values: MappingProxyType
    parties: tuple
    fund_registro_id: str | None


@dataclass(frozen=True)
class Selection:
    """Fundos e classes que entram, e as contagens do que ficou fora."""

    funds: tuple[SelectedRegistro, ...]
    classes: tuple[SelectedRegistro, ...]
    counts: Counter


def _fixed_part(row, varying):
    return (
        {column: value for column, value in row.values.items() if column not in varying},
        row.cnpj,
        row.scope,
        row.invalid_columns - varying,
    )


def merge_rows(table, registro_id, rows):
    """Junta as linhas do mesmo registro; os papeis viram um conjunto."""

    varying = spec.ROW_VARYING[table]
    first = _fixed_part(rows[0], varying)
    values = dict(first[0])
    person_types = {
        row.values[spec.PERSON_TYPE_COLUMN]
        for row in rows
        if spec.PERSON_TYPE_COLUMN in row.values
    }

    if len(person_types) == 1:
        values[spec.PERSON_TYPE_COLUMN] = person_types.pop()

    parties = sorted(
        {party for row in rows for party in row.parties},
        key=lambda party: (party.role, party.field_name, party.cnpj, party.name or ""),
    )

    return Registro(
        table=table,
        registro_id=registro_id,
        cnpj=rows[0].cnpj,
        scope=rows[0].scope,
        values=MappingProxyType(values),
        parties=tuple(parties),
        invalid_columns=frozenset().union(*(row.invalid_columns for row in rows)),
        consistent=all(_fixed_part(row, varying) == first for row in rows[1:]),
        mixed_person_type=len(person_types) > 1,
        line_count=len(rows),
    )


def group_registros(table, rows, counts):
    """Agrupa as linhas por ID de registro, na ordem do arquivo."""

    by_id = defaultdict(list)

    for row in rows:
        registro_id = row.values.get(spec.REGISTRO_COLUMN[table])

        if registro_id is None:
            counts[("sem_id", table, row.scope or OUT_OF_SCOPE)] += 1
            continue

        by_id[registro_id].append(row)

    registros = [
        merge_rows(table, registro_id, group)
        for registro_id, group in by_id.items()
    ]

    for registro in registros:
        scope_key = registro.scope or OUT_OF_SCOPE
        counts[("registros", table, scope_key)] += 1

        if registro.line_count > 1:
            counts[("registros_com_varias_linhas", table, scope_key)] += 1

    return registros


def _rank(registro):
    return (
        registro.values.get(SITUATION) != CANCELLED,
        registro.values.get(SITUATION_DATE) or "",
    )


def choose_current(table, registros, counts):
    """Registro vigente de cada CNPJ que tem algum registro no escopo."""

    by_cnpj = defaultdict(list)

    for registro in registros:
        if registro.cnpj is None:
            if registro.scope is not None:
                counts[("fora", table, INVALID_CNPJ)] += 1

            continue

        by_cnpj[registro.cnpj].append(registro)

    chosen = []

    for group in by_cnpj.values():
        if not any(registro.scope is not None for registro in group):
            continue

        counts[("cnpjs_candidatos", table)] += 1

        if not all(registro.consistent for registro in group):
            counts[("fora", table, INCONSISTENT)] += 1
            continue

        if any(SITUATION_DATE in registro.invalid_columns for registro in group):
            counts[("fora", table, INVALID_DATE)] += 1
            continue

        best = max(_rank(registro) for registro in group)
        top = [registro for registro in group if _rank(registro) == best]

        if len(top) > 1:
            counts[("fora", table, TIE)] += 1
            continue

        if top[0].scope is None:
            counts[("fora", table, OTHER_TYPE)] += 1
            continue

        chosen.append(top[0])

    return chosen


def _selected(registro, fund_registro_id=None):
    return SelectedRegistro(
        table=registro.table,
        registro_id=registro.registro_id,
        cnpj=registro.cnpj,
        scope=registro.scope,
        cancelled=registro.values.get(SITUATION) == CANCELLED,
        values=registro.values,
        parties=registro.parties,
        fund_registro_id=fund_registro_id,
    )


def _count_selected(selected, counts):
    status = "cancelado" if selected.cancelled else "nao cancelado"
    counts[("vigentes", selected.table, selected.scope, status)] += 1

    for column in selected.values:
        counts[("observacoes", selected.table, spec.KINDS[selected.table][column])] += 1

    for party in selected.parties:
        counts[("papeis", party.role)] += 1


def select_fidc_fiagro(cadastro):
    """Fundos e classes FIDC e FIAGRO vigentes do cadastro lido."""

    counts = Counter()
    fund_registros = group_registros(spec.FUND_TABLE, cadastro.fund_rows, counts)
    funds = []

    for registro in choose_current(spec.FUND_TABLE, fund_registros, counts):
        if registro.mixed_person_type:
            counts[("tipo_pessoa_misturado", registro.scope)] += 1

        funds.append(_selected(registro))

    loaded_funds = {fund.registro_id: fund for fund in funds}
    class_registros = group_registros(spec.CLASS_TABLE, cadastro.class_rows, counts)
    classes = []

    for registro in choose_current(spec.CLASS_TABLE, class_registros, counts):
        fund_registro_id = registro.values.get(FUND_LINK)
        fund = loaded_funds.get(fund_registro_id)

        if fund is None:
            counts[("fora", spec.CLASS_TABLE, FUND_NOT_LOADED)] += 1
            continue

        if fund.scope != registro.scope:
            counts[("par_divergente",)] += 1

        classes.append(_selected(registro, fund_registro_id))

    for selected in funds + classes:
        _count_selected(selected, counts)

    return Selection(funds=tuple(funds), classes=tuple(classes), counts=counts)
