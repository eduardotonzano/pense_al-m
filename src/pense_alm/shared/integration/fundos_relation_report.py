"""Relatorio das relacoes de prestadora de Fundos (FU7.2, fase 3).

So contagens, tipos e o motivo da leitura incompleta: nenhum CNPJ, nome,
caminho ou mensagem de excecao entra aqui. As somas sao conferidas na
criacao, e cada mensagem de erro diz qual soma ou regra falhou.

- Soma 1, por tipo: pares_lidos = criadas + mantidas + reabertas +
  outra_fonte_presente + status_inesperado_presente + nao_criadas.total +
  erros de criar + erros de reabrir.
- Soma 2, por tipo: gravadas = mantidas + reabertas + outra_fonte_presente +
  status_inesperado_presente + fechadas + fechamento_suspenso +
  inativa_ausente + outra_fonte_ausente + status_inesperado_ausente + erros
  de reabrir + erros de fechar.
- Soma 3: a leitura e completa se e so se nao ha motivo; completa, nenhum
  fechamento suspenso; incompleta, nenhum fechamento.
- Soma 4: fundos_fora_do_normal_com_relacao <=
  relacoes_de_fundo_fora_do_normal_intactas, e um e zero se e so se o outro
  e zero.
- Regra 5 (erros) e regra 6 (tipos).

pares_de_fundo_nao_resolvido e relacoes_de_fundo_ausente_do_retrato sao
informativos e ficam fora das somas.
"""

from dataclasses import dataclass, field, fields

from pense_alm.shared.entities import RelationshipType

from .fundos_adapter import RELATION_TYPES
from .fundos_records import CadastroIncompleteReason
from .fundos_relation_rules import RelationOperation


# Campo do relatorio para cada tipo de relacao.
TYPE_FIELDS = {
    RelationshipType.ADMINISTERED_BY: "administered_by",
    RelationshipType.CUSTODIED_BY: "custodied_by",
    RelationshipType.MANAGES: "manages",
}
# Contadores de RelacoesPorTipo (todos menos nao_criadas).
TYPE_COUNTERS = (
    "pares_lidos",
    "gravadas",
    "criadas",
    "mantidas",
    "reabertas",
    "outra_fonte_presente",
    "status_inesperado_presente",
    "fechadas",
    "fechamento_suspenso",
    "inativa_ausente",
    "outra_fonte_ausente",
    "status_inesperado_ausente",
)
_GENERAL_COUNTERS = (
    "pares_de_fundo_nao_resolvido",
    "fundos_fora_do_normal_com_relacao",
    "relacoes_de_fundo_fora_do_normal_intactas",
    "relacoes_de_fundo_ausente_do_retrato",
)


def _require_count(value, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"Regra 6: {name} deve ser inteiro.")

    if value < 0:
        raise ValueError(f"Regra 6: {name} nao pode ser negativo.")


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


@dataclass(frozen=True, slots=True)
class RelacoesNaoCriadas:
    """Linhas de papel de fundo resolvido que nao viraram par, por motivo."""

    prestadora_sem_entidade: int = 0
    autorrelacao: int = 0

    def __post_init__(self) -> None:
        for item in fields(self):
            _require_count(getattr(self, item.name), item.name)

    @property
    def total(self) -> int:
        return self.prestadora_sem_entidade + self.autorrelacao


@dataclass(frozen=True, slots=True)
class RelacoesPorTipo:
    """Contagens de um tipo de relacao (ADMINISTERED_BY, CUSTODIED_BY ou MANAGES).

    pares_lidos: pares (tipo, prestadora) dos fundos resolvidos, inclusive os
    que nao viraram par. gravadas: relacoes desses fundos ja no destino, na
    direcao do fundo, de qualquer fonte. Os demais sao os resultados do
    classify; criadas, reabertas e fechadas so contam quando o save passa.
    """

    pares_lidos: int = 0
    gravadas: int = 0
    criadas: int = 0
    mantidas: int = 0
    reabertas: int = 0
    outra_fonte_presente: int = 0
    status_inesperado_presente: int = 0
    nao_criadas: RelacoesNaoCriadas = field(default_factory=RelacoesNaoCriadas)
    fechadas: int = 0
    fechamento_suspenso: int = 0
    inativa_ausente: int = 0
    outra_fonte_ausente: int = 0
    status_inesperado_ausente: int = 0

    def __post_init__(self) -> None:
        for name in TYPE_COUNTERS:
            _require_count(getattr(self, name), name)

        if not isinstance(self.nao_criadas, RelacoesNaoCriadas):
            raise TypeError("Regra 6: nao_criadas deve ser RelacoesNaoCriadas.")


@dataclass(frozen=True, slots=True)
class FundosRelationError:
    """Erros de gravacao, pelo tipo da excecao; a mensagem nunca e guardada."""

    tipo_relacao: RelationshipType
    operacao: RelationOperation
    tipo: str
    quantidade: int

    def __post_init__(self) -> None:
        if (
            not isinstance(self.tipo_relacao, RelationshipType)
            or self.tipo_relacao not in RELATION_TYPES
        ):
            raise ValueError("Regra 5: tipo_relacao fora do adaptador de Fundos.")

        if not isinstance(self.operacao, RelationOperation):
            raise TypeError("Regra 5: operacao deve ser RelationOperation.")

        if not isinstance(self.tipo, str) or not self.tipo.strip():
            raise ValueError("Regra 5: o tipo do erro nao pode ser vazio.")

        if isinstance(self.quantidade, bool) or not isinstance(
            self.quantidade, int
        ):
            raise TypeError("Regra 5: a quantidade deve ser inteira.")

        if self.quantidade < 1:
            raise ValueError("Regra 5: a quantidade deve ser pelo menos 1.")


