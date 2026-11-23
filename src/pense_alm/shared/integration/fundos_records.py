"""Records do cadastro do banco de Fundos lido pela camada (FU7.2).

O leitor (fundos_reader) entrega os valores brutos do banco de Fundos, sem
regra de negocio alem do agrupamento por CNPJ do ADR-013 (D6) e do filtro
das linhas do cadastro (F-05). Os motivos (sem nome, nome divergente, tipo
fora do mapa etc.) e os mapas de tipo e de situacao ficam no adaptador.

Cada campo de valor guarda todos os valores distintos da competencia, em
ordem, para que o leitor nunca escolha entre dois valores (conflito aberto
no banco de Fundos). O CNPJ nao e normalizado aqui: o servico normaliza e
conta o que for recusado.

Os campos com CNPJ, nome ou a lista de assuntos ficam fora do repr, para
que nenhuma impressao de objeto mostre esses dados.

Os records Cda* sao o CDA lido para a fase 4 (INVESTS_IN, PR C): as
competencias com posicao, os meses com coleta e sem posicao e os detentores
no L_H de cada um, so com CNPJ, ids e datas, nunca nome nem valor.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum


PARTY_ROLES = ("administrador", "gestor", "custodiante")
CLASS_ONLY_ROLES = ("custodiante",)
SOURCE_TABLES = ("funds", "fund_classes")


class CadastroIncompleteReason(StrEnum):
    """Por que a leitura nao e completa: a primeira checagem que falha.

    A ordem e a dos valores: status da coleta, fonte, membro ausente,
    membro nao processado e line_count nulo (registro_fundo.csv e
    registro_classe.csv). Sem comparacao com o manifesto.
    """

    STATUS_NAO_SUCCESS = "status_nao_success"
    FONTE_DIFERENTE = "fonte_diferente"
    MEMBRO_AUSENTE = "membro_ausente"
    MEMBRO_NAO_PROCESSADO = "membro_nao_processado"
    LINE_COUNT_NULO = "line_count_nulo"


def _require_positive_int(value, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} deve ser inteiro.")

    if value < 1:
        raise ValueError(f"{name} deve ser positivo.")


def _require_count(value, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} deve ser inteiro.")

    if value < 0:
        raise ValueError(f"{name} nao pode ser negativo.")


def _require_text(value, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} deve ser texto.")

    if not value.strip():
        raise ValueError(f"{name} nao pode ser vazio.")


def _distinct_texts(values, name: str) -> tuple[str, ...]:
    if isinstance(values, str) or not isinstance(values, (tuple, list)):
        raise TypeError(f"{name} deve ser uma tupla de textos.")

    values = tuple(values)

    for value in values:
        _require_text(value, name)

    if len(set(values)) != len(values):
        raise ValueError(f"{name} nao pode repetir valores.")

    return values


@dataclass(frozen=True, slots=True)
class FundosPartyLink:
    """Uma linha de papel do cadastro, ja filtrada pelo leitor (F-05)."""

    role: str
    cnpj: str = field(repr=False)
    name: str | None = field(repr=False)
    party_observation_id: int

    def __post_init__(self) -> None:
        if self.role not in PARTY_ROLES:
            raise ValueError("role deve ser administrador, gestor ou custodiante.")

        _require_text(self.cnpj, "cnpj")

        if self.name is not None:
            _require_text(self.name, "name")

        _require_positive_int(self.party_observation_id, "party_observation_id")


@dataclass(frozen=True, slots=True)
class FundosSubjectRecord:
    """Um grupo do D6: um CNPJ do cadastro, com os valores brutos em R.

    source_table e source_id apontam a linha que decide: o fundo, ou a
    classe quando o CNPJ so existe como classe. names, situacoes e
    tipos_pessoa_gestor sao do lado que decide; tipos_classe vem da classe
    de mesmo CNPJ (ou da propria classe, quando ela e o grupo).
    """

    cnpj: str = field(repr=False)
    source_table: str
    source_id: int
    names: tuple[str, ...] = field(repr=False)
    situacoes: tuple[str, ...]
    tipos_fundo: tuple[str, ...]
    tipos_classe: tuple[str, ...]
    tipos_pessoa_gestor: tuple[str, ...]
    parties: tuple[FundosPartyLink, ...] = field(repr=False)

    def __post_init__(self) -> None:
        _require_text(self.cnpj, "cnpj")

        if self.source_table not in SOURCE_TABLES:
            raise ValueError("source_table deve ser funds ou fund_classes.")

        _require_positive_int(self.source_id, "source_id")

        for name in (
            "names",
            "situacoes",
            "tipos_fundo",
            "tipos_classe",
            "tipos_pessoa_gestor",
        ):
            object.__setattr__(
                self,
                name,
                _distinct_texts(getattr(self, name), name),
            )

        if isinstance(self.parties, str) or not isinstance(
            self.parties, (tuple, list)
        ):
            raise TypeError("parties deve ser uma tupla de FundosPartyLink.")

        parties = tuple(self.parties)

        if any(not isinstance(party, FundosPartyLink) for party in parties):
            raise TypeError("parties deve ser uma tupla de FundosPartyLink.")

        if self.source_table == "fund_classes":
            if self.tipos_fundo or self.tipos_pessoa_gestor:
                raise ValueError(
                    "Classe que so existe como classe nao tem campos de fundo."
                )

            if any(party.role not in CLASS_ONLY_ROLES for party in parties):
                raise ValueError(
                    "Classe que so existe como classe so tem custodiante."
                )

        object.__setattr__(self, "parties", parties)


@dataclass(frozen=True, slots=True)
class CadastroSnapshot:
    """O retrato do cadastro na competencia R, com as contagens do D6.

    funds_read e classes_read contam as linhas com alguma observacao
    registro_fundo.* ou registro_classe.* em R. As classes lidas se dividem
    em: mesmo CNPJ do proprio fundo, CNPJ de outro fundo, CNPJ que so existe
    como classe e CNPJ de fundo sem dado em R (vale o lado do fundo, entao
    essa classe nao abre grupo).

    complete e verdadeiro se e so se incomplete_reason e None.
    """

    reference_date: date
    collection_run_id: int
    started_at: datetime
    complete: bool
    funds_in_table: int
    classes_in_table: int
    funds_read: int
    classes_read: int
    classes_same_cnpj: int
    classes_other_fund_cnpj: int
    classes_only_class: int
    classes_of_fund_without_data: int
    subjects: tuple[FundosSubjectRecord, ...] = field(repr=False)
    incomplete_reason: CadastroIncompleteReason | None = None

    def __post_init__(self) -> None:
        if isinstance(self.reference_date, datetime) or not isinstance(
            self.reference_date, date
        ):
            raise TypeError("reference_date deve ser data, sem hora.")

        _require_positive_int(self.collection_run_id, "collection_run_id")

        if not isinstance(self.started_at, datetime):
            raise TypeError("started_at deve ser datetime.")

        if self.started_at.utcoffset() is None:
            raise ValueError("started_at deve possuir timezone.")

        if not isinstance(self.complete, bool):
            raise TypeError("complete deve ser booleano.")

        if self.incomplete_reason is not None and not isinstance(
            self.incomplete_reason, CadastroIncompleteReason
        ):
            raise TypeError("incomplete_reason deve ser CadastroIncompleteReason.")

        if self.complete != (self.incomplete_reason is None):
            raise ValueError(
                "A leitura e completa se e so se nao ha motivo de incompleta."
            )

        for name in (
            "funds_in_table",
            "classes_in_table",
            "funds_read",
            "classes_read",
            "classes_same_cnpj",
            "classes_other_fund_cnpj",
            "classes_only_class",
            "classes_of_fund_without_data",
        ):
            _require_count(getattr(self, name), name)

        if self.funds_read > self.funds_in_table:
            raise ValueError("funds_read nao pode passar de funds_in_table.")

        if self.classes_read > self.classes_in_table:
            raise ValueError("classes_read nao pode passar de classes_in_table.")

        if self.classes_read != (
            self.classes_same_cnpj
            + self.classes_other_fund_cnpj
            + self.classes_only_class
            + self.classes_of_fund_without_data
        ):
            raise ValueError(
                "classes_read deve ser a soma das classes por tipo de CNPJ."
            )

        if isinstance(self.subjects, str) or not isinstance(
            self.subjects, (tuple, list)
        ):
            raise TypeError("subjects deve ser uma tupla de FundosSubjectRecord.")

        subjects = tuple(self.subjects)

        if any(
            not isinstance(subject, FundosSubjectRecord) for subject in subjects
        ):
            raise TypeError("subjects deve ser uma tupla de FundosSubjectRecord.")

        if len(subjects) != self.funds_read + self.classes_only_class:
            raise ValueError(
                "Deve haver um assunto por fundo lido e por classe que so "
                "existe como classe."
            )

        fund_subjects = sum(
            1 for subject in subjects if subject.source_table == "funds"
        )

        if fund_subjects != self.funds_read:
            raise ValueError("Deve haver um assunto por fundo lido.")

        keys = {(subject.source_table, subject.source_id) for subject in subjects}

        if len(keys) != len(subjects):
            raise ValueError("Cada linha de origem gera um assunto so.")

        object.__setattr__(self, "subjects", subjects)

    @property
    def funds_without_data(self) -> int:
        """Fundos da tabela sem nenhuma observacao registro_fundo.* em R."""

        return self.funds_in_table - self.funds_read

    @property
    def classes_without_data(self) -> int:
        """Classes da tabela sem nenhuma observacao registro_classe.* em R."""

        return self.classes_in_table - self.classes_read


@dataclass(frozen=True, slots=True)
class CdaHoldingLink:
    """Uma linha de holdings do CDA de um detentor (INVESTS_IN, PR C).

    So o CNPJ do investido (sem normalizar: as regras normalizam e contam o
    recusado), o id da linha e o inicio da coleta. Nome e valores da posicao
    nunca entram aqui.
    """

    investee_cnpj: str = field(repr=False)
    holding_id: int
    collected_at: datetime

    def __post_init__(self) -> None:
        _require_text(self.investee_cnpj, "investee_cnpj")
        _require_positive_int(self.holding_id, "holding_id")

        if not isinstance(self.collected_at, datetime):
            raise TypeError("collected_at deve ser datetime.")

        if self.collected_at.utcoffset() is None:
            raise ValueError("collected_at deve possuir timezone.")


class CdaUnavailableReason(StrEnum):
    """Por que o banco de Fundos nao tem dados de CDA (a fase 4 so conta)."""

    SEM_MIGRATION_004 = "sem_migration_004"
    SEM_COLETA_DE_CDA = "sem_coleta_de_cda"


class CdaIncompleteReason(StrEnum):
    """Por que uma competencia do CDA nao e completa: a primeira checagem que falha.

    A ordem e a dos valores: status da coleta, fonte, membro ausente
    (cda_fie_AAAAMM.csv ou cda_fie_CONFID_AAAAMM.csv), membro nao
    processado, line_count nulo e competencia divergente (linhas da coleta
    com mais de um reference_date, ou de outro mes que o AAAAMM do
    manifesto).
    """

    STATUS_NAO_SUCCESS = "status_nao_success"
    FONTE_DIFERENTE = "fonte_diferente"
    MEMBRO_AUSENTE = "membro_ausente"
    MEMBRO_NAO_PROCESSADO = "membro_nao_processado"
    LINE_COUNT_NULO = "line_count_nulo"
    COMPETENCIA_DIVERGENTE = "competencia_divergente"


def _require_date(value, name: str) -> None:
    if isinstance(value, datetime) or not isinstance(value, date):
        raise TypeError(f"{name} deve ser date.")


def _require_bool(value, name: str) -> None:
    if not isinstance(value, bool):
        raise TypeError(f"{name} deve ser booleano.")


def _tuple_of(values, kind, name: str) -> tuple:
    if isinstance(values, str) or not isinstance(values, (tuple, list)):
        raise TypeError(f"{name} deve ser uma tupla.")

    values = tuple(values)

    if any(not isinstance(value, kind) for value in values):
        raise TypeError(f"{name} deve conter {kind.__name__}.")

    return values


def _run_ids(values) -> tuple[int, ...]:
    values = _tuple_of(values, int, "run_ids")

    for value in values:
        _require_positive_int(value, "run_ids")

    if not values or list(values) != sorted(set(values)):
        raise ValueError("run_ids deve ter ids em ordem, sem repetir.")

    return values


def _require_reason(value) -> None:
    if value is not None and not isinstance(value, CdaIncompleteReason):
        raise TypeError("incomplete_reason deve ser CdaIncompleteReason.")


def months_between(earlier: date, later: date) -> int:
    """Meses entre duas competencias: 0 no mesmo mes, negativo se later vem antes."""

    _require_date(earlier, "earlier")
    _require_date(later, "later")

    return (later.year - earlier.year) * 12 + later.month - earlier.month


@dataclass(frozen=True, slots=True)
class CdaCompetence:
    """Uma competencia do CDA com posicao (identificada ou confidencial).

    run_ids sao as coletas com linha na competencia e as coletas sem nenhuma
    posicao do mesmo mes. closing_run_id e a de maior (started_at, id) entre
    as que tem linha: a coleta da proveniencia do fechamento. Completa se e
    so se nao ha motivo.
    """

    reference_date: date
    run_ids: tuple[int, ...]
    closing_run_id: int
    closing_started_at: datetime
    incomplete_reason: CdaIncompleteReason | None = None

    def __post_init__(self) -> None:
        _require_date(self.reference_date, "reference_date")
        object.__setattr__(self, "run_ids", _run_ids(self.run_ids))
        _require_positive_int(self.closing_run_id, "closing_run_id")

        if self.closing_run_id not in self.run_ids:
            raise ValueError("closing_run_id deve estar em run_ids.")

        if not isinstance(self.closing_started_at, datetime):
            raise TypeError("closing_started_at deve ser datetime.")

        if self.closing_started_at.utcoffset() is None:
            raise ValueError("closing_started_at deve possuir timezone.")

        _require_reason(self.incomplete_reason)

    @property
    def period(self) -> str:
        """AAAAMM da competencia."""

        return f"{self.reference_date.year:04d}{self.reference_date.month:02d}"

    @property
    def complete(self) -> bool:
        return self.incomplete_reason is None


@dataclass(frozen=True, slots=True)
class CdaEmptyPeriod:
    """Mes (AAAAMM do manifesto) com coleta de CDA e nenhuma posicao gravada."""

    period: str
    run_ids: tuple[int, ...]
    incomplete_reason: CdaIncompleteReason | None = None

    def __post_init__(self) -> None:
        period = self.period

        if not (
            isinstance(period, str)
            and len(period) == 6
            and period.isascii()
            and period.isdigit()
            and 1 <= int(period[4:]) <= 12
        ):
            raise ValueError("period deve ser AAAAMM.")

        object.__setattr__(self, "run_ids", _run_ids(self.run_ids))
        _require_reason(self.incomplete_reason)

    @property
    def complete(self) -> bool:
        return self.incomplete_reason is None


@dataclass(frozen=True, slots=True)
class CdaHolderRecord:
    """Um detentor do CDA na competencia mais recente dele (L_H).

    links sao so as linhas de holdings de L_H, em ordem de id; o CNPJ fica
    sem normalizar (o servico normaliza). has_confidential: ha posicao
    confidencial em L_H.
    """

    cnpj: str = field(repr=False)
    competence: date
    has_identified: bool
    has_confidential: bool
    links: tuple[CdaHoldingLink, ...] = field(default=(), repr=False)

    def __post_init__(self) -> None:
        _require_text(self.cnpj, "cnpj")
        _require_date(self.competence, "competence")
        _require_bool(self.has_identified, "has_identified")
        _require_bool(self.has_confidential, "has_confidential")
        links = _tuple_of(self.links, CdaHoldingLink, "links")
        ids = [link.holding_id for link in links]

        if ids != sorted(set(ids)):
            raise ValueError("links deve estar em ordem de id, sem repetir.")

        if self.has_identified != bool(links):
            raise ValueError("has_identified vale se e so se ha links.")

        if not (self.has_identified or self.has_confidential):
            raise ValueError("O detentor precisa ter posicao em L_H.")

        object.__setattr__(self, "links", links)


@dataclass(frozen=True, slots=True)
class CdaSnapshot:
    """O CDA do banco de Fundos lido pela camada (fase 4, INVESTS_IN).

    Sem dados (sem a migration 004 ou sem coleta de CDA): available falso e
    so o motivo. Com dados: as competencias com posicao, os meses com coleta
    e nenhuma posicao, e os detentores, cada um no seu L_H.
    """

    available: bool
    unavailable_reason: CdaUnavailableReason | None = None
    competences: tuple[CdaCompetence, ...] = ()
    empty_periods: tuple[CdaEmptyPeriod, ...] = ()
    holders: tuple[CdaHolderRecord, ...] = field(default=(), repr=False)

    def __post_init__(self) -> None:
        _require_bool(self.available, "available")
        competences = _tuple_of(self.competences, CdaCompetence, "competences")
        empty = _tuple_of(self.empty_periods, CdaEmptyPeriod, "empty_periods")
        holders = _tuple_of(self.holders, CdaHolderRecord, "holders")

        if self.available:
            if self.unavailable_reason is not None:
                raise ValueError("Com dados de CDA nao ha motivo de indisponivel.")

            if not competences and not empty:
                raise ValueError("Com dados de CDA ha pelo menos uma coleta.")
        else:
            if not isinstance(self.unavailable_reason, CdaUnavailableReason):
                raise TypeError("Sem dados de CDA, informe o CdaUnavailableReason.")

            if competences or empty or holders:
                raise ValueError("Sem dados de CDA nao ha competencia nem detentor.")

        dates = [item.reference_date for item in competences]

        if dates != sorted(set(dates)):
            raise ValueError("competences deve estar em ordem, sem repetir.")

        periods = [item.period for item in empty]

        if periods != sorted(set(periods)) or set(periods) & {
            item.period for item in competences
        }:
            raise ValueError("empty_periods deve estar em ordem, sem mes com posicao.")

        cnpjs = [holder.cnpj for holder in holders]

        if len(set(cnpjs)) != len(cnpjs):
            raise ValueError("holders nao pode repetir CNPJ.")

        if any(holder.competence not in dates for holder in holders):
            raise ValueError("O L_H de cada detentor deve estar em competences.")

        object.__setattr__(self, "competences", competences)
        object.__setattr__(self, "empty_periods", empty)
        object.__setattr__(self, "holders", holders)

    def competence(self, reference_date: date) -> CdaCompetence:
        """A competencia lida com essa data; KeyError se nao houver."""

        for item in self.competences:
            if item.reference_date == reference_date:
                return item

        raise KeyError("Competencia fora do CDA lido.")

    @property
    def latest_complete(self) -> date | None:
        """C_max: a maior competencia completa com posicao."""

        dates = [item.reference_date for item in self.competences if item.complete]

        return max(dates) if dates else None

    @property
    def complete(self) -> bool:
        """O L_H de todo detentor e completo e o mes mais novo do banco tambem.

        Um mes recente com coleta incompleta e sem nenhuma posicao deixa o CDA
        incompleto (C6). Sem dados de CDA, falso: quem chama olha available
        antes.
        """

        if not self.available:
            return False

        if any(not self.competence(holder.competence).complete for holder in self.holders):
            return False

        newest = max(
            [item.period for item in self.competences]
            + [item.period for item in self.empty_periods]
        )

        return all(
            item.complete
            for item in self.competences + self.empty_periods
            if item.period == newest
        )
