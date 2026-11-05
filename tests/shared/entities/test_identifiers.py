"""Testes de identificadores de entidade."""

import random

import pytest

from pense_alm.shared.entities import (
    DataProvenance,
    EntityIdentifier,
    IdentifierType,
    IdentifierValidationError,
    SourceType,
    normalize_cnpj,
    normalize_identifier,
)

from ..cnpj_amostras import (
    CNPJ_1,
    CNPJ_ALFA_1,
    CNPJ_RECEITA,
    CNPJ_RECEITA_MASCARA,
    CPF_FICTICIO,
    CPF_FICTICIO_MASCARA,
    cnpj_ficticio,
    com_mascara,
    dv_errado,
    montar_cnpj,
)


@pytest.fixture
def bacen_provenance():
    return DataProvenance(
        source_type=SourceType.BACEN,
        source_name="Banco Central do Brasil",
    )


def test_cnpj_is_normalized(bacen_provenance):
    identifier = EntityIdentifier(
        identifier_type=IdentifierType.CNPJ,
        value=com_mascara(CNPJ_1),
        provenance=bacen_provenance,
        is_primary=True,
    )

    assert identifier.value == CNPJ_1
    assert identifier.canonical_key == f"cnpj:{CNPJ_1}"


def test_non_cnpj_identifier_is_uppercase(bacen_provenance):
    identifier = EntityIdentifier(
        identifier_type=IdentifierType.BACEN_CODE,
        value="  abc123  ",
        provenance=bacen_provenance,
    )

    assert identifier.value == "ABC123"


def test_empty_identifier_is_rejected(bacen_provenance):
    with pytest.raises(IdentifierValidationError):
        EntityIdentifier(
            identifier_type=IdentifierType.CVM_CODE,
            value=" ",
            provenance=bacen_provenance,
        )


@pytest.mark.parametrize(
    "value",
    [
        "123",
        "11.111.111/1111-11",
    ],
)
def test_invalid_cnpj_is_rejected(value):
    with pytest.raises(IdentifierValidationError):
        normalize_cnpj(value)


def test_identifier_is_immutable(bacen_provenance):
    identifier = EntityIdentifier(
        identifier_type=IdentifierType.BACEN_CODE,
        value="123",
        provenance=bacen_provenance,
    )

    with pytest.raises(AttributeError):
        identifier.value = "456"


# CNPJ alfanumerico (IN RFB 2.229/2024, ADR-011).


@pytest.mark.parametrize(
    "value, expected",
    [
        (CNPJ_1, CNPJ_1),
        (com_mascara(CNPJ_1), CNPJ_1),
        (CNPJ_ALFA_1, CNPJ_ALFA_1),
        (com_mascara(CNPJ_ALFA_1), CNPJ_ALFA_1),
        (CNPJ_RECEITA, CNPJ_RECEITA),
        (CNPJ_RECEITA_MASCARA, CNPJ_RECEITA),
    ],
    ids=[
        "numerico",
        "numerico-mascara",
        "alfanumerico",
        "alfanumerico-mascara",
        "receita",
        "receita-mascara",
    ],
)
def test_cnpj_accepted_forms(value, expected):
    assert normalize_cnpj(value) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        (CNPJ_ALFA_1.lower(), CNPJ_ALFA_1),
        (com_mascara(CNPJ_ALFA_1).lower(), CNPJ_ALFA_1),
        (CNPJ_RECEITA_MASCARA.lower(), CNPJ_RECEITA),
        ("  " + CNPJ_RECEITA + " ", CNPJ_RECEITA),
    ],
    ids=[
        "minuscula",
        "minuscula-mascara",
        "receita-minuscula-mascara",
        "espacos-em-volta",
    ],
)
def test_cnpj_lowercase_and_surrounding_spaces_are_normalized(
    value,
    expected,
):
    assert normalize_cnpj(value) == expected


def test_cnpj_partial_mask_is_accepted():
    # Diferenca registrada no ADR-011: a camada remove ponto, barra e
    # hifen em qualquer posicao; o fundos.cnpj recusa mascara parcial.
    assert normalize_cnpj("12.ABC.34501DE-35") == CNPJ_RECEITA


@pytest.mark.parametrize(
    "value",
    [
        dv_errado(CNPJ_1),
        dv_errado(CNPJ_ALFA_1),
        "12ABC34501DE36",
    ],
    ids=["numerico", "alfanumerico", "receita"],
)
def test_cnpj_invalid_check_digit_is_rejected(value):
    with pytest.raises(
        IdentifierValidationError,
        match="digito verificador",
    ):
        normalize_cnpj(value)


@pytest.mark.parametrize(
    "value",
    [
        "12ABC34501D\u00c935",
        "12ABC34501D\u00c735",
        "12ABC34501D*35",
        "12ABC34501D_35",
        "12ABC 34501DE35",
        "\uff112ABC34501DE35",
        "\u06612ABC34501DE35",
        "12\u0131BC34501DE10",
    ],
    ids=[
        "acento",
        "cedilha",
        "simbolo",
        "sublinhado",
        "espaco-interno",
        "digito-unicode-largo",
        "digito-unicode-arabe",
        "letra-que-vira-ascii-em-maiuscula",
    ],
)
def test_cnpj_characters_outside_the_alphabet_are_rejected(value):
    with pytest.raises(
        IdentifierValidationError,
        match="14 caracteres",
    ):
        normalize_cnpj(value)


def test_dotless_i_vector_would_be_valid_with_ascii_i():
    # Garante que o vetor acima so falha pelo caractere nao ASCII.
    assert normalize_cnpj("12IBC34501DE10") == "12IBC34501DE10"


