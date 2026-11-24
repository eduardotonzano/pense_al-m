"""Cedentes gravados por bloco no informe de FIDC (FU11.2).

O informe traz, em cada bloco da tab_I, ate 9 posicoes de cedente, com o CPF
ou CNPJ e o percentual: bloco a (com aquisicao substancial dos riscos e
beneficios, TAB_I2A12_*) e bloco b (sem, TAB_I2B12_*). O modelo do
Suplemento G pede o cedente "quando representar mais de 10% do PL do fundo"
(docs/fundos-sonda-pdd-cedente.md, secao 3). A carga do informe grava em
party_observations so o cedente com CNPJ valido, sem nome, e o percentual em
party_observation_shares, como veio. O cedente com CPF NAO e gravado: o
informe pode ter cedente pessoa fisica que nao aparece aqui.

Por assunto (classe ou fundo), competencia e bloco:
- a lista e a dos cedentes GRAVADOS (com CNPJ), com a posicao e o percentual
  como informado. O CNPJ nao aparece em repr;
- bloco sem cedente gravado sai com estado e motivo sem_cedente_gravado,
  nunca zero nem "sem concentracao": nao se sabe se nao ha cedente acima do
  corte, se ele tem CPF ou se nao foi informado;
- a quantidade (stored_count) conta os CNPJs distintos gravados no bloco. E
  um minimo, nunca o total de cedentes do bloco;
- o maior percentual (largest_share) e o maior valor informado entre os
  gravados, sem conta nenhuma (nada e somado), com o qualificador do proprio
  valor, que pode ser acima_de_100. Nao e medida de concentracao;
- qualificadores do percentual, que nunca mudam o valor: acima_de_100, zero,
  ate_10 (acima de 0 e ate 10) e negativo. A base do percentual nao esta
  confirmada, e nenhuma conta usa o percentual (decisao de 24/11/2026);
- marcas do bloco: lista_cheia (posicao 9 ocupada: a lista do informe pode
  estar cortada), posicao_sem_cnpj_gravado (posicao abaixo da maior sem
  CNPJ gravado: vazia, CPF ou invalida no arquivo, sem distinguir),
  cnpj_repetido_no_bloco e posicao_com_mais_de_um_cnpj (mais de um CNPJ na
  mesma posicao da competencia, o que so acontece com reapresentacao; os
  dois sao listados e nenhum e escolhido);
- o cedente que tambem esta no outro bloco do mesmo assunto e marcado; os
  blocos nunca sao juntados.

Limitacao da carga (README do modulo de Fundos, "Papeis"): com
reapresentacao, o conjunto de cedentes de uma competencia e a soma dos ZIPs
carregados dela e pode incluir cedente que saiu. Dentro da competencia, por
posicao e CNPJ, vale a linha da fonte ativa de maior prioridade e, depois, a
coleta mais recente, como em reading.

Nada e gravado. Exige as migrations 002 e 003.
"""

import re
from dataclasses import dataclass
from dataclasses import field
from dataclasses import replace
from decimal import Decimal
from decimal import InvalidOperation

from fundos.database import normalize_iso_date
from fundos.indicators.reading import IndicatorDatabaseError
from fundos.indicators.reading import check_subjects
from fundos.indicators.reading import read_competence
from fundos.indicators.reading import read_snapshot
from fundos.indicators.reading import subject_filter
from fundos.indicators.values import BLOCK_A
from fundos.indicators.values import BLOCK_B
from fundos.indicators.values import BLOCKS
from fundos.indicators.values import CLASS_SUBJECT
from fundos.indicators.values import FUND_SUBJECT
from fundos.indicators.values import NO_DATA
from fundos.indicators.values import PRESENT
from fundos.indicators.values import REASON_MISSING
from fundos.indicators.values import REASON_UNEXPECTED_TYPE
from fundos.indicators.values import FieldValue
from fundos.indicators.values import Subject


NO_CEDENTE_STORED = "sem_cedente_gravado"

ABOVE_100 = "acima_de_100"
ZERO = "zero"
UP_TO_10 = "ate_10"
NEGATIVE = "negativo"

FULL_LIST = "lista_cheia"
MISSING_POSITION = "posicao_sem_cnpj_gravado"
REPEATED_CNPJ = "cnpj_repetido_no_bloco"
SEVERAL_CNPJ_IN_POSITION = "posicao_com_mais_de_um_cnpj"

LIST_SIZE = 9

GROUPS = {BLOCK_A: "TAB_I2A12", BLOCK_B: "TAB_I2B12"}

BLOCK_TOTALS = {
    BLOCK_A: "tab_I.TAB_I2A_VL_DIRCRED_RISCO",
    BLOCK_B: "tab_I.TAB_I2B_VL_DIRCRED_SEM_RISCO",
}

