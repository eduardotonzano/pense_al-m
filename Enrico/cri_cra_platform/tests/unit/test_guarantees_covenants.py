import pytest

from credit_assets.guarantees_covenants import extract, normalize_operator


@pytest.mark.parametrize(("raw", "expected"), [
    ("igual ou inferior a", "<="), ("não poderá ser superior a", "<="), ("no máximo,", "<="),
    ("igual ou superior a", ">="), ("não inferior a", ">="), ("no mínimo,", ">="), ("pelo menos", ">="),
    ("superior a", ">"), ("inferior a", "<"), ("≤", "<="),
])
def test_operator_reading(raw, expected):
    assert normalize_operator(raw) == expected


def by_item(items):
    return {i.item: i for i in items}


def test_guarantees_present_negated_and_cited():
    text = ("8.1 Os CRI contarão com a Alienação Fiduciária de Imóvel e a Cessão Fiduciária de Recebíveis. "
            "8.2 A Alienação Fiduciária de Imóvel recai sobre a matrícula 22.139. A Cessão Fiduciária de Recebíveis "
            "corresponde a 30% dos aluguéis. Os CRI não contarão com garantia flutuante da Emissora. "
            "(xxiv) Coobrigação da Emissora. Não há.")
    items = by_item(extract([("722251", 37, text, False)]))
    assert items["alienacao_fiduciaria_imovel"].situacao == "presente"
    assert items["cessao_fiduciaria"].situacao == "presente"
    assert items["garantia_flutuante"].situacao == "negada"
    assert items["coobrigacao"].situacao == "negada"
    assert "fianca" not in items


def test_other_issues_annex_of_the_trustee_is_ignored():
    annex = ("Emissão: 316 Adimplente Garantias: Fiança, Penhor de Ações\n"
             "Emissão: 317 Adimplente Garantias: Hipoteca, Aval\nEmissão: 318 Inadimplente Garantias: Fiança")
    assert extract([("722251", 127, annex, False)]) == []


def test_covenant_limit_operator_and_page():
    text = ("7.2 Índices financeiros. (b) a razão entre a Dívida Líquida e o EBITDA do respectivo ano deverá ser "
            "igual ou inferior a 3,0x, apurada anualmente. A Devedora deverá assegurar o loan to value de, no máximo, "
            "60% (sessenta por cento).")
    items = by_item(extract([("1040836", 68, text, False)]))
    debt = items["divida_liquida_ebitda"]
    assert (debt.situacao, debt.operador, debt.limite, debt.unidade, debt.pagina) == ("com_limite", "<=", "3.0", "x", 68)
    assert debt.periodicidade == "anualmente"
    ltv = items["ltv"]
    assert (ltv.operador, ltv.limite, ltv.unidade) == ("<=", "60", "%")


def test_clause_numbers_and_money_do_not_cut_the_sentence():
    text = "8.3.1. O LTV não poderá ser superior a 60% enquanto o saldo for de R$ 1.250.000,00 ou mais."
    ltv = by_item(extract([("1", 38, text, False)]))["ltv"]
    assert ltv.limite == "60" and ltv.operador == "<="
