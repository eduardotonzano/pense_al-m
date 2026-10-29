from __future__ import annotations

from credit_assets.market_events import compare, detect


def row(**kw):
    base = {"CNPJ_Emissora": "1", "Codigo_ISIN": "BRAAAAAAAAA1", "Codigo_Identificacao_Certificado": "C1",
            "Data_Referencia": "2026-07-01", "Situacao": "Adimplente", "Classificacao_Risco_Atual": "A.br",
            "Data_Vencimento": "2030-12-18", "Taxa_Juros": "CDI + 1,5000% a.a", "Valor_Certificados": "1000.00",
            "Amortizacoes": "0"}
    base.update(kw)
    return base


def test_no_event_when_nothing_changes():
    assert compare(row(), row(Data_Referencia="2026-08-01")) == []


def test_status_rating_maturity_and_rate_changes():
    assert compare(row(), row(Situacao="Em atraso")) == ["entrou_em_atraso"]
    assert compare(row(Situacao="Em atraso"), row()) == ["saiu_do_atraso"]
    assert compare(row(), row(Classificacao_Risco_Atual="BBB.br")) == ["rating_mudou"]
    assert compare(row(), row(Data_Vencimento="2031-12-18")) == ["vencimento_mudou"]
    assert compare(row(), row(Taxa_Juros="CDI + 2,5% a.a")) == ["taxa_mudou"]


def test_rate_formatting_differences_are_not_events():
    assert compare(row(), row(Taxa_Juros="cdi + 1,5% a.a")) == []
    assert compare(row(), row(Taxa_Juros="CDI  +  1,50% a.a")) == []
    assert compare(row(Taxa_Juros="Pré-fixada 14,4287%"), row(Taxa_Juros="14,43% PRE")) == []
    assert compare(row(Taxa_Juros="CDI + 6,7282% a.a."), row(Taxa_Juros="CDI + 8,3300% a.a.")) == ["taxa_mudou"]
    assert compare(row(Taxa_Juros="Sem remuneração"), row(Taxa_Juros="CDI + 2%")) == []


def test_balance_drop_without_amortization_and_zero_balance():
    assert compare(row(), row(Valor_Certificados="800")) == ["saldo_caiu_sem_amortizacao"]
    assert compare(row(), row(Valor_Certificados="800", Amortizacoes="200")) == []  # explicada pela amortização
    assert compare(row(), row(Valor_Certificados="950")) == []  # abaixo do limite de 10%
    assert compare(row(), row(Valor_Certificados="0")) == ["saldo_zerou"]
    assert compare(row(Valor_Certificados=""), row(Valor_Certificados="0")) == []  # sem saldo anterior


def test_detect_uses_previous_reported_month_and_skips_series_without_isin():
    rows = [
        row(Data_Referencia="2026-05-01"),
        row(Data_Referencia="2026-08-01", Situacao="Em atraso"),  # julho não informado: compara com maio
        row(Codigo_ISIN="", Data_Referencia="2026-07-01"),
        row(Codigo_ISIN="", Data_Referencia="2026-08-01", Situacao="Em atraso"),
        row(Codigo_ISIN="BRBBBBBBBBB1", Data_Referencia="2026-08-01"),  # série nova, sem mês anterior
    ]
    events = detect(rows, "2026-08")
    assert [(e["evento"], e["mes_anterior"]) for e in events] == [("entrou_em_atraso", "2026-05")]
    assert events[0]["antes"] == "Adimplente" and events[0]["depois"] == "Em atraso"
