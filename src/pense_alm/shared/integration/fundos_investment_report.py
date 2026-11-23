"""Relatorio da fase 4 de Fundos: INVESTS_IN a partir do CDA (FU7.2, PR C2).

So contagens, a competencia mais nova completa e os motivos: nenhum CNPJ,
nome, caminho ou mensagem de excecao entra aqui. As somas sao conferidas na
criacao, e cada mensagem de erro diz qual soma ou regra falhou.

- Soma 1: pares_lidos = criadas + mantidas + reabertas + outra_fonte_presente
  + status_inesperado_presente + vigencia_posterior_presente +
  nao_criadas.total + erros de criar + erros de reabrir.
- Soma 2: gravadas = mantidas + reabertas + outra_fonte_presente +
  status_inesperado_presente + vigencia_posterior_presente + fechadas +
  fechamento_suspenso + suspensa_por_confidencial + inativa_ausente +
  outra_fonte_ausente + status_inesperado_ausente + vigencia_posterior_ausente
  + erros de reabrir + erros de fechar.
- Soma 3: a leitura e completa se e so se nao ha motivo; completa, nenhum
  detentor em CDA incompleto; sem detentor em CDA incompleto, nenhum
  fechamento suspenso. Leitura incompleta ainda fecha: o fechamento e por
  detentor (D6 de 23/11/2026).
- Sem CDA: so o motivo; todo o resto e zero.
- Soma 4 (S8): detentores_fora_do_normal_com_relacao cabe em
  detentores_fora_do_normal_na_camada e em
  relacoes_de_detentor_fora_do_normal_intactas, e um e zero se e so se o
  outro e zero.
- Soma 5: detentores_lidos = na camada + fora do normal na camada + fora da
  camada + fora do retrato + CNPJ recusado.
- Soma 6 (atraso, C4): a distribuicao por meses fecha com
  detentores_atrasados e relacoes_de_detentor_atrasado, os meses sao
  distintos, crescentes e pelo menos 1, detentores_atrasados cabe em
  detentores_na_camada e, sem competencia completa, nao ha atraso.
- Regra 7 (erros) e regra 8 (tipos).

pares_com_investido_fora_do_normal, relacoes_de_detentor_ausente_do_cda e o
atraso sao informativos e ficam fora das somas 1, 2 e 5.
"""

from dataclasses import dataclass, field, fields
from datetime import date, datetime

from .fundos_records import CdaIncompleteReason, CdaUnavailableReason
from .fundos_relation_rules import RelationOperation


# Grupos de contadores do relatorio, na ordem da saida.
HOLDER_COUNTERS = (
    "detentores_lidos",
    "detentores_na_camada",
    "detentores_fora_do_normal_na_camada",
    "detentores_fora_da_camada",
    "detentores_fora_do_retrato",
    "detentores_cnpj_recusado",
    "detentores_em_cda_incompleto",
)
PAIR_COUNTERS = (
    "pares_lidos",
    "gravadas",
    "criadas",
    "mantidas",
    "reabertas",
    "outra_fonte_presente",
    "status_inesperado_presente",
    "vigencia_posterior_presente",
    "fechadas",
    "fechamento_suspenso",
    "suspensa_por_confidencial",
    "inativa_ausente",
    "outra_fonte_ausente",
    "status_inesperado_ausente",
    "vigencia_posterior_ausente",
)
INFO_COUNTERS = (
    "detentores_fora_do_normal_com_relacao",
    "relacoes_de_detentor_fora_do_normal_intactas",
    "pares_com_investido_fora_do_normal",
    "relacoes_de_detentor_ausente_do_cda",
    "detentores_atrasados",
    "relacoes_de_detentor_atrasado",
)
COUNTERS = HOLDER_COUNTERS + PAIR_COUNTERS + INFO_COUNTERS


