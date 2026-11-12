from __future__ import annotations

import re

from credit_assets.cnpj import clean_cnpj
from credit_assets.cnpj import normalize_cnpj as _canonical_cnpj

# Valor sem letra: so digitos, ponto, barra, hifen e espaco, como antes da regra
# alfanumerica. Outros simbolos reprovam em vez de serem descartados.
_NUMERIC_CNPJ_TEXT = re.compile(r"[\d.\-/\s]*")

def only_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")

def normalize_cnpj(value: object) -> str | None:
    """CNPJ canonico (14 caracteres, numerico ou alfanumerico, maiusculas) ou None.

    A regra e a de credit_assets/cnpj.py (IN RFB 2.229/2024, ADR-011): formato,
    caracteres iguais e os dois digitos verificadores. Valor com letra vai direto
    para ela. Valor sem letra aceita tambem espacos entre os digitos, como antes;
    tirados os separadores, passa pela mesma regra, que exige ASCII. Nunca corrige
    nem completa zeros. CPF (11 digitos) reprova. Valor que nao e texto da None.
    """
    if not isinstance(value, str):
        return None
    if any(character.isalpha() for character in value):
        candidate = value
    elif _NUMERIC_CNPJ_TEXT.fullmatch(value):
        candidate = only_digits(value)
    else:
        return None
    try:
        return _canonical_cnpj(candidate)
    except ValueError:
        return None

def is_valid_cnpj(value: object) -> bool:
    """True quando normalize_cnpj devolve um CNPJ."""
    return normalize_cnpj(value) is not None

def format_cnpj(cnpj: str) -> str:
    """NN.NNN.NNN/NNNN-NN, o formato do ativos_piloto.csv, tambem com letras.

    Recebe so os 14 caracteres canonicos (saida de normalize_cnpj); a mensagem de
    erro nao repete o valor.
    """
    if not isinstance(cnpj, str) or clean_cnpj(cnpj) != cnpj:
        raise ValueError(
            "CNPJ precisa ter 14 caracteres canonicos: 12 em [0-9A-Z] e 2 digitos, sem mascara."
        )
    return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"

def validate_asset_type(value: str) -> str:
    normalized = value.strip().upper()
    if normalized not in {"CRI", "CRA"}:
        raise ValueError(f"Tipo de ativo inválido: {value}")
    return normalized
