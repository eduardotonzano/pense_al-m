"""Garantias do informe de FIDC (tab_X_7), como informadas (FU11.4).

Sao os dois campos da tab_X_7, ligados aos itens "7) Garantias" do modelo
do Suplemento G da Resolucao CVM 175 (Suplemento G, correspondencia pelo
nome do campo; o dicionario de dados da CVM nao descreve os dois campos):
- 7.1 TAB_X_VL_GARANTIA_DIRCRED: "Valor total das garantias vinculadas aos
  direitos creditorios", em R$;
- 7.2 TAB_X_PR_GARANTIA_DIRCRED: "Percentual dos direitos creditorios com
  garantias vinculadas", em %.

O informe nao traz o tipo da garantia nem um campo de presenca. Cada campo
sai como informado, com fonte, competencia, observacao e coleta, e estado
presente ou sem_dado (com o motivo): valor ausente e sem_dado, nunca zero;
zero informado e zero.

Nada e calculado entre os dois campos: o percentual e informado e nao e o
valor sobre a carteira (medido em 09 e 10/2026, em copias).

Marcas:
- garantia_informada_zero: valor e percentual informados iguais a 0. A
  exibicao diz "o informe traz 0", sem afirmar que nao ha garantia;
- percentual_acima_de_100: o percentual informado passa de 100;
- valor_e_percentual_incoerentes: um maior que 0 e o outro igual a 0;
- valor_negativo e percentual_negativo;
- conflito_aberto: algum dos dois campos tem conflito aberto no banco.

Nao confirmado: a base e a unidade do 7.2 (valor ou quantidade de direitos
creditorios) e se o 0 quer dizer "nao ha" ou "nao preenchido". Nada e
gravado.
"""

from dataclasses import dataclass
from decimal import Decimal

from fundos.database import normalize_iso_date
from fundos.indicators.reading import previous_month_end
from fundos.indicators.reading import read_competence
from fundos.indicators.values import PRESENT
from fundos.indicators.values import FieldValue
from fundos.indicators.values import Subject


TABLE = "tab_X_7"
VALUE = "tab_X_7.TAB_X_VL_GARANTIA_DIRCRED"
PERCENT = "tab_X_7.TAB_X_PR_GARANTIA_DIRCRED"

CORRESPONDENCE = "Suplemento G, correspondencia pelo nome do campo"
VALUE_ITEM = "7.1"
VALUE_NAME = "Valor total das garantias vinculadas aos direitos creditorios"
PERCENT_ITEM = "7.2"
PERCENT_NAME = "Percentual dos direitos creditorios com garantias vinculadas"

INFORMED_ZERO = "garantia_informada_zero"
PERCENT_ABOVE_100 = "percentual_acima_de_100"
INCOHERENT = "valor_e_percentual_incoerentes"
NEGATIVE_VALUE = "valor_negativo"
NEGATIVE_PERCENT = "percentual_negativo"
OPEN_CONFLICT = "conflito_aberto"
FLAGS = (
    INFORMED_ZERO,
    PERCENT_ABOVE_100,
    INCOHERENT,
    NEGATIVE_VALUE,
    NEGATIVE_PERCENT,
    OPEN_CONFLICT,
)

HUNDRED = Decimal(100)


@dataclass(frozen=True)
class GuaranteeResult:
    """As garantias de um assunto (classe ou fundo) numa competencia, como informadas."""

    subject: Subject
    reference_date: str
    value: FieldValue
    percent: FieldValue
    flags: tuple[str, ...] = ()
    correspondence: str = CORRESPONDENCE


def fields():
    """Campos lidos: o valor (7.1) e o percentual (7.2) da tab_X_7."""

    return (VALUE, PERCENT)


def _month_end(reference_date):
    reference = normalize_iso_date(reference_date, "Competencia")
    previous_month_end(reference)
    return reference


def _flags(value, percent):
    flags = []
    both = value.state == PRESENT and percent.state == PRESENT

    if both and value.value == 0 and percent.value == 0:
        flags.append(INFORMED_ZERO)

    if percent.state == PRESENT and percent.value > HUNDRED:
        flags.append(PERCENT_ABOVE_100)

    if both and (
        (value.value > 0 and percent.value == 0) or (value.value == 0 and percent.value > 0)
    ):
        flags.append(INCOHERENT)

    if value.state == PRESENT and value.value < 0:
        flags.append(NEGATIVE_VALUE)

    if percent.state == PRESENT and percent.value < 0:
        flags.append(NEGATIVE_PERCENT)

    if value.open_conflict or percent.open_conflict:
        flags.append(OPEN_CONFLICT)

    return tuple(flags)


def garantias(connection, reference_date, subjects=None):
    """As garantias por assunto (classe ou fundo) numa competencia (so le).

    So os assuntos com algum dos dois campos na competencia; subjects
    (opcional) limita a leitura. Devolve uma tupla em ordem de assunto.
    """

    reference = _month_end(reference_date)

    return tuple(
        GuaranteeResult(
            subject=subject,
            reference_date=reference,
            value=values[VALUE],
            percent=values[PERCENT],
            flags=_flags(values[VALUE], values[PERCENT]),
        )
        for subject, values in read_competence(connection, reference, fields(), subjects).items()
    )
