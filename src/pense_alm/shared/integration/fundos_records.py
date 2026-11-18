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
