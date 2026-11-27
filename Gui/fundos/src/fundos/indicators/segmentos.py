"""Carteira por segmento do informe de FIDC (tab_II), calculada na leitura (FU11.4).

E a tabela II do modelo do Suplemento G da Resolucao CVM 175, "Carteira
por Segmento", como o informe a traz: o total TAB_II_VL_CARTEIRA e os 11
segmentos de topo (II.a a II.k), 5 deles com subitens (c, d, f, h e i).
Os valores sao em R$, como gravados, em Decimal exato.

Base do percentual: TAB_II_VL_CARTEIRA informado, o total da propria
tabela. O PL nao entra (decisao 8 de Fundos). Cada segmento e cada subitem
saem com o % nesse total. A soma dos segmentos e conferida com o total, e
a de cada subitem com o seu segmento, em Decimal exato; a diferenca vira
marca, e o total nunca e recalculado.

Concentracao, so nos 11 segmentos de topo: a lista dos segmentos maiores
que 0, do maior para o menor, o maior segmento, a quantidade de segmentos
diferentes de 0 e o HHI, a soma dos quadrados das parcelas em %, de 0 a
10.000. E concentracao por segmento informado, e nao por cedente nem por
sacado. O indicador nao tem faixa nem limiar.

Estado "calculado" ou "sem_dado", com o motivo:
- campo_ausente ou tipo_inesperado: no total ou em algum segmento de topo;
- denominador_zero ou denominador_negativo: o total e 0 ou negativo; os
  valores em R$ continuam presentes, sem o %.

Marcas:
- segmento_negativo: algum segmento de topo negativo. O valor e o % saem
  como informados, e o % dos demais pode passar de 100%; o maior segmento
  e o HHI ficam sem dado, com o motivo segmento_negativo;
- soma_dos_segmentos_diferente_do_total e subitens_diferentes_do_segmento;
- com_outros: II.f.8 ou II.i.4 ("Outros") diferente de 0;
- conflito_aberto: algum campo tem conflito aberto no banco.

Nao confirmado: o que o segmento classifica (o informe nao define) e se o
total cobre so direitos creditorios. Nada e gravado.
"""

from dataclasses import dataclass
from decimal import Decimal
from decimal import Inexact
from decimal import Rounded
from decimal import localcontext

from fundos.database import normalize_iso_date
from fundos.indicators.reading import previous_month_end
from fundos.indicators.reading import read_competence
from fundos.indicators.values import NO_DATA
from fundos.indicators.values import PRECISION
from fundos.indicators.values import PRESENT
from fundos.indicators.values import REASON_NEGATIVE_DENOMINATOR
from fundos.indicators.values import REASON_ZERO_DENOMINATOR
from fundos.indicators.values import Amount
from fundos.indicators.values import Ratio
from fundos.indicators.values import Subject
from fundos.indicators.values import percentage
from fundos.indicators.values import reported


TABLE = "tab_II"
OFFICIAL_NAME = "Carteira por Segmento"
TOTAL = "tab_II.TAB_II_VL_CARTEIRA"
BASE = "tab_II.TAB_II_VL_CARTEIRA informado (o total da propria tab_II); o PL nao entra"

CALCULATED = "calculado"
STATES = (CALCULATED, NO_DATA)

NEGATIVE_SEGMENT = "segmento_negativo"
SUM_DIFFERS = "soma_dos_segmentos_diferente_do_total"
SUBITEMS_DIFFER = "subitens_diferentes_do_segmento"
WITH_OTHERS = "com_outros"
OPEN_CONFLICT = "conflito_aberto"
FLAGS = (NEGATIVE_SEGMENT, SUM_DIFFERS, SUBITEMS_DIFFER, WITH_OTHERS, OPEN_CONFLICT)

HHI_SCALE = Decimal(10000)
_EXACT_PRECISION = 1000


def _field(column):
    return TABLE + "." + column