_IDENTIFIER = re.compile(r"tab_I\.(TAB_I2[AB]12)_CPF_CNPJ_CEDENTE_([1-9])")
_BLOCK_OF_GROUP = {group: block for block, group in GROUPS.items()}
_TABLES = ("party_observations", "party_observation_shares", "party_conflicts")


@dataclass(frozen=True)
class StoredCedente:
    """Um cedente gravado (com CNPJ) numa posicao do bloco.

    field_name e a coluna do identificador na CVM (com a posicao); share e o
    percentual como informado, com o campo de origem; qualifier marca a
    faixa do percentual sem mudar o valor.
    """

    block: str
    position: int
    field_name: str
    cnpj: str = field(repr=False)
    share: FieldValue
    qualifier: str | None
    party_observation_id: int
    source_code: str
    collected_at: str
    open_conflict: bool
    in_other_block: bool


@dataclass(frozen=True)
class StoredCount:
    """CNPJs distintos gravados no bloco: um minimo, nunca o total de cedentes."""

    state: str
    value: int | None
    reason: str | None = None


@dataclass(frozen=True)
class LargestShare:
    """Maior percentual informado entre os gravados, sem conta nenhuma."""

    state: str
    value: Decimal | None
    qualifier: str | None
    position: int | None
    field_name: str | None
    reason: str | None = None


@dataclass(frozen=True)
class CedenteBlock:
    """Cedentes gravados de um bloco (a ou b), com as marcas do bloco.

    state e presente ou sem_cedente_gravado. block_total e o total do bloco
    na tab_I (I.2.a ou I.2.b), so como contexto.
    """

    block: str
    state: str
    cedentes: tuple[StoredCedente, ...]
    stored_count: StoredCount
    largest_share: LargestShare
    flags: tuple[str, ...]
    missing_positions: tuple[int, ...]
    block_total: FieldValue


@dataclass(frozen=True)
class CedentesResult:
    """Cedentes gravados de um assunto numa competencia (blocos a e b)."""

    subject: Subject
    reference_date: str
    blocks: tuple[CedenteBlock, ...]

    def block(self, name):
        """O bloco a ou b."""

        return next(block for block in self.blocks if block.block == name)


def share_qualifier(value):
    """Faixa do percentual informado; None de acima de 10 ate 100."""

    if value is None:
        return None

    if value < 0:
        return NEGATIVE

    if value == 0:
        return ZERO

    if value <= 10:
        return UP_TO_10

    if value > 100:
        return ABOVE_100

    return None


def _check_migrations(connection):
    found = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
            " AND name IN (?, ?, ?)",
            _TABLES,
        )
    }

    if len(found) != len(_TABLES):
        raise IndicatorDatabaseError(
            "O banco nao tem as migrations 002 e 003 (cedentes e percentuais)."
        )


def _share(identifier, share_field_name, share_value, reference, source_code, collected_at):
    name = share_field_name or identifier.replace("_CPF_CNPJ_CEDENTE_", "_PR_CEDENTE_")

    if share_value is None:
        return FieldValue.missing(name, reference)

    try:
        value = Decimal(share_value)
    except InvalidOperation:
        return FieldValue(name, reference, NO_DATA, reason=REASON_UNEXPECTED_TYPE)

    return FieldValue(
        name,
        reference,
        PRESENT,
        value,
        source_code=source_code,
        collected_at=collected_at,
    )


def _read_rows(connection, reference, subjects):
    where, parameters = "", ()

    if subjects is not None:
        where, parameters = subject_filter(subjects, "p")

    rows = connection.execute(
        "SELECT p.id, p.fund_id, p.fund_class_id, p.field_name, p.party_cnpj,"
        " p.collected_at, src.code, src.priority, s.share_field_name,"
        " s.share_value, f.cnpj, c.cnpj"
        " FROM party_observations p"
        " JOIN sources src ON src.id = p.source_id"
        " LEFT JOIN party_observation_shares s ON s.party_observation_id = p.id"
        " LEFT JOIN funds f ON f.id = p.fund_id"
        " LEFT JOIN fund_classes c ON c.id = p.fund_class_id"
        " WHERE p.role = 'cedente' AND src.active = 1 AND p.reference_date = ?"
        + where,
        (reference,) + parameters,
    ).fetchall()
    conflicts = {
        (row[0], row[1], row[2], row[3])
        for row in connection.execute(
            "SELECT p.fund_id, p.fund_class_id, p.field_name, p.party_cnpj"
            " FROM party_conflicts pc JOIN party_observations p"
            " ON p.id = pc.party_observation_a_id OR p.id = pc.party_observation_b_id"
            " WHERE pc.status = 'open' AND pc.reference_date = ?"
            " AND p.role = 'cedente'",
            (reference,),
        )
    }

    return rows, conflicts


