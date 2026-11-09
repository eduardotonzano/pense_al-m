from __future__ import annotations

import string
from decimal import Decimal

import pytest

from credit_assets.debtor_exposure import (
    aggregate,
    classify_identifier,
    format_cnpj,
    fraction,
    informed_cnpj,
    normalize_cnpj,
)
from tests.cnpj_amostras import (
    CNPJ_ALFA_1,
    CNPJ_RECEITA,
    CNPJ_RECEITA_MASCARA,
    com_mascara,
    dv_errado,
    montar_cnpj,
)

CAFE = "01486546000167"  # Café Brasil (CNPJ do Termo)
ECO = "10.753.164/0001-43"  # Eco Securitizadora


def test_normalize_cnpj_validates_check_digits():
    assert normalize_cnpj("01.486.546/0001-67") == CAFE
    assert normalize_cnpj(ECO) == "10753164000143"
    assert normalize_cnpj("01486546000168") is None  # dígito errado
    assert normalize_cnpj("0") is None and normalize_cnpj("") is None
    assert normalize_cnpj("00000000000000") is None
    assert format_cnpj(CAFE) == "01.486.546/0001-67"


def test_fraction_accepts_0_1_and_0_100_and_rejects_negative():
    assert fraction("1.0000") == Decimal("1.0000")
    assert fraction("0,25") == Decimal("0.25")
    assert fraction("25") == Decimal("0.25")
    assert fraction("-1") is None and fraction("") is None and fraction("abc") is None


def link(cert, cnpj=CAFE, tipo="Devedor", pct="1.0", kind="CRA"):
    return {"certificado": cert, "tipo": tipo, "cnpj": cnpj, "percentual": pct, "kind": kind}


def test_aggregate_exposure_contagion_and_invalid_counts():
    links = [
        link("A"), link("A"),  # repetido no mesmo certificado conta uma vez
        link("B", pct="0.5"),
        link("C", cnpj="10753164000143"),
        link("D", cnpj="0"),
        link("E", pct="-1"),
        link("A", tipo="Cedente"),
    ]
    balances = {"A": Decimal(100), "B": Decimal(200), "C": Decimal(50), "E": Decimal(10)}
    ranking, stats = aggregate(links, balances, delinquent={"A"})
    cafe = next(i for i in ranking if i["cnpj"] == CAFE)
    assert cafe["exposicao"] == Decimal(200)  # 100 (A) + 0,5 × 200 (B); E sem percentual válido
    assert cafe["certificados"] == {"A", "B", "E"} and cafe["em_atraso"] == {"A"} and cafe["contagio"]
    other = next(i for i in ranking if i["cnpj"] == "10753164000143")
    assert not other["contagio"]
    assert stats == {"vinculos": 6, "nao_informado": 1, "cpf": 0, "cnpj_invalido": 0, "cnpj_sem_zeros": 0,
                     "cnpj_alfanumerico": 0, "percentual_invalido": 1}
    assert ranking[0]["cnpj"] == CAFE


def test_classify_identifier_separates_missing_cpf_lost_zeros_and_invalid():
    from credit_assets.debtor_exposure import classify_identifier, informed_cnpj
    assert classify_identifier("01.486.546/0001-67") == ("cnpj", CAFE)
    assert classify_identifier("1486546000167") == ("cnpj_sem_zeros", CAFE)  # CSV perdeu o zero à esquerda
    assert classify_identifier("1486546000168") == ("invalido", None)  # sem zero e com dígito errado: não recupera
    for missing in ("", "0", "1", ",", "NA", None, "00000000000000", "99.999.999/9999-99"):
        assert classify_identifier(missing) == ("nao_informado", None)
    assert classify_identifier("529.982.247-25") == ("cpf", None)  # CPF não é devolvido
    assert classify_identifier("01486546000168") == ("invalido", None)
    assert informed_cnpj("1486546000167") == CAFE and informed_cnpj("529.982.247-25") is None


def test_aggregate_counts_each_reason_apart():
    links = [link("A", cnpj=""), link("B", cnpj="529.982.247-25"), link("C", cnpj="01486546000168"),
             link("D", cnpj="1486546000167")]
    ranking, stats = aggregate(links, {"D": Decimal(10)}, delinquent=set())
    assert [i["cnpj"] for i in ranking] == [CAFE]
    assert (stats["nao_informado"], stats["cpf"], stats["cnpj_invalido"], stats["cnpj_sem_zeros"]) == (1, 1, 1, 1)


