import random

import pytest

from apoio import FAKE_CPF
from apoio import FAKE_CPF_MASKED
from apoio import make_test_cnpj
from fundos.cnpj import InvalidCnpjError
from fundos.cnpj import cnpj_check_digits
from fundos.cnpj import format_cnpj
from fundos.cnpj import is_valid_cnpj
from fundos.cnpj import looks_like_cpf
from fundos.cnpj import normalize_cnpj


NUMERIC = make_test_cnpj(1)
ALPHANUMERIC = make_test_cnpj(1, alphanumeric=True)

# Exemplo de referencia do CNPJ alfanumerico: vem de material tecnico de
# terceiros sobre o CNPJ alfanumerico, onde e descrito como ficticio. Nao e
# norma conferida no repositorio.
REFERENCE_MASKED = "12.ABC.345/01DE-35"
REFERENCE = "12ABC34501DE35"


def masked(cnpj):
    return cnpj[:2] + "." + cnpj[2:5] + "." + cnpj[5:8] + "/" + cnpj[8:12] + "-" + cnpj[12:]


def wrong_last_digit(cnpj):
    return cnpj[:13] + str((int(cnpj[13]) + 1) % 10)


def with_leading_zeros(zeros):
    """CNPJ valido que comeca com zeros, e a mesma entrada sem esses zeros."""

    base = "0" * zeros + "999999199999"[: 12 - zeros]
    full = base + cnpj_check_digits(base)
    return full, full[zeros:]


def test_reference_example_has_check_digits_35():
    assert cnpj_check_digits("12ABC34501DE") == "35"


def test_reference_example_normalizes_and_formats():
    assert normalize_cnpj(REFERENCE_MASKED) == REFERENCE
    assert format_cnpj(REFERENCE) == REFERENCE_MASKED


@pytest.mark.parametrize(
    "value, expected",
    [
        (NUMERIC, NUMERIC),
        (masked(NUMERIC), NUMERIC),
        (ALPHANUMERIC, ALPHANUMERIC),
        (masked(ALPHANUMERIC), ALPHANUMERIC),
    ],
    ids=["numerico", "numerico-mascara", "alfanumerico", "alfanumerico-mascara"],
)
def test_accepted_forms(value, expected):
    assert normalize_cnpj(value) == expected


@pytest.mark.parametrize(
    "value",
    [ALPHANUMERIC.lower(), masked(ALPHANUMERIC).lower(), "  " + ALPHANUMERIC + " "],
    ids=["minuscula", "minuscula-mascara", "espacos"],
)
def test_lowercase_and_surrounding_spaces_are_normalized(value):
    assert normalize_cnpj(value) == ALPHANUMERIC


@pytest.mark.parametrize(
    "value",
    [wrong_last_digit(NUMERIC), "12ABC34501DE36"],
    ids=["numerico", "alfanumerico"],
)
def test_invalid_check_digit_is_refused(value):
    with pytest.raises(InvalidCnpjError, match="digito verificador"):
        normalize_cnpj(value)


@pytest.mark.parametrize(
    "value",
    [
        "12ABC34501DE3A",
        "12.ABC.345/01DE-3A",
        "12ABC34501DÇ35",
        "12ABC34501D*35",
        "12.ABC.34501DE-35",
        "12ABC34501DE3",
        "",
    ],
    ids=[
        "letra-no-dv",
        "letra-no-dv-mascara",
        "cedilha",
        "simbolo",
        "mascara-parcial",
        "13-caracteres",
        "vazio",
    ],
)
def test_values_outside_the_format_are_refused(value):
    with pytest.raises(InvalidCnpjError):
        normalize_cnpj(value)


@pytest.mark.parametrize("value", [None, 99999991999962, b"99999991999962"])
def test_non_text_is_refused(value):
    with pytest.raises(InvalidCnpjError, match="texto"):
        normalize_cnpj(value)