@pytest.mark.parametrize(
    "value",
    [
        "12ABC34501DE3A",
        "12.ABC.345/01DE-3A",
        "12ABC34501DEA5",
    ],
    ids=["ultimo", "ultimo-mascara", "penultimo"],
)
def test_cnpj_letter_in_check_digit_positions_is_rejected(value):
    with pytest.raises(
        IdentifierValidationError,
        match="14 caracteres",
    ):
        normalize_cnpj(value)


def _valid_with_leading_zeros(zeros):
    full = montar_cnpj("0" * zeros + "999999199999"[: 12 - zeros])
    return full, full[zeros:]


@pytest.mark.parametrize(
    "value",
    [
        _valid_with_leading_zeros(3)[1],
        _valid_with_leading_zeros(1)[1],
        CNPJ_1 + "5",
    ],
    ids=["11-caracteres", "13-caracteres", "15-caracteres"],
)
def test_cnpj_with_wrong_length_is_rejected_and_never_padded(value):
    with pytest.raises(
        IdentifierValidationError,
        match="14 caracteres",
    ):
        normalize_cnpj(value)


def test_short_vectors_are_valid_cnpj_with_leading_zeros():
    # Os vetores de 11 e 13 caracteres so falham por nao serem
    # completados com zeros.
    for zeros in (1, 3):
        full, short = _valid_with_leading_zeros(zeros)

        assert normalize_cnpj(full) == full
        assert len(short) == 14 - zeros


def test_cnpj_all_equal_characters_are_rejected_even_with_valid_dv():
    assert montar_cnpj("000000000000") == "00000000000000"

    with pytest.raises(
        IdentifierValidationError,
        match="iguais",
    ):
        normalize_cnpj("00000000000000")


@pytest.mark.parametrize(
    "value",
    [CPF_FICTICIO, CPF_FICTICIO_MASCARA],
    ids=["cpf", "cpf-mascara"],
)
def test_cpf_is_rejected(value):
    with pytest.raises(IdentifierValidationError):
        normalize_cnpj(value)


@pytest.mark.parametrize(
    "value",
    [None, 99999991999904, b"99999991999904"],
    ids=["none", "inteiro", "bytes"],
)
def test_cnpj_that_is_not_text_is_rejected(value):
    with pytest.raises(
        IdentifierValidationError,
        match="texto",
    ):
        normalize_cnpj(value)


@pytest.mark.parametrize(
    "value",
    ["", "   "],
    ids=["vazio", "so-espacos"],
)
def test_empty_cnpj_is_rejected(value):
    with pytest.raises(IdentifierValidationError):
        normalize_cnpj(value)


def test_cnpj_error_messages_never_repeat_the_value():
    values = (
        dv_errado(CNPJ_1),
        dv_errado(CNPJ_ALFA_1),
        com_mascara(dv_errado(CNPJ_1)),
        "12ABC34501DE3A",
        "12ABC34501D*35",
        CPF_FICTICIO,
        "00000000000000",
    )

    for value in values:
        with pytest.raises(IdentifierValidationError) as error:
            normalize_cnpj(value)

        message = str(error.value)

        assert value not in message
        assert value.replace(".", "").replace("/", "").replace(
            "-", ""
        ) not in message


def test_normalize_identifier_accepts_alphanumeric_cnpj():
    assert normalize_identifier(
        IdentifierType.CNPJ,
        " 12.abc.345/01de-35 ",
    ) == CNPJ_RECEITA


def test_alphanumeric_identifier_canonical_key(bacen_provenance):
    identifier = EntityIdentifier(
        identifier_type=IdentifierType.CNPJ,
        value=com_mascara(CNPJ_ALFA_1).lower(),
        provenance=bacen_provenance,
    )

    assert identifier.value == CNPJ_ALFA_1
    assert identifier.canonical_key == f"cnpj:{CNPJ_ALFA_1}"


def _classic_numeric_check_digits(base12):
    """Calculo classico do CNPJ numerico, escrito aqui so para comparar."""

    digits = [int(character) for character in base12]
    first_weights = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    second_weights = [6] + first_weights

    remainder = sum(
        d * w for d, w in zip(digits, first_weights)
    ) % 11
    first = 0 if remainder < 2 else 11 - remainder

    remainder = sum(
        d * w for d, w in zip(digits + [first], second_weights)
    ) % 11
    second = 0 if remainder < 2 else 11 - remainder

    return f"{first}{second}"


def test_numeric_cnpj_follows_the_classic_calculation():
    generator = random.Random(2026)

    for _ in range(1000):
        base = "".join(
            generator.choice("0123456789") for _ in range(12)
        )
        cnpj = base + _classic_numeric_check_digits(base)

        if len(set(cnpj)) == 1:
            continue

        assert normalize_cnpj(cnpj) == cnpj
        assert montar_cnpj(base) == cnpj


def test_test_helper_reproduces_the_receita_example():
    assert montar_cnpj("12ABC34501DE") == CNPJ_RECEITA


def test_test_helper_and_production_code_agree():
    # Os dois calculos sao independentes (tests/shared/cnpj_amostras.py
    # e pense_alm.shared.entities.identifiers).
    for n in range(10):
        for alfanumerico in (False, True):
            cnpj = cnpj_ficticio(n, alfanumerico=alfanumerico)

            assert normalize_cnpj(cnpj) == cnpj
            assert normalize_cnpj(com_mascara(cnpj)) == cnpj

            with pytest.raises(IdentifierValidationError):
                normalize_cnpj(dv_errado(cnpj))