# CNPJ alfanumérico (IN RFB 2.229/2024). Valores fictícios de tests/cnpj_amostras.py, com DV calculado lá.


def _is_valid_numeric(value: str) -> bool:
    return len(value) == 14 and value.isdigit() and len(set(value)) > 1 and montar_cnpj(value[:12]) == value


def _numeric_rest(value: str) -> str:
    """O que o código antigo fazia: tira tudo que não é dígito e completa com zeros."""

    return "".join(c for c in value if c.isdigit()).zfill(14)


def _letter_bases(letters: int):
    """Bases fictícias 9999999n9999 com 1 letra (fora da posição do n: sobram 11 dígitos na base) ou 2 letras
    (posições 0 e 11: sobram 10)."""

    upper = string.ascii_uppercase
    for n in range(10):
        root = "9999999" + str(n) + "9999"
        if letters == 1:
            spots = [((pos,), (letter,)) for pos in range(12) if pos != 7 for letter in upper]
        else:
            spots = [((0, 11), (first, second)) for first in upper for second in upper]
        for positions, chosen in spots:
            base = list(root)
            for pos, letter in zip(positions, chosen):
                base[pos] = letter
            yield "".join(base)


def _valid_alnum_with_numeric_rest(letters: int) -> list[str]:
    """CNPJs alfanuméricos válidos cujo resto numérico, completado com zeros, é um CNPJ numérico válido."""

    candidates = (montar_cnpj(base) for base in _letter_bases(letters))
    return [value for value in candidates if _is_valid_numeric(_numeric_rest(value))]


def _wrong_dv_alnum_with_numeric_rest(letters: int) -> list[str]:
    """Valores com letra e DV alfanumérico errado cujo resto numérico é um CNPJ numérico válido."""

    found = []
    for base in _letter_bases(letters):
        rest = "".join(c for c in base if c.isdigit())
        value = base + montar_cnpj(rest.zfill(12))[12:]
        if value != montar_cnpj(base) and _is_valid_numeric(_numeric_rest(value)):
            found.append(value)
    return found


@pytest.mark.parametrize("letters", [1, 2], ids=["uma-letra-13-digitos", "duas-letras-12-digitos"])
def test_letter_value_never_takes_the_lost_zeros_path(letters):
    vectors = _valid_alnum_with_numeric_rest(letters)
    assert vectors  # o gerador acha casos: tirar as letras forma, por acaso, outro CNPJ
    for value in vectors:
        assert classify_identifier(value) == ("cnpj", value)
        assert classify_identifier(com_mascara(value).lower()) == ("cnpj", value)
        assert informed_cnpj(value) == value


@pytest.mark.parametrize("letters", [1, 2], ids=["uma-letra-13-digitos", "duas-letras-12-digitos"])
def test_letter_value_with_wrong_dv_is_invalid_even_if_digits_would_be_a_cnpj(letters):
    vectors = _wrong_dv_alnum_with_numeric_rest(letters)
    assert vectors
    for value in vectors:
        assert classify_identifier(value) == ("invalido", None)
        assert informed_cnpj(value) is None


def test_alphanumeric_cnpj_is_accepted_and_formatted():
    for value, expected in [
        (CNPJ_ALFA_1, CNPJ_ALFA_1),
        (com_mascara(CNPJ_ALFA_1), CNPJ_ALFA_1),
        (com_mascara(CNPJ_ALFA_1).lower(), CNPJ_ALFA_1),
        (CNPJ_RECEITA, CNPJ_RECEITA),
        (CNPJ_RECEITA_MASCARA, CNPJ_RECEITA),
        (" " + CNPJ_RECEITA_MASCARA.lower() + " ", CNPJ_RECEITA),
        ("12IBC34501DE10", "12IBC34501DE10"),
    ]:
        assert normalize_cnpj(value) == expected
        assert classify_identifier(value) == ("cnpj", expected)
        assert informed_cnpj(value) == expected
    assert normalize_cnpj(dv_errado(CNPJ_RECEITA)) is None
    assert format_cnpj(CNPJ_RECEITA) == CNPJ_RECEITA_MASCARA


