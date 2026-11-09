from __future__ import annotations

from decimal import Decimal

from credit_assets.debtor_exposure import aggregate, format_cnpj, fraction, normalize_cnpj

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
                     "percentual_invalido": 1}
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