def _require_count(value, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"Regra 8: {name} deve ser inteiro.")

    if value < 0:
        raise ValueError(f"Regra 8: {name} nao pode ser negativo.")


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _tuple_of(values, kind, rule: str, name: str) -> tuple:
    if isinstance(values, str) or not isinstance(values, (tuple, list)):
        raise TypeError(f"{rule}: {name} deve ser uma tupla.")

    values = tuple(values)

    if any(not isinstance(value, kind) for value in values):
        raise TypeError(f"{rule}: {name} deve conter {kind.__name__}.")

    return values


@dataclass(frozen=True, slots=True)
class InvestimentosNaoCriados:
    """Investidos lidos que nao viraram par, por motivo (um por investido)."""

    investido_fora_da_camada: int = 0
    investido_de_outro_tipo: int = 0
    autorrelacao: int = 0
    cnpj_recusado: int = 0

    def __post_init__(self) -> None:
        for item in fields(self):
            _require_count(getattr(self, item.name), item.name)

    @property
    def total(self) -> int:
        return sum(getattr(self, item.name) for item in fields(self))


@dataclass(frozen=True, slots=True)
class AtrasoEmMeses:
    """Detentores com L_H a tantos meses do C_max, e as relacoes ativas deles."""

    meses: int
    detentores: int
    relacoes: int

    def __post_init__(self) -> None:
        for item in fields(self):
            _require_count(getattr(self, item.name), item.name)

        _check(self.meses >= 1, "Soma 6: o atraso e de pelo menos 1 mes.")
        _check(self.detentores >= 1, "Soma 6: cada atraso tem pelo menos 1 detentor.")


@dataclass(frozen=True, slots=True)
class FundosInvestmentError:
    """Erros de gravacao, pelo tipo da excecao; a mensagem nunca e guardada."""

    operacao: RelationOperation
    tipo: str
    quantidade: int

    def __post_init__(self) -> None:
        if not isinstance(self.operacao, RelationOperation):
            raise TypeError("Regra 7: operacao deve ser RelationOperation.")

        if not isinstance(self.tipo, str) or not self.tipo.strip():
            raise ValueError("Regra 7: o tipo do erro nao pode ser vazio.")

        if isinstance(self.quantidade, bool) or not isinstance(self.quantidade, int):
            raise TypeError("Regra 7: a quantidade deve ser inteira.")

        if self.quantidade < 1:
            raise ValueError("Regra 7: a quantidade deve ser pelo menos 1.")


def _error_key(erro: FundosInvestmentError):
    return (erro.operacao.value, erro.tipo)