TWO_ZEROS = montar_cnpj("009999991999")  # fictício, com dois zeros à esquerda


@pytest.mark.parametrize("value, expected", [
    ("01.486.546/0001-67", ("cnpj", CAFE)),
    ("01486546000167", ("cnpj", CAFE)),
    (" 01.486.546/0001-67 ", ("cnpj", CAFE)),
    ("01 486 546 0001 67", ("cnpj", CAFE)),
    ("1486546000167", ("cnpj_sem_zeros", CAFE)),
    ("1.486.546/0001-67", ("cnpj_sem_zeros", CAFE)),
    (TWO_ZEROS[2:], ("cnpj_sem_zeros", TWO_ZEROS)),
    ("529.982.247-25", ("cpf", None)),
    ("01486546000168", ("invalido", None)),
    ("1486546000168", ("invalido", None)),
    ("", ("nao_informado", None)),
    ("0", ("nao_informado", None)),
    (None, ("nao_informado", None)),
    ("00000000000000", ("nao_informado", None)),
    ("99.999.999/9999-99", ("nao_informado", None)),
])
def test_values_without_letters_keep_todays_classification(value, expected):
    assert classify_identifier(value) == expected


@pytest.mark.parametrize("value, expected", [
    ("NA", ("nao_informado", None)),
    ("N/A", ("nao_informado", None)),
    ("Não informado", ("nao_informado", None)),
    ("CPF 529.982.247-25", ("invalido", None)),  # com letra, nunca vira CPF
    ("12ABC34501DE3A", ("invalido", None)),  # letra na posição do DV
    ("12.ABC.345/01DE-3A", ("invalido", None)),
])
def test_letter_values_that_are_not_cnpj(value, expected):
    assert classify_identifier(value) == expected
    assert normalize_cnpj(value) is None


def test_dotless_i_in_alphanumeric_cnpj_is_invalid():
    # "12IBC34501DE10" é válido (DV conferido pelo cálculo independente); trocar o I por "ı" (U+0131), que vira "I"
    # em maiúsculas, mantém os mesmos dígitos e tem de ser recusado.
    assert montar_cnpj("12IBC34501DE") == "12IBC34501DE10"
    assert classify_identifier("12ıBC34501DE10") == ("invalido", None)
    assert normalize_cnpj("12ıBC34501DE10") is None


@pytest.mark.parametrize("value, expected", [
    ("CNPJ 01.486.546/0001-67", ("cnpj", CAFE)),  # como hoje: 14 dígitos ASCII nunca vêm só de um alfanumérico
    ("CNPJ: 01486546000167", ("cnpj", CAFE)),
    ("CNPJ 01.486.546/0001-68", ("invalido", None)),  # DV errado
    ("CNPJ 1486546000167", ("invalido", None)),  # 13 dígitos com letra: nunca completa zeros
    ("CNPJ 00.000.000/0000-00", ("nao_informado", None)),
])
def test_letter_value_with_14_digits_keeps_todays_result(value, expected):
    assert classify_identifier(value) == expected
    assert normalize_cnpj(value) == (expected[1] if expected[0] == "cnpj" else None)


def test_aggregate_counts_alphanumeric_cnpj_among_valid():
    links = [
        link("A", cnpj=CNPJ_RECEITA),
        link("A", cnpj=CNPJ_RECEITA_MASCARA),
        link("A", cnpj=CNPJ_RECEITA_MASCARA.lower()),
        link("B", cnpj="CNPJ 01.486.546/0001-67"),  # letra só no rótulo: CNPJ numérico
    ]
    ranking, stats = aggregate(links, {"A": Decimal(100), "B": Decimal(10)}, delinquent=set())
    assert [i["cnpj"] for i in ranking] == [CNPJ_RECEITA, CAFE]
    alnum, numeric = ranking
    assert alnum["certificados"] == {"A"} and alnum["exposicao"] == Decimal(100)
    assert numeric["certificados"] == {"B"} and numeric["exposicao"] == Decimal(10)
    # por vínculo, como vinculos e cnpj_sem_zeros: as 3 variantes contam; o rótulo com CNPJ numérico não
    assert stats["vinculos"] == 4 and stats["cnpj_alfanumerico"] == 3