# (item do modelo, nome oficial sem acento, campo, ((item, nome, campo), ...)).
# Os nomes sao as descricoes do dicionario de dados da CVM.
SEGMENTS = (
    ("II.a", "Industrial", _field("TAB_II_A_VL_INDUST"), ()),
    (
        "II.b",
        "Mercado Imobiliario (nao financeiro - ver itens f6 e f7)",
        _field("TAB_II_B_VL_IMOBIL"),
        (),
    ),
    (
        "II.c",
        "Comercial",
        _field("TAB_II_C_VL_COMERC"),
        (
            ("II.c.1", "Comercial", _field("TAB_II_C1_VL_COMERC")),
            ("II.c.2", "Comercial - Varejo", _field("TAB_II_C2_VL_VAREJO")),
            ("II.c.3", "Arrendamento Mercantil", _field("TAB_II_C3_VL_ARREND")),
        ),
    ),
    (
        "II.d",
        "Servicos",
        _field("TAB_II_D_VL_SERV"),
        (
            ("II.d.1", "Servicos", _field("TAB_II_D1_VL_SERV")),
            (
                "II.d.2",
                "Servicos Publicos (eletricidade, telefonia, transporte, saneamento, etc)",
                _field("TAB_II_D2_VL_SERV_PUBLICO"),
            ),
            ("II.d.3", "Servicos Educacionais", _field("TAB_II_D3_VL_SERV_EDUC")),
            ("II.d.4", "Entretenimento", _field("TAB_II_D4_VL_ENTRET")),
        ),
    ),
    ("II.e", "Agronegocio", _field("TAB_II_E_VL_AGRONEG"), ()),
    (
        "II.f",
        "Financeiro",
        _field("TAB_II_F_VL_FINANC"),
        (
            ("II.f.1", "Credito Pessoal", _field("TAB_II_F1_VL_CRED_PESSOA")),
            ("II.f.2", "Credito Pessoal Consignado", _field("TAB_II_F2_VL_CRED_PESSOA_CONSIG")),
            ("II.f.3", "Direitos Credito Corporativo", _field("TAB_II_F3_VL_CRED_CORP")),
            ("II.f.4", "Middle Market", _field("TAB_II_F4_VL_MIDMARKET")),
            ("II.f.5", "Veiculos", _field("TAB_II_F5_VL_VEICULO")),
            ("II.f.6", "Carteira Imobiliaria - Empresarial", _field("TAB_II_F6_VL_IMOBIL_EMPRESA")),
            ("II.f.7", "Carteira Imobiliaria - Residencial", _field("TAB_II_F7_VL_IMOBIL_RESID")),
            ("II.f.8", "Outros", _field("TAB_II_F8_VL_OUTRO")),
        ),
    ),
    ("II.g", "Cartao de Credito", _field("TAB_II_G_VL_CREDITO"), ()),
    (
        "II.h",
        "Factoring",
        _field("TAB_II_H_VL_FACTOR"),
        (
            ("II.h.1", "Factoring - Pessoal (Perfil do Sacado)", _field("TAB_II_H1_VL_PESSOA")),
            ("II.h.2", "Factoring - Corporativo (Perfil do Sacado)", _field("TAB_II_H2_VL_CORP")),
        ),
    ),
    (
        "II.i",
        "Setor Publico (art. 1, par. 1, II, ICVM 444)",
        _field("TAB_II_I_VL_SETOR_PUBLICO"),
        (
            ("II.i.1", "Precatorios", _field("TAB_II_I1_VL_PRECAT")),
            ("II.i.2", "Creditos Tributarios", _field("TAB_II_I2_VL_TRIBUT")),
            ("II.i.3", "Royalties", _field("TAB_II_I3_VL_ROYALTIES")),
            ("II.i.4", "Outros", _field("TAB_II_I4_VL_OUTRO")),
        ),
    ),
    ("II.j", "Acoes Judiciais (art. 1, par. 1, III, ICVM 444)", _field("TAB_II_J_VL_JUDICIAL"), ()),
    ("II.k", "Propriedade Intelectual e Marcas & Patentes", _field("TAB_II_K_VL_MARCA"), ()),
)

OTHERS = (_field("TAB_II_F8_VL_OUTRO"), _field("TAB_II_I4_VL_OUTRO"))


@dataclass(frozen=True)
class SegmentShare:
    """Um segmento (ou subitem): o valor informado e o % no total da tab_II."""

    item: str
    name: str
    amount: Amount
    share: Ratio
    subitems: tuple["SegmentShare", ...] = ()

    def subitem(self, item):
        """O subitem pelo item do modelo (por exemplo II.f.8), ou None."""

        return next((sub for sub in self.subitems if sub.item == item), None)


@dataclass(frozen=True)
class SegmentResult:
    """A carteira por segmento de um assunto (classe ou fundo) numa competencia.

    segments: os 11 de topo, na ordem do modelo. ordered: so os maiores que
    0, do maior para o menor (empate: ordem do modelo), com todos os 11
    presentes. largest e hhi: so com estado calculado e sem segmento
    negativo; senao None, com o motivo em hhi_reason.
    """

    subject: Subject
    reference_date: str
    state: str
    total: Amount
    segments: tuple[SegmentShare, ...]
    ordered: tuple[SegmentShare, ...]
    largest: SegmentShare | None
    nonzero_count: int | None
    hhi: Decimal | None
    reason: str | None = None
    hhi_reason: str | None = None
    flags: tuple[str, ...] = ()
    name: str = OFFICIAL_NAME
    base: str = BASE

    def segment(self, item):
        """O segmento de topo pelo item do modelo (por exemplo II.f), ou None."""

        return next((segment for segment in self.segments if segment.item == item), None)