@dataclass(frozen=True, slots=True)
class FundosInvestmentReport:
    """Relatorio da fase 4 (INVESTS_IN a partir do CDA), so com contagens.

    Detentores: cada detentor do CDA cai numa categoria so, pelo CNPJ. Na
    camada: em funcionamento normal e resolvido nas fases 1 e 2 (so estes sao
    processados). Fora do normal na camada: do backlog, ja na camada (S8).
    Fora do retrato: fundo da camada cujo CNPJ nao esta no retrato. Fora da
    camada: o resto. Em CDA incompleto: processados com L_H incompleto.

    Pares: um por investido do detentor processado, no L_H dele. gravadas:
    as INVESTS_IN que saem desses detentores, de qualquer fonte. Os demais
    sao os resultados das regras; criadas, reabertas e fechadas so contam
    quando o save passa.
    """

    cda_disponivel: bool
    leitura_completa: bool
    motivo_sem_cda: CdaUnavailableReason | None = None
    motivo_incompleto: CdaIncompleteReason | None = None
    competencia_mais_nova_completa: date | None = None
    detentores_lidos: int = 0
    detentores_na_camada: int = 0
    detentores_fora_do_normal_na_camada: int = 0
    detentores_fora_da_camada: int = 0
    detentores_fora_do_retrato: int = 0
    detentores_cnpj_recusado: int = 0
    detentores_em_cda_incompleto: int = 0
    pares_lidos: int = 0
    gravadas: int = 0
    criadas: int = 0
    mantidas: int = 0
    reabertas: int = 0
    outra_fonte_presente: int = 0
    status_inesperado_presente: int = 0
    vigencia_posterior_presente: int = 0
    nao_criadas: InvestimentosNaoCriados = field(default_factory=InvestimentosNaoCriados)
    fechadas: int = 0
    fechamento_suspenso: int = 0
    suspensa_por_confidencial: int = 0
    inativa_ausente: int = 0
    outra_fonte_ausente: int = 0
    status_inesperado_ausente: int = 0
    vigencia_posterior_ausente: int = 0
    detentores_fora_do_normal_com_relacao: int = 0
    relacoes_de_detentor_fora_do_normal_intactas: int = 0
    pares_com_investido_fora_do_normal: int = 0
    relacoes_de_detentor_ausente_do_cda: int = 0
    detentores_atrasados: int = 0
    relacoes_de_detentor_atrasado: int = 0
    atraso: tuple[AtrasoEmMeses, ...] = ()
    erros: tuple[FundosInvestmentError, ...] = ()

    def __post_init__(self) -> None:
        self._check_types()
        self._check_errors()

        if not self.cda_disponivel:
            self._check_without_cda()
            return

        _check(self.motivo_sem_cda is None, "Sem CDA: com CDA nao ha motivo_sem_cda.")
        criar = self.erros_de(RelationOperation.CRIAR)
        reabrir = self.erros_de(RelationOperation.REABRIR)
        fechar = self.erros_de(RelationOperation.FECHAR)

        _check(
            self.pares_lidos
            == self.criadas
            + self.mantidas
            + self.reabertas
            + self.outra_fonte_presente
            + self.status_inesperado_presente
            + self.vigencia_posterior_presente
            + self.nao_criadas.total
            + criar
            + reabrir,
            "Soma 1: pares_lidos deve ser a soma dos resultados dos pares lidos.",
        )
        _check(
            self.gravadas
            == self.mantidas
            + self.reabertas
            + self.outra_fonte_presente
            + self.status_inesperado_presente
            + self.vigencia_posterior_presente
            + self.fechadas
            + self.fechamento_suspenso
            + self.suspensa_por_confidencial
            + self.inativa_ausente
            + self.outra_fonte_ausente
            + self.status_inesperado_ausente
            + self.vigencia_posterior_ausente
            + reabrir
            + fechar,
            "Soma 2: gravadas deve ser a soma dos resultados das relacoes gravadas.",
        )
        _check(
            self.leitura_completa == (self.motivo_incompleto is None),
            "Soma 3: a leitura e completa se e so se nao ha motivo.",
        )
        _check(
            self.detentores_em_cda_incompleto <= self.detentores_na_camada,
            "Soma 3: detentores_em_cda_incompleto cabe em detentores_na_camada.",
        )

        if self.leitura_completa:
            _check(
                self.detentores_em_cda_incompleto == 0,
                "Soma 3: leitura completa nao tem detentor em CDA incompleto.",
            )

        if self.detentores_em_cda_incompleto == 0:
            _check(
                self.fechamento_suspenso == 0,
                "Soma 3: sem detentor em CDA incompleto, nenhum fechamento suspenso.",
            )

        _check(
            self.detentores_fora_do_normal_com_relacao
            <= self.detentores_fora_do_normal_na_camada
            and self.detentores_fora_do_normal_com_relacao
            <= self.relacoes_de_detentor_fora_do_normal_intactas
            and (self.detentores_fora_do_normal_com_relacao == 0)
            == (self.relacoes_de_detentor_fora_do_normal_intactas == 0),
            "Soma 4: detentores_fora_do_normal_com_relacao deve caber nos "
            "detentores fora do normal e nas relacoes intactas.",
        )
        _check(
            self.detentores_lidos
            == self.detentores_na_camada
            + self.detentores_fora_do_normal_na_camada
            + self.detentores_fora_da_camada
            + self.detentores_fora_do_retrato
            + self.detentores_cnpj_recusado,
            "Soma 5: detentores_lidos deve ser a soma das categorias.",
        )
        self._check_delay()

    def _check_types(self) -> None:
        # Regra 8: tipos.
        for name in ("cda_disponivel", "leitura_completa"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"Regra 8: {name} deve ser booleano.")

        if self.motivo_sem_cda is not None and not isinstance(
            self.motivo_sem_cda, CdaUnavailableReason
        ):
            raise TypeError("Regra 8: motivo_sem_cda deve ser CdaUnavailableReason.")

        if self.motivo_incompleto is not None and not isinstance(
            self.motivo_incompleto, CdaIncompleteReason
        ):
            raise TypeError("Regra 8: motivo_incompleto deve ser CdaIncompleteReason.")

        latest = self.competencia_mais_nova_completa

        if latest is not None and (isinstance(latest, datetime) or not isinstance(latest, date)):
            raise TypeError("Regra 8: competencia_mais_nova_completa deve ser date.")

        for name in COUNTERS:
            _require_count(getattr(self, name), name)

        if not isinstance(self.nao_criadas, InvestimentosNaoCriados):
            raise TypeError("Regra 8: nao_criadas deve ser InvestimentosNaoCriados.")

        object.__setattr__(
            self, "atraso", _tuple_of(self.atraso, AtrasoEmMeses, "Regra 8", "atraso")
        )

    def _check_errors(self) -> None:
        # Regra 7: erros.
        erros = _tuple_of(self.erros, FundosInvestmentError, "Regra 7", "erros")
        chaves = [_error_key(erro) for erro in erros]

        _check(
            len(set(chaves)) == len(chaves),
            "Regra 7: o par (operacao, tipo) nao pode se repetir.",
        )
        object.__setattr__(self, "erros", tuple(sorted(erros, key=_error_key)))

    def _check_without_cda(self) -> None:
        _check(
            isinstance(self.motivo_sem_cda, CdaUnavailableReason),
            "Sem CDA: informe o motivo_sem_cda.",
        )
        _check(
            not self.leitura_completa
            and self.motivo_incompleto is None
            and self.competencia_mais_nova_completa is None
            and all(getattr(self, name) == 0 for name in COUNTERS)
            and self.nao_criadas.total == 0
            and not self.atraso
            and not self.erros,
            "Sem CDA: todo o resto do relatorio e zero.",
        )

    def _check_delay(self) -> None:
        meses = [item.meses for item in self.atraso]

        _check(
            meses == sorted(set(meses)),
            "Soma 6: os meses do atraso sao distintos e crescentes.",
        )
        _check(
            sum(item.detentores for item in self.atraso) == self.detentores_atrasados
            and sum(item.relacoes for item in self.atraso)
            == self.relacoes_de_detentor_atrasado,
            "Soma 6: a distribuicao do atraso deve fechar com os totais.",
        )
        _check(
            self.detentores_atrasados <= self.detentores_na_camada,
            "Soma 6: detentores_atrasados cabe em detentores_na_camada.",
        )

        if self.competencia_mais_nova_completa is None:
            _check(not self.atraso, "Soma 6: sem competencia completa, nao ha atraso.")

    @classmethod
    def sem_cda(cls, motivo: CdaUnavailableReason) -> "FundosInvestmentReport":
        """O relatorio da fase 4 quando o banco de Fundos nao tem dados de CDA."""

        return cls(cda_disponivel=False, leitura_completa=False, motivo_sem_cda=motivo)

    def erros_de(self, operacao: RelationOperation) -> int:
        """Quantidade de erros numa operacao."""

        return sum(erro.quantidade for erro in self.erros if erro.operacao is operacao)

    @property
    def erros_total(self) -> int:
        return sum(erro.quantidade for erro in self.erros)
