"""CNPJs fictícios para os testes do CRI/CRA.

Mesma API e mesmas raízes de tests/shared/cnpj_amostras.py, na raiz do
repositório (ADR-011), mas sem importar nada de lá: o CRI/CRA é independente.
Nada aqui é dado real. As raízes 9999999n + 9999 e ZZZZZZZn + ZZZZ não parecem
raiz de empresa. DV válido não prova que o CNPJ não exista; sem rede não há como
conferir na Receita. O CPF fictício (99999999999) tem DV inválido, então não é
CPF de ninguém.

O cálculo do DV aqui é independente do código de produção (credit_assets.cnpj),
de propósito: os testes conferem um contra o outro. Os pesos são gerados como
2, 3, ..., 9, 2, 3, ... a partir da direita, em vez de tabelados.
"""

_CARACTERES_DA_BASE = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _pesos(quantidade):
    return [2 + (posicao % 8) for posicao in range(quantidade)][::-1]


def montar_cnpj(base12):
    """Devolve a base de 12 caracteres seguida dos 2 DVs (IN RFB 2.229/2024)."""

    if len(base12) != 12 or any(
        caractere not in _CARACTERES_DA_BASE for caractere in base12
    ):
        raise ValueError("A base deve ter 12 caracteres em [0-9A-Z].")

    valores = [ord(caractere) - 48 for caractere in base12]

    for _ in range(2):
        resto = sum(
            valor * peso
            for valor, peso in zip(valores, _pesos(len(valores)))
        ) % 11
        valores.append(0 if resto < 2 else 11 - resto)

    return base12 + str(valores[12]) + str(valores[13])


def cnpj_ficticio(n=1, *, alfanumerico=False):
    """CNPJ fictício sem máscara, com DV válido; n vai de 0 a 9."""

    if not 0 <= n <= 9:
        raise ValueError("n vai de 0 a 9.")

    if alfanumerico:
        return montar_cnpj("ZZZZZZZ" + str(n) + "ZZZZ")

    return montar_cnpj("9999999" + str(n) + "9999")


def com_mascara(cnpj):
    """Aplica a máscara completa NN.NNN.NNN/NNNN-NN."""

    return (
        cnpj[:2] + "." + cnpj[2:5] + "." + cnpj[5:8]
        + "/" + cnpj[8:12] + "-" + cnpj[12:]
    )


def dv_errado(cnpj):
    """O mesmo CNPJ com o último dígito verificador trocado."""

    return cnpj[:13] + str((int(cnpj[13]) + 1) % 10)


CNPJ_1 = cnpj_ficticio(1)
CNPJ_2 = cnpj_ficticio(2)
CNPJ_3 = cnpj_ficticio(3)
CNPJ_4 = cnpj_ficticio(4)
CNPJ_5 = cnpj_ficticio(5)
CNPJ_6 = cnpj_ficticio(6)
CNPJ_7 = cnpj_ficticio(7)

CNPJ_ALFA_1 = cnpj_ficticio(1, alfanumerico=True)
CNPJ_ALFA_2 = cnpj_ficticio(2, alfanumerico=True)

# Exemplo de referência do CNPJ alfanumérico divulgado pela Receita.
CNPJ_RECEITA = "12ABC34501DE35"
CNPJ_RECEITA_MASCARA = "12.ABC.345/01DE-35"

CPF_FICTICIO = "99999999999"
CPF_FICTICIO_MASCARA = "999.999.999-99"