def _chosen_rows(rows, conflicts, reference):
    """{assunto: {bloco: [StoredCedente sem a marca do outro bloco]}}.

    Por assunto, posicao e CNPJ, fica a linha da fonte de maior prioridade
    e, depois, a coleta mais recente (e o maior id).
    """

    chosen = {}

    for row in rows:
        match = _IDENTIFIER.fullmatch(row[3])

        if match is None:
            continue

        if row[1] is not None:
            subject = Subject(FUND_SUBJECT, row[1], row[10])
        else:
            subject = Subject(CLASS_SUBJECT, row[2], row[11])

        key = (subject, row[3], row[4])
        rank = (row[7], row[5], row[0])

        if key not in chosen or rank > chosen[key][0]:
            chosen[key] = (rank, subject, match, row)

    found = {}

    for _, subject, match, row in chosen.values():
        share = _share(row[3], row[8], row[9], reference, row[6], row[5])
        block = _BLOCK_OF_GROUP[match.group(1)]
        found.setdefault(subject, {}).setdefault(block, []).append(
            StoredCedente(
                block=block,
                position=int(match.group(2)),
                field_name=row[3],
                cnpj=row[4],
                share=share,
                qualifier=share_qualifier(share.value),
                party_observation_id=row[0],
                source_code=row[6],
                collected_at=row[5],
                open_conflict=(row[1], row[2], row[3], row[4]) in conflicts,
                in_other_block=False,
            )
        )

    return found


def _empty_block(block, block_total):
    return CedenteBlock(
        block=block,
        state=NO_CEDENTE_STORED,
        cedentes=(),
        stored_count=StoredCount(NO_DATA, None, NO_CEDENTE_STORED),
        largest_share=LargestShare(NO_DATA, None, None, None, None, NO_CEDENTE_STORED),
        flags=(),
        missing_positions=(),
        block_total=block_total,
    )


def _block(block, cedentes, block_total):
    if not cedentes:
        return _empty_block(block, block_total)

    positions = {}

    for cedente in cedentes:
        positions.setdefault(cedente.position, set()).add(cedente.cnpj)

    missing = tuple(
        position for position in range(1, max(positions) + 1) if position not in positions
    )
    cnpjs = [cedente.cnpj for cedente in cedentes]
    flags = []

    if LIST_SIZE in positions:
        flags.append(FULL_LIST)

    if missing:
        flags.append(MISSING_POSITION)

    if len(cnpjs) != len(set(cnpjs)):
        flags.append(REPEATED_CNPJ)

    if any(len(found) > 1 for found in positions.values()):
        flags.append(SEVERAL_CNPJ_IN_POSITION)

    with_share = [c for c in cedentes if c.share.state == PRESENT]

    if with_share:
        top = max(with_share, key=lambda c: (c.share.value, -c.position))
        largest = LargestShare(
            PRESENT, top.share.value, top.qualifier, top.position, top.share.field_name
        )
    else:
        largest = LargestShare(NO_DATA, None, None, None, None, REASON_MISSING)

    return CedenteBlock(
        block=block,
        state=PRESENT,
        cedentes=cedentes,
        stored_count=StoredCount(PRESENT, len(set(cnpjs))),
        largest_share=largest,
        flags=tuple(flags),
        missing_positions=missing,
        block_total=block_total,
    )


def stored_cedentes(connection, reference_date, subjects=None):
    """Cedentes gravados por assunto e bloco, numa competencia.

    O universo e o dos assuntos com o total I.2.a ou I.2.b na competencia,
    mais os que tiverem cedente gravado nela. Devolve CedentesResult por
    assunto, em ordem.
    """

    reference = normalize_iso_date(reference_date, "Competencia")

    if subjects is not None:
        subjects = check_subjects(subjects)

        if not subjects:
            return ()

    with read_snapshot(connection):
        _check_migrations(connection)
        totals = read_competence(
            connection, reference, tuple(BLOCK_TOTALS.values()), subjects
        )
        rows, conflicts = _read_rows(connection, reference, subjects)

    by_subject = _chosen_rows(rows, conflicts, reference)
    results = []

    for subject in sorted(set(totals) | set(by_subject)):
        found = by_subject.get(subject, {})
        cnpjs = {block: {c.cnpj for c in found.get(block, ())} for block in BLOCKS}
        blocks = []

        for block in BLOCKS:
            other = BLOCK_B if block == BLOCK_A else BLOCK_A
            cedentes = tuple(
                replace(cedente, in_other_block=cedente.cnpj in cnpjs[other])
                for cedente in sorted(
                    found.get(block, ()),
                    key=lambda c: (c.position, c.party_observation_id),
                )
            )
            block_total = totals.get(subject, {}).get(
                BLOCK_TOTALS[block]
            ) or FieldValue.missing(BLOCK_TOTALS[block], reference)
            blocks.append(_block(block, cedentes, block_total))

        results.append(CedentesResult(subject, reference, tuple(blocks)))

    return tuple(results)
