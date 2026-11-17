"""Relatorio da importacao de entidades de Fundos (FU7.2, fases 1 e 2).

So contagens, a competencia do cadastro e o indicador de leitura completa:
nenhum CNPJ nem nome entra aqui. As somas sao conferidas na criacao, para
que nenhum fundo, classe ou prestadora fique fora da conta (ADR-013 e
decisoes de 16 e 17/11/2026). Cada mensagem de erro diz qual soma falhou.
"""

from dataclasses import dataclass, fields
from datetime import date, datetime


ERROR_PHASES = ("fundos", "prestadoras")


def _require_count(value, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} deve ser inteiro.")

    if value < 0:
        raise ValueError(f"{name} nao pode ser negativo.")


def _check_counters(instance) -> None:
    for item in fields(instance):
        _require_count(getattr(instance, item.name), item.name)


def _total(instance) -> int:
    return sum(getattr(instance, item.name) for item in fields(instance))


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


@dataclass(frozen=True, slots=True)
class FundosBacklog:
    """Grupos fora do funcionamento normal (D7), por situacao."""

    fase_pre_operacional: int = 0
    em_liquidacao: int = 0
    cancelado: int = 0
    incorporacao: int = 0
    em_situacao_especial: int = 0
    situacao_fora_da_tabela: int = 0
    sem_situacao: int = 0
    situacao_conflitante: int = 0

    def __post_init__(self) -> None:
        _check_counters(self)

    @property
    def total(self) -> int:
        return _total(self)


@dataclass(frozen=True, slots=True)
class FundosNaoCriados:
    """Grupos em funcionamento normal que nao viraram entidade, por motivo."""

    sem_nome: int = 0
    nome_divergente: int = 0
    tipo_divergente: int = 0
    tipo_fora_do_mapa: int = 0
    cnpj_recusado: int = 0
    cnpj_colisao: int = 0
    id_ocupado: int = 0

    def __post_init__(self) -> None:
        _check_counters(self)

    @property
    def total(self) -> int:
        return _total(self)


@dataclass(frozen=True, slots=True)
class PrestadorasNaoCriadas:
    """Prestadoras ligadas que nao viraram entidade, por motivo."""

    sem_nome: int = 0
    nome_divergente: int = 0
    cnpj_recusado: int = 0
    id_ocupado: int = 0

    def __post_init__(self) -> None:
        _check_counters(self)

    @property
    def total(self) -> int:
        return _total(self)


@dataclass(frozen=True, slots=True)
class FundosImportError:
    """Erros de uma fase, pelo tipo da excecao; a mensagem nunca e guardada."""

    fase: str
    tipo: str
    quantidade: int

    def __post_init__(self) -> None:
        if self.fase not in ERROR_PHASES:
            raise ValueError("Regra 10: a fase deve ser fundos ou prestadoras.")

        if not isinstance(self.tipo, str) or not self.tipo.strip():
            raise ValueError("Regra 10: o tipo do erro nao pode ser vazio.")

        if isinstance(self.quantidade, bool) or not isinstance(
            self.quantidade, int
        ):
            raise TypeError("Regra 10: a quantidade deve ser inteira.")

        if self.quantidade < 1:
            raise ValueError("Regra 10: a quantidade deve ser pelo menos 1.")


_COUNTERS = (
    "fundos_na_tabela",
    "fundos_lidos",
    "fundos_sem_dado_na_competencia",
    "classes_na_tabela",
    "classes_lidas",
    "classes_sem_dado_na_competencia",
    "classes_unidas_ao_fundo",
    "classes_com_cnpj_de_outro_fundo",
    "classes_so_como_classe",
    "classes_de_fundo_sem_dado",
    "cnpjs_lidos",
    "gestor_pessoa_fisica",
    "gestor_tipo_conflitante",
    "em_funcionamento_normal",
    "fora_do_normal_ja_na_camada",
    "fundos_criados",
    "fundos_reutilizados",
    "prestadoras_candidatas",
    "prestadoras_ligadas",
    "prestadoras_so_de_fundo_nao_resolvido",
    "prestadoras_criadas",
    "prestadoras_reutilizadas",
)