def test_all_equal_characters_are_refused_even_with_valid_check_digits():
    assert cnpj_check_digits("000000000000") == "00"

    with pytest.raises(InvalidCnpjError, match="iguais"):
        normalize_cnpj("00000000000000")


@pytest.mark.parametrize("zeros", [1, 2])
def test_leading_zeros_are_restored_only_when_asked(zeros):
    full, short = with_leading_zeros(zeros)

    with pytest.raises(InvalidCnpjError):
        normalize_cnpj(short)

    assert normalize_cnpj(short, allow_missing_leading_zeros=True) == full


def test_restored_zeros_still_need_a_valid_check_digit():
    full, short = with_leading_zeros(1)

    with pytest.raises(InvalidCnpjError, match="digito verificador"):
        normalize_cnpj(wrong_last_digit(full)[1:], allow_missing_leading_zeros=True)

    assert short == full[1:]


def test_eleven_digits_are_never_completed_even_if_they_would_be_valid():
    full, eleven = with_leading_zeros(3)

    assert is_valid_cnpj(full)
    assert len(eleven) == 11

    for value in (eleven, FAKE_CPF):
        with pytest.raises(InvalidCnpjError):
            normalize_cnpj(value, allow_missing_leading_zeros=True)


def test_zeros_are_never_added_to_input_with_letters():
    with pytest.raises(InvalidCnpjError):
        normalize_cnpj(ALPHANUMERIC[1:], allow_missing_leading_zeros=True)


def test_format_round_trip():
    for cnpj in (NUMERIC, ALPHANUMERIC, REFERENCE):
        assert normalize_cnpj(format_cnpj(cnpj)) == cnpj


def test_is_valid_cnpj_needs_the_normalized_form():
    assert is_valid_cnpj(NUMERIC)
    assert is_valid_cnpj(ALPHANUMERIC)
    assert not is_valid_cnpj(masked(NUMERIC))
    assert not is_valid_cnpj(ALPHANUMERIC.lower())
    assert not is_valid_cnpj(None)


def test_check_digits_need_a_base_of_12_uppercase_characters():
    for base in ("12abc34501de", "12ABC34501D", "12ABC34501DE0"):
        with pytest.raises(InvalidCnpjError):
            cnpj_check_digits(base)


def test_looks_like_cpf_is_format_only():
    assert looks_like_cpf(FAKE_CPF)
    assert looks_like_cpf(FAKE_CPF_MASKED)
    assert not looks_like_cpf(NUMERIC)
    assert not looks_like_cpf(masked(NUMERIC))
    assert not looks_like_cpf(ALPHANUMERIC)
    assert not looks_like_cpf(None)


def test_fictitious_helper_and_production_code_agree():
    # Os dois calculos sao independentes (tests/apoio.py e fundos.cnpj).
    for n in range(10):
        for alphanumeric in (False, True):
            assert is_valid_cnpj(make_test_cnpj(n, alphanumeric=alphanumeric))


def test_error_messages_never_repeat_the_value():
    for value in (wrong_last_digit(NUMERIC), FAKE_CPF, "12ABC34501DE3A"):
        with pytest.raises(InvalidCnpjError) as error:
            normalize_cnpj(value)

        assert value not in str(error.value)


def classic_numeric_check_digits(base12):
    """Calculo classico do CNPJ numerico, escrito aqui so para comparar."""

    digits = [int(char) for char in base12]
    first_weights = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    second_weights = [6] + first_weights
    remainder = sum(d * w for d, w in zip(digits, first_weights)) % 11
    first = 0 if remainder < 2 else 11 - remainder
    remainder = sum(d * w for d, w in zip(digits + [first], second_weights)) % 11
    second = 0 if remainder < 2 else 11 - remainder
    return str(first) + str(second)


def test_numeric_result_equals_the_classic_calculation():
    generator = random.Random(2026)
    bases = [
        "".join(generator.choice("0123456789") for _ in range(12))
        for _ in range(1000)
    ]

    for base in bases:
        assert cnpj_check_digits(base) == classic_numeric_check_digits(base)
