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


TERMO_DOIS_INDICES = """   (xix) não atendimento dos índices financeiros definidos abaixo (“Índices Financeiros”):

          (a) a razão entre o Ativo Circulante e o Passivo Circulante seja igual ou maior que 1,20 (um
                  inteiro e vinte centésimos) (“Índice de Liquidez Corrente”); e/ou

          (b) a razão entre a Dívida Líquida e o EBITDA (“Índice Financeiro de Endividamento”) do
                  respectivo ano deverá ser igual ou inferior a 3,0x.
"""


def test_two_indices_in_one_sentence_keep_their_own_limit():
    covenants = {i.item: i for i in extract([("1040836", 68, TERMO_DOIS_INDICES, False)]) if i.grupo == "covenant"}
    assert (covenants["liquidez_corrente"].operador, covenants["liquidez_corrente"].limite) == (">=", "1.20")
    assert (covenants["divida_liquida_ebitda"].operador, covenants["divida_liquida_ebitda"].limite,
            covenants["divida_liquida_ebitda"].unidade) == ("<=", "3.0", "x")


def test_limit_before_the_name_and_two_names_in_one_clause():
    before = "O índice de endividamento, igual ou inferior a 3,0x, (“Dívida Líquida / EBITDA”) será apurado."
    got = {i.item: i for i in extract([("d", 1, before, False)]) if i.grupo == "covenant"}
    assert got["divida_liquida_ebitda"].limite == "3.0"
    same = "A Dívida Líquida / EBITDA não poderá ser superior a 3,0x e o Índice de Liquidez Corrente não poderá ser inferior a 1,2x."
    got = {i.item: i for i in extract([("d", 1, same, False)]) if i.grupo == "covenant"}
    assert (got["divida_liquida_ebitda"].operador, got["divida_liquida_ebitda"].limite) == ("<=", "3.0")
    assert (got["liquidez_corrente"].operador, got["liquidez_corrente"].limite) == (">=", "1.2")


def test_indicator_without_its_own_limit_does_not_borrow_the_neighbour_limit():
    text = "A Devedora deverá manter o Índice de Liquidez Corrente. A Dívida Líquida / EBITDA não poderá ser superior a 3,0x."
    got = {i.item: i for i in extract([("d", 1, text, False)]) if i.grupo == "covenant"}
    assert got["liquidez_corrente"].situacao == "sem_limite" and got["liquidez_corrente"].limite == ""


def _cov(text):
    return {i.item: i for i in extract([("d", 1, text, False)]) if i.grupo == "covenant"}


def _gar(text):
    return {i.item: i for i in extract([("d", 1, text, False)]) if i.grupo == "garantia"}


def test_number_in_words_and_acronyms_do_not_split_the_clause():
    text = ("(a) a razão entre o Ativo Circulante e o Passivo Circulante seja igual ou maior que 1,00 (um) "
            "(“Índice de Liquidez Corrente”); e/ou (b) a razão entre a Dívida Líquida e o EBITDA deverá ser igual ou "
            "inferior a 3,75x.")
    got = _cov(text)
    assert (got["liquidez_corrente"].operador, got["liquidez_corrente"].limite) == (">=", "1.00")
    assert (got["divida_liquida_ebitda"].operador, got["divida_liquida_ebitda"].limite) == ("<=", "3.75")


def test_negated_for_operator_and_enumerations_between_name_and_limit():
    assert _cov("A Dívida Líquida / EBITDA não for maior que 3,00x.")["divida_liquida_ebitda"].operador == "<="
    ltv = ("O LTV, definido como (i) o saldo devedor dos CRI e (ii) o valor de avaliação dos imóveis, "
           "seja superior a 65%.")
    got = _cov(ltv)["ltv"]
    assert (got.operador, got.limite) == (">", "65")


def test_liquidity_of_guarantees_is_not_current_liquidity():
    assert "liquidez_corrente" not in _cov("13. Índice de Liquidez de Garantias ....... 20")


def test_guarantee_heading_followed_by_negation_is_denied():
    text = "5.1. Garantia Flutuante\n5.1.1. Os CRI não contarão com garantia flutuante da Emissora."
    assert _gar(text)["garantia_flutuante"].situacao == "negada"
    assert _gar("Ausência de coobrigação da Securitizadora: os CRI não contam com coobrigação.")["coobrigacao"].situacao == "negada"


def test_rental_insurance_and_permitted_investments_are_not_guarantees():
    assert "fianca" not in _gar("A locatária contratou Seguro Fiança e Fiança Bancária para o contrato de locação.")
    assert "coobrigacao" not in _gar("aplicações com emissão ou coobrigação de pessoa de baixo risco de crédito")


def test_deadline_in_days_is_not_a_covenant_limit():
    text = ("Caso, em qualquer Data de Apuração, o LTV seja superior a 65% (sessenta e cinco por cento), haverá reforço. "
            "Adicionalmente, a partir da Primeira Verificação do LTV, os titulares poderão solicitar novo laudo "
            "em até 30 (trinta) dias da Data de Verificação.")
    items = by_item(extract([("190673", 34, text, False)]))
    assert (items["ltv"].operador, items["ltv"].limite, items["ltv"].unidade) == (">", "65", "%")
    text = ("Será apurado, em até 5 (cinco) Dias Úteis de antecedência, o Índice de Cobertura. "
            "O Índice de Cobertura deverá ser igual ou superior a 1,30.")
    items = by_item(extract([("258148", 30, text, False)]))
    assert (items["razao_garantia"].operador, items["razao_garantia"].limite) == (">=", "1.30")