def _error_key(erro: FundosRelationError):
    return (erro.tipo_relacao.value, erro.operacao.value, erro.tipo)


@dataclass(frozen=True, slots=True)
class FundosRelationReport:
    """Relatorio da fase 3 (relacoes de prestadora), so com contagens."""

    leitura_completa: bool
    motivo_nao_fechar: CadastroIncompleteReason | None
    administered_by: RelacoesPorTipo
    custodied_by: RelacoesPorTipo
    manages: RelacoesPorTipo
    pares_de_fundo_nao_resolvido: int
    fundos_fora_do_normal_com_relacao: int
    relacoes_de_fundo_fora_do_normal_intactas: int
    relacoes_de_fundo_ausente_do_retrato: int
    erros: tuple[FundosRelationError, ...] = ()

    def __post_init__(self) -> None:
        # Regra 6: tipos.
        if not isinstance(self.leitura_completa, bool):
            raise TypeError("Regra 6: leitura_completa deve ser booleano.")

        if self.motivo_nao_fechar is not None and not isinstance(
            self.motivo_nao_fechar, CadastroIncompleteReason
        ):
            raise TypeError(
                "Regra 6: motivo_nao_fechar deve ser CadastroIncompleteReason."
            )

        for name in TYPE_FIELDS.values():
            if not isinstance(getattr(self, name), RelacoesPorTipo):
                raise TypeError(f"Regra 6: {name} deve ser RelacoesPorTipo.")

        for name in _GENERAL_COUNTERS:
            _require_count(getattr(self, name), name)

        # Regra 5: erros.
        if isinstance(self.erros, str) or not isinstance(
            self.erros, (tuple, list)
        ):
            raise TypeError("Regra 5: erros deve ser uma tupla.")

        erros = tuple(self.erros)

        if any(not isinstance(erro, FundosRelationError) for erro in erros):
            raise TypeError("Regra 5: erros deve conter FundosRelationError.")

        chaves = [_error_key(erro) for erro in erros]

        _check(
            len(set(chaves)) == len(chaves),
            "Regra 5: o trio (tipo_relacao, operacao, tipo) nao pode se repetir.",
        )
        object.__setattr__(self, "erros", tuple(sorted(erros, key=_error_key)))

        for kind, name in TYPE_FIELDS.items():
            counts = getattr(self, name)
            criar = self.erros_de(kind, RelationOperation.CRIAR)
            reabrir = self.erros_de(kind, RelationOperation.REABRIR)
            fechar = self.erros_de(kind, RelationOperation.FECHAR)

            _check(
                counts.pares_lidos
                == counts.criadas
                + counts.mantidas
                + counts.reabertas
                + counts.outra_fonte_presente
                + counts.status_inesperado_presente
                + counts.nao_criadas.total
                + criar
                + reabrir,
                f"Soma 1 ({name}): pares_lidos deve ser a soma dos resultados "
                "dos pares lidos.",
            )
            _check(
                counts.gravadas
                == counts.mantidas
                + counts.reabertas
                + counts.outra_fonte_presente
                + counts.status_inesperado_presente
                + counts.fechadas
                + counts.fechamento_suspenso
                + counts.inativa_ausente
                + counts.outra_fonte_ausente
                + counts.status_inesperado_ausente
                + reabrir
                + fechar,
                f"Soma 2 ({name}): gravadas deve ser a soma dos resultados das "
                "relacoes gravadas.",
            )

        _check(
            self.leitura_completa == (self.motivo_nao_fechar is None),
            "Soma 3: a leitura e completa se e so se nao ha motivo.",
        )

        if self.leitura_completa:
            _check(
                all(
                    getattr(self, name).fechamento_suspenso == 0
                    for name in TYPE_FIELDS.values()
                ),
                "Soma 3: leitura completa nao suspende fechamento.",
            )
        else:
            _check(
                all(
                    getattr(self, name).fechadas == 0
                    for name in TYPE_FIELDS.values()
                ),
                "Soma 3: leitura incompleta nao fecha relacao.",
            )

        _check(
            self.fundos_fora_do_normal_com_relacao
            <= self.relacoes_de_fundo_fora_do_normal_intactas
            and (self.fundos_fora_do_normal_com_relacao == 0)
            == (self.relacoes_de_fundo_fora_do_normal_intactas == 0),
            "Soma 4: fundos_fora_do_normal_com_relacao deve caber em "
            "relacoes_de_fundo_fora_do_normal_intactas.",
        )

    def por_tipo(self, kind: RelationshipType) -> RelacoesPorTipo:
        """As contagens de um tipo de relacao."""

        return getattr(self, TYPE_FIELDS[kind])

    def erros_de(self, kind: RelationshipType, operacao: RelationOperation) -> int:
        """Quantidade de erros de um tipo de relacao numa operacao."""

        return sum(
            erro.quantidade
            for erro in self.erros
            if erro.tipo_relacao is kind and erro.operacao is operacao
        )

    @property
    def erros_total(self) -> int:
        return sum(erro.quantidade for erro in self.erros)