@dataclass(frozen=True, slots=True)
class FundosEntityReport:
    """Relatorio das fases 1 e 2 (fundos, classes e prestadoras).

    gestor_pessoa_fisica conta os fundos lidos cujo Tipo_Pessoa_Gestor e
    exatamente {'PF'}; gestor_tipo_conflitante conta os que tem mais de um
    valor (so informativo). fora_do_normal_ja_na_camada conta os grupos do
    backlog cujo CNPJ ja existe na camada como FIDC ou FIAGRO.
    """

    competencia_cadastro: date
    leitura_completa: bool
    fundos_na_tabela: int
    fundos_lidos: int
    fundos_sem_dado_na_competencia: int
    classes_na_tabela: int
    classes_lidas: int
    classes_sem_dado_na_competencia: int
    classes_unidas_ao_fundo: int
    classes_com_cnpj_de_outro_fundo: int
    classes_so_como_classe: int
    classes_de_fundo_sem_dado: int
    cnpjs_lidos: int
    gestor_pessoa_fisica: int
    gestor_tipo_conflitante: int
    em_funcionamento_normal: int
    backlog: FundosBacklog
    fora_do_normal_ja_na_camada: int
    fundos_criados: int
    fundos_reutilizados: int
    fundos_nao_criados: FundosNaoCriados
    prestadoras_candidatas: int
    prestadoras_ligadas: int
    prestadoras_so_de_fundo_nao_resolvido: int
    prestadoras_criadas: int
    prestadoras_reutilizadas: int
    prestadoras_nao_criadas: PrestadorasNaoCriadas
    erros: tuple[FundosImportError, ...] = ()

    def __post_init__(self) -> None:
        # Regra 1: tipos.
        if isinstance(self.competencia_cadastro, datetime) or not isinstance(
            self.competencia_cadastro, date
        ):
            raise TypeError("Regra 1: competencia_cadastro deve ser data, sem hora.")

        if not isinstance(self.leitura_completa, bool):
            raise TypeError("Regra 1: leitura_completa deve ser booleano.")

        for name in _COUNTERS:
            _require_count(getattr(self, name), name)

        for name, kind in (
            ("backlog", FundosBacklog),
            ("fundos_nao_criados", FundosNaoCriados),
            ("prestadoras_nao_criadas", PrestadorasNaoCriadas),
        ):
            if not isinstance(getattr(self, name), kind):
                raise TypeError(f"Regra 1: {name} deve ser {kind.__name__}.")

        if isinstance(self.erros, str) or not isinstance(
            self.erros, (tuple, list)
        ):
            raise TypeError("Regra 10: erros deve ser uma tupla.")

        erros = tuple(self.erros)

        if any(not isinstance(erro, FundosImportError) for erro in erros):
            raise TypeError("Regra 10: erros deve conter FundosImportError.")

        pares = [(erro.fase, erro.tipo) for erro in erros]

        _check(
            len(set(pares)) == len(pares),
            "Regra 10: o par (fase, tipo) nao pode se repetir.",
        )
        object.__setattr__(
            self,
            "erros",
            tuple(sorted(erros, key=lambda erro: (erro.fase, erro.tipo))),
        )

        _check(
            self.fundos_na_tabela
            == self.fundos_lidos + self.fundos_sem_dado_na_competencia,
            "Soma 2: fundos_na_tabela deve ser fundos_lidos + "
            "fundos_sem_dado_na_competencia.",
        )
        _check(
            self.classes_na_tabela
            == self.classes_lidas + self.classes_sem_dado_na_competencia,
            "Soma 3: classes_na_tabela deve ser classes_lidas + "
            "classes_sem_dado_na_competencia.",
        )
        _check(
            self.classes_lidas
            == self.classes_unidas_ao_fundo
            + self.classes_com_cnpj_de_outro_fundo
            + self.classes_so_como_classe
            + self.classes_de_fundo_sem_dado,
            "Soma 4: classes_lidas deve ser a soma das classes por tipo de CNPJ.",
        )
        _check(
            self.cnpjs_lidos == self.fundos_lidos + self.classes_so_como_classe,
            "Soma 5: cnpjs_lidos deve ser fundos_lidos + classes_so_como_classe.",
        )
        _check(
            self.cnpjs_lidos == self.em_funcionamento_normal + self.backlog.total,
            "Soma 6: cnpjs_lidos deve ser em_funcionamento_normal + backlog.",
        )
        _check(
            self.fora_do_normal_ja_na_camada <= self.backlog.total,
            "Soma 7: fora_do_normal_ja_na_camada nao pode passar do backlog.",
        )
        _check(
            self.gestor_pessoa_fisica + self.gestor_tipo_conflitante
            <= self.fundos_lidos,
            "Soma 7: gestor_pessoa_fisica + gestor_tipo_conflitante nao pode "
            "passar de fundos_lidos.",
        )
        _check(
            self.em_funcionamento_normal
            == self.fundos_criados
            + self.fundos_reutilizados
            + self.fundos_nao_criados.total
            + self.erros_da_fase("fundos"),
            "Soma 8: em_funcionamento_normal deve ser criados + reutilizados + "
            "nao criados + erros da fase fundos.",
        )
        _check(
            self.prestadoras_candidatas
            == self.prestadoras_ligadas
            + self.prestadoras_so_de_fundo_nao_resolvido,
            "Soma 9: prestadoras_candidatas deve ser ligadas + "
            "so_de_fundo_nao_resolvido.",
        )
        _check(
            self.prestadoras_ligadas
            == self.prestadoras_criadas
            + self.prestadoras_reutilizadas
            + self.prestadoras_nao_criadas.total
            + self.erros_da_fase("prestadoras"),
            "Soma 9: prestadoras_ligadas deve ser criadas + reutilizadas + "
            "nao criadas + erros da fase prestadoras.",
        )

    def erros_da_fase(self, fase: str) -> int:
        """Quantidade de erros de uma fase."""

        return sum(erro.quantidade for erro in self.erros if erro.fase == fase)

    @property
    def erros_total(self) -> int:
        return sum(erro.quantidade for erro in self.erros)
