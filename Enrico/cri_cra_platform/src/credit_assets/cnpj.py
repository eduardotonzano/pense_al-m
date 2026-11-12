"""CNPJ numérico ou alfanumérico (IN RFB 2.229/2024, ADR-011).

Cópia local da regra canônica da camada compartilhada
(pense_alm.shared.entities.identifiers.normalize_cnpj, em <raiz do repositório>/src).
O CRI/CRA não importa pense_alm: a raiz não tem pyproject, e o pytest.ini e o
requirements.txt daqui não a citam. A paridade é conferida em
tests/unit/test_cnpj.py, que compara este módulo com a camada nos mesmos vetores.

Regra: tira os espaços das pontas, remove só ponto, barra e hífen (em qualquer
posição) e põe em maiúsculas; exige 14 caracteres ASCII, os 12 primeiros em
[0-9A-Z] e os 2 últimos numéricos; recusa sequência de caracteres iguais e valida
os dois dígitos verificadores, com cada caractere valendo ord(c) - 48. Para CNPJ
só numérico o resultado é o do cálculo clássico. Nunca completa zeros à esquerda
(11 dígitos pode ser CPF). As mensagens de erro nunca repetem o valor recebido e
são as mesmas da camada.
"""
from __future__ import annotations

import re

WEIGHTS_FIRST = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
WEIGHTS_SECOND = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)

_SEPARATORS = str.maketrans("", "", "./-")
_FORMAT = re.compile(r"[0-9A-Z]{12}[0-9]{2}")

FORMAT_MESSAGE = (
    "CNPJ deve ter 14 caracteres: os 12 primeiros em "
    "[0-9A-Z] e os 2 ultimos numericos."
)


def _check_digit(values: list[int], weights: tuple[int, ...]) -> int:
    remainder = sum(value * weight for value, weight in zip(values, weights)) % 11
    return 0 if remainder < 2 else 11 - remainder


def clean_cnpj(value: object) -> str | None:
    """CNPJ sem máscara e em maiúsculas, se tiver o formato; senão None.

    Tira os espaços das pontas, remove ponto, barra e hífen e põe em maiúsculas.
    Devolve None se o valor não for texto, não for ASCII ou não tiver 12
    caracteres em [0-9A-Z] seguidos de 2 dígitos. Não confere o dígito
    verificador nem a sequência de caracteres iguais.
    """

    if not isinstance(value, str):
        return None

    candidate = value.strip()

    # isascii antes de upper: o i sem ponto (U+0131) vira "I" em maiúsculas e
    # passaria por uma letra ASCII.
    if not candidate.isascii():
        return None

    candidate = candidate.translate(_SEPARATORS).upper()

    if _FORMAT.fullmatch(candidate) is None:
        return None

    return candidate


def normalize_cnpj(value: object) -> str:
    """CNPJ canônico (14 caracteres, maiúsculas) ou ValueError."""

    if not isinstance(value, str):
        raise ValueError("CNPJ deve ser texto.")

    candidate = clean_cnpj(value)

    if candidate is None:
        raise ValueError(FORMAT_MESSAGE)

    if len(set(candidate)) == 1:
        raise ValueError("CNPJ nao pode possuir todos os caracteres iguais.")

    values = [ord(character) - 48 for character in candidate[:12]]
    first = _check_digit(values, WEIGHTS_FIRST)
    second = _check_digit(values + [first], WEIGHTS_SECOND)

    if candidate[12:] != f"{first}{second}":
        raise ValueError("CNPJ com digito verificador invalido.")

    return candidate
