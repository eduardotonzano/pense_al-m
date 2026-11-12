"""CNPJ numerico ou alfanumerico (IN RFB 2.229/2024, ADR-011).

Copia local da regra canonica da camada compartilhada
(pense_alm.shared.entities.identifiers.normalize_cnpj, na raiz do
repositorio). Este pacote nao importa pense_alm (dependencies = [] no
pyproject.toml), entao mantem a sua copia, como o modulo de Fundos. A
paridade e garantida pelos mesmos vetores de teste (tests/test_cnpj.py).

Regra: tira os espacos das pontas, remove so ponto, barra e hifen (em
qualquer posicao) e poe em maiusculas; exige 14 caracteres ASCII, os 12
primeiros em [0-9A-Z] e os 2 ultimos numericos; recusa sequencia de
caracteres iguais e valida os dois digitos verificadores, com cada
caractere valendo ord(c) - 48. Para CNPJ so numerico o resultado e o do
calculo classico. Nunca completa zeros a esquerda (11 digitos pode ser
CPF). As mensagens de erro nunca repetem o valor recebido.
"""

import re


WEIGHTS_FIRST = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
WEIGHTS_SECOND = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)

_SEPARATORS = str.maketrans("", "", "./-")
_FORMAT = re.compile(r"[0-9A-Z]{12}[0-9]{2}")

FORMAT_MESSAGE = (
    "CNPJ deve ter 14 caracteres: os 12 primeiros em "
    "[0-9A-Z] e os 2 ultimos numericos."
)


def _check_digit(values, weights):
    remainder = sum(
        value * weight
        for value, weight in zip(values, weights)
    ) % 11

    return 0 if remainder < 2 else 11 - remainder


def clean_cnpj(value):
    """Devolve o CNPJ sem mascara e em maiusculas, se tiver o formato.

    Tira os espacos das pontas, remove ponto, barra e hifen e poe em
    maiusculas. Devolve None se o valor nao for texto, nao for ASCII ou
    nao tiver 12 caracteres em [0-9A-Z] seguidos de 2 digitos. Nao confere
    o digito verificador nem a sequencia de caracteres iguais.
    """

    if not isinstance(value, str):
        return None

    candidate = value.strip()

    # isascii antes de upper: o i sem ponto (U+0131) vira "I" em
    # maiusculas e passaria por uma letra ASCII.
    if not candidate.isascii():
        return None

    candidate = candidate.translate(_SEPARATORS).upper()

    if _FORMAT.fullmatch(candidate) is None:
        return None

    return candidate


def normalize_cnpj(value):
    """Devolve o CNPJ canonico (14 caracteres) ou levanta ValueError."""

    if not isinstance(value, str):
        raise ValueError("CNPJ deve ser texto.")

    candidate = clean_cnpj(value)

    if candidate is None:
        raise ValueError(FORMAT_MESSAGE)

    if len(set(candidate)) == 1:
        raise ValueError(
            "CNPJ nao pode possuir todos os caracteres iguais."
        )

    values = [ord(character) - 48 for character in candidate[:12]]
    first = _check_digit(values, WEIGHTS_FIRST)
    second = _check_digit(values + [first], WEIGHTS_SECOND)

    if candidate[12:] != f"{first}{second}":
        raise ValueError("CNPJ com digito verificador invalido.")

    return candidate
