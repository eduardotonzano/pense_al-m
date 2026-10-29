from __future__ import annotations

from credit_assets.termo_values import best, extract, is_lastro_context


def pages(*texts):
    return [(i + 1, t) for i, t in enumerate(texts)]


def test_dates_money_and_quantities_are_normalized():
    cands = extract(pages(
        "5.6.1. Para todos os efeitos e fins legais, a Data de Emissão dos CRA é 21 de setembro de 2022.",
        "5.2.1. A Emissão compreende 100.000 (cem mil) CRA. 5.3.1. Os CRA têm Valor Nominal Unitário de R$ 1.000,00 "
        "(mil reais). 5.4.1. O valor total da Emissão é de R$ 100.000.000,00 (cem milhões de reais)",
        "os CRA vencerão na Data de Vencimento, qual seja, 30 de setembro de 2027, equivalente a 1.836 dias",
    ))
    assert [c.value for c in best(cands, "data_emissao")] == ["2022-09-21"]
    assert [c.value for c in best(cands, "quantidade")] == ["100000"]
    assert [c.value for c in best(cands, "valor_nominal_unitario")] == ["1000.00"]
    assert [c.value for c in best(cands, "valor_total")] == ["100000000.00"]
    assert [c.value for c in best(cands, "data_vencimento")] == ["2027-09-30"]


def test_vencendo_portanto_is_preferred_and_lastro_dates_are_separated():
    cands = extract(pages(
        "as Notas Comerciais Escriturais da 1ª Série terão prazo de 1.827 dias, vencendo, portanto, em 16 de dezembro de 2030",
        "a Data de Vencimento será informada no anexo, 01/01/2040",
        "os CRA da 1ª Série terão prazo de vigência de 1829 dias corridos, vencendo, portanto, em 18 de dezembro de 2030",
        "dias, contados da Data de Emissão, vencendo-se, portanto, em 29 de agosto de 2036 (\"Data de Vencimento dos CRI\")",
    ))
    assert sorted(c.value for c in best(cands, "data_vencimento")) == ["2030-12-18", "2036-08-29"]
    assert [c.value for c in best(cands, "data_vencimento_lastro")] == ["2030-12-16"]


def test_issue_date_takes_the_first_occurrence():
    cands = extract(pages(
        "Data de Emissão: 09 de dezembro de 2020; 14. Local de Emissão",
        "Data de Emissão CRI FORTE 1 309 20/12/2050",
    ))
    assert [c.value for c in best(cands, "data_emissao")] == ["2020-12-09"]


def test_lastro_context():
    assert is_lastro_context("as debêntures terão prazo de 4.381 dias")
    assert not is_lastro_context("os cri desta emissão, lastreados em debêntures, terão prazo; os cri")
    assert not is_lastro_context("sem nada relevante")