def fields():
    """Campos lidos: o total e cada segmento, com os seus subitens logo depois (33)."""

    names = [TOTAL]

    for _, _, field_name, subitems in SEGMENTS:
        names.append(field_name)
        names.extend(sub_field for _, _, sub_field in subitems)

    return tuple(names)


def _exact_sum(values):
    with localcontext() as context:
        context.prec = _EXACT_PRECISION
        context.traps[Inexact] = True
        context.traps[Rounded] = True
        return sum(values, Decimal(0))


def hhi(amounts, total):
    """Soma dos quadrados das parcelas em % (de 0 a 10.000), com total > 0.

    O numerador (soma dos quadrados x 10.000) e exato; a divisao pelo
    quadrado do total tem 28 digitos, sem arredondar para exibicao.
    """

    with localcontext() as context:
        context.prec = _EXACT_PRECISION
        context.traps[Inexact] = True
        context.traps[Rounded] = True
        numerator = sum((value * value for value in amounts), Decimal(0)) * HHI_SCALE
        denominator = total * total

    with localcontext() as context:
        context.prec = PRECISION
        return numerator / denominator


def _month_end(reference_date):
    reference = normalize_iso_date(reference_date, "Competencia")
    previous_month_end(reference)
    return reference


def _share(item, name, field_value, total, subitems=()):
    amount = reported(field_value)
    return SegmentShare(item, name, amount, percentage(amount, total), tuple(subitems))


def _state(total, segments):
    for amount in (total,) + tuple(segment.amount for segment in segments):
        if amount.state != PRESENT:
            return NO_DATA, amount.reason

    if total.value == 0:
        return NO_DATA, REASON_ZERO_DENOMINATOR

    if total.value < 0:
        return NO_DATA, REASON_NEGATIVE_DENOMINATOR

    return CALCULATED, None


def _present(amounts):
    return all(amount.state == PRESENT for amount in amounts)


def _flags(values, total, segments):
    flags = []
    amounts = [segment.amount for segment in segments]

    if any(amount.state == PRESENT and amount.value < 0 for amount in amounts):
        flags.append(NEGATIVE_SEGMENT)

    if _present([total] + amounts) and _exact_sum(a.value for a in amounts) != total.value:
        flags.append(SUM_DIFFERS)

    for segment in segments:
        parts = [sub.amount for sub in segment.subitems]

        if parts and _present([segment.amount] + parts):
            if _exact_sum(part.value for part in parts) != segment.amount.value:
                flags.append(SUBITEMS_DIFFER)
                break

    if any(values[name].state == PRESENT and values[name].value != 0 for name in OTHERS):
        flags.append(WITH_OTHERS)

    if any(value.open_conflict for value in values.values()):
        flags.append(OPEN_CONFLICT)

    return tuple(flags)


def _result(subject, reference, values):
    total = reported(values[TOTAL])
    segments = tuple(
        _share(
            item,
            name,
            values[field_name],
            total,
            [_share(sub_item, sub_name, values[sub_field], total) for sub_item, sub_name, sub_field in subitems],
        )
        for item, name, field_name, subitems in SEGMENTS
    )
    state, reason = _state(total, segments)
    flags = _flags(values, total, segments)
    ordered = ()
    nonzero_count = None

    if _present([segment.amount for segment in segments]):
        ordered = tuple(
            sorted(
                (segment for segment in segments if segment.amount.value > 0),
                key=lambda segment: segment.amount.value,
                reverse=True,
            )
        )
        nonzero_count = sum(1 for segment in segments if segment.amount.value != 0)

    largest = None
    concentration = None
    concentration_reason = reason

    if state == CALCULATED and NEGATIVE_SEGMENT in flags:
        concentration_reason = NEGATIVE_SEGMENT
    elif state == CALCULATED:
        largest = ordered[0] if ordered else None
        concentration = hhi([segment.amount.value for segment in segments], total.value)

    return SegmentResult(
        subject=subject,
        reference_date=reference,
        state=state,
        total=total,
        segments=segments,
        ordered=ordered,
        largest=largest,
        nonzero_count=nonzero_count,
        hhi=concentration,
        reason=reason,
        hhi_reason=concentration_reason,
        flags=flags,
    )


def carteira_por_segmento(connection, reference_date, subjects=None):
    """A carteira por segmento por assunto (classe ou fundo) numa competencia (so le).

    So os assuntos com algum campo da tab_II na competencia; subjects
    (opcional) limita a leitura. Devolve uma tupla em ordem de assunto.
    """

    reference = _month_end(reference_date)

    return tuple(
        _result(subject, reference, values)
        for subject, values in read_competence(connection, reference, fields(), subjects).items()
    )
