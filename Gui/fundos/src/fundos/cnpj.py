"""CNPJ: normalizar, validar o digito verificador e formatar para exibicao.

Aceita o CNPJ numerico e o alfanumerico (IN RFB 2.229/2024): 12 caracteres
em [0-9A-Z] e 2 digitos verificadores numericos. Cada caractere vale
ord(c) - 48 (algarismos de 0 a 9, letras de A = 17 a Z = 42); para CNPJ so
numerico o resultado e o do calculo classico. Aceitar o alfanumerico e
decisao de implementacao de 27/10/2026, registrada por Eduardo, a confirmar
com o Gui.

Esta normalizacao e uma proposta, nao uma decisao. As mensagens de erro nunca
repetem o valor recebido.
"""

import re


WEIGHTS_FIRST = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
WEIGHTS_SECOND = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)

_BASE = re.compile(r"[0-9A-Z]{12}")
_PLAIN = re.compile(r"[0-9A-Z]{12}[0-9]{2}")
_MASKED = re.compile(
    r"([0-9A-Z]{2})\.([0-9A-Z]{3})\.([0-9A-Z]{3})/([0-9A-Z]{4})-([0-9]{2})"
)
_MISSING_ZEROS = re.compile(r"[0-9]{12,13}")
_CPF_FORMAT = re.compile(r"[0-9]{11}|[0-9]{3}\.[0-9]{3}\.[0-9]{3}-[0-9]{2}")


class InvalidCnpjError(ValueError):
    """O valor nao e um CNPJ valido."""


def _check_digit(values, weights):
    remainder = sum(
        value * weight for value, weight in zip(values, weights)
    ) % 11
    return 0 if remainder < 2 else 11 - remainder


def cnpj_check_digits(base12):
    """Calcula os dois digitos verificadores de uma base de 12 caracteres."""

    if not isinstance(base12, str) or _BASE.fullmatch(base12) is None:
        raise InvalidCnpjError(
            "A base do CNPJ deve ter 12 caracteres em [0-9A-Z]."
        )

    values = [ord(char) - 48 for char in base12]
    first = _check_digit(values, WEIGHTS_FIRST)
    second = _check_digit(values + [first], WEIGHTS_SECOND)

    return str(first) + str(second)


def is_valid_cnpj(value):
    """Indica se o valor ja esta na forma normalizada e tem DV valido."""

    if not isinstance(value, str) or _PLAIN.fullmatch(value) is None:
        return False

    if len(set(value)) == 1:
        return False

    return cnpj_check_digits(value[:12]) == value[12:]


def normalize_cnpj(value, *, allow_missing_leading_zeros=False):
    """Devolve o CNPJ com 14 caracteres, sem mascara e em maiusculas.

    Aceita os 14 caracteres ou a mascara completa NN.NNN.NNN/NNNN-NN (letras
    permitidas nas 12 primeiras posicoes). Com allow_missing_leading_zeros,
    completa com zeros a esquerda so entradas numericas de 12 ou 13 digitos;
    nunca 11 digitos ou menos, que podem ser CPF.
    """

    if not isinstance(value, str):
        raise InvalidCnpjError("O CNPJ deve ser texto.")

    candidate = value.strip()

    if not candidate.isascii():
        raise InvalidCnpjError(
            "CNPJ com caractere fora de [0-9A-Z] e da mascara."
        )

    candidate = candidate.upper()
    masked = _MASKED.fullmatch(candidate)

    if masked is not None:
        candidate = "".join(masked.groups())
    elif (
        allow_missing_leading_zeros
        and _MISSING_ZEROS.fullmatch(candidate) is not None
    ):
        candidate = candidate.zfill(14)

    if _PLAIN.fullmatch(candidate) is None:
        raise InvalidCnpjError(
            "CNPJ fora do formato: 14 caracteres, os 12 primeiros em "
            "[0-9A-Z] e os 2 ultimos numericos, com ou sem a mascara "
            "completa."
        )

    if len(set(candidate)) == 1:
        raise InvalidCnpjError("CNPJ com todos os caracteres iguais.")

    if cnpj_check_digits(candidate[:12]) != candidate[12:]:
        raise InvalidCnpjError("CNPJ com digito verificador invalido.")

    return candidate


def format_cnpj(value):
    """Formata para exibicao: NN.NNN.NNN/NNNN-NN (com letras, se houver)."""

    cnpj = normalize_cnpj(value)

    return (
        cnpj[:2]
        + "."
        + cnpj[2:5]
        + "."
        + cnpj[5:8]
        + "/"
        + cnpj[8:12]
        + "-"
        + cnpj[12:]
    )


def looks_like_cpf(value):
    """Indica se o valor tem formato de CPF (so o formato, sem DV)."""

    return (
        isinstance(value, str)
        and _CPF_FORMAT.fullmatch(value.strip()) is not None
    )
