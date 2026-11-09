from datetime import date

from credit_assets.leverage_monthly_report import as_rows, parse_text, status
from credit_assets.leverage_portal import display_label, live_emissions, monthly_reports, recent_enough

FOOTER = ["       CERTIFICADO DE RECEBÍVEIS IMOBILIÁRIOS - BTLA", "Página 1 de 3"]
COVER = [
    "\xa0\xa0RELATÓRIO\xa0MENSAL\xa0DE\xa0ACOMPANHAMENTO", "Setembro\xa0de\xa02026", "Características Gerais da Emissão",
    "Série", "Código IF", "Subordinação", "Valor Total da Oferta",
    "1ª", "26G2474440", "Sênior", "75.000.000",
    "2ª", "-", "-", "-",
    "3ª", "26G2474576", "Sênior", "75.000.000",
    "Pagamento aos Investidores",
]
FUND_HEAD = ["Saldo Inicial", "Rendimento (+)", "Resgate (-)", "Recomposição (+)", "Saldo Final"]
PAGE2 = [
    "Saldo Devedor", "Quantidade", "Preço Unitário", "Saldo Devedor",
    "1ª", "75.000", "999,62864926", "74.972.148,69", "2ª", "-", "-", "-", "3ª", "75.000", "1.004,65", "75.348.895,75",
    "Fundo de Reserva", "Itaú RF Referenciado DI Grau de Investimento", *FUND_HEAD, "Saldo Mínimo", "Situação",
    "R$", "1.927.544", "14.632", "(1.253.590)", "0", "688.586", "3.682.650", "Desenquadrado",
    # fundo sem saldo mínimo nem situação: não é monitorado
    "Fundo de Obra", "Itaú RF Referenciado DI Grau de Investimento", *FUND_HEAD, "Remanescente de Obra",
    "R$", "0", "0", "0", "0", "0", "0",
    "Fundo de Reserva Tamboré", "Itaú Index Simples Selic RF FICFI", *FUND_HEAD, "Saldo Mínimo", "Situação",
    "R$", "662.981", "10.940", "(286.259)", "786.693", "1.174.354", "1.188.770", "Enquadrado",
]
PAGE3 = [
    "Loan to Value (LTV) - LTV", "Apurado", "Máximo", "Situação", "Variáveis para Cálculo:", "  Saldo Devedor dos CRI",
    "  Valor de Mercado da Fração Ideal do Imóvel", ".", "-", "53%", "Não Apurado", "nan", "R$ 150.321.044", "-",
    "Índice de Cobertura do Serviço da Dívida (ICSD) - ICSD", "Apurado", "Mínimo", "Situação",
    "Variáveis para Cálculo:", "  Recebimento de Aluguel Mensal", "  Serviço da Dívida do CRI", ".", "167%", "120%",
    "Enquadrado", "nan", "R$ 2.076.902", "R$ 1.247.021",
    # nome com "Mínimo" não é título de coluna
    "Fluxo Mínimo - FM", "Apurado", "Mínimo", "Situação", "Variáveis para Cálculo:", "PMT Ordinário", ".", "126%",
    "105%", "Enquadrado", "nan", "R$ 252.142",
]


def report():
    return parse_text(["\n".join(COVER + FOOTER), "\n".join(PAGE2 + FOOTER), "\n".join(PAGE3 + FOOTER)])


def test_funds_with_minimum_and_indices_with_values_as_in_source():
    parsed = report()
    assert (parsed.competencia, parsed.competencia_mm_aaaa) == ("Setembro/2026", "09/2026")
    assert parsed.series == [("1ª", "26G2474440"), ("3ª", "26G2474576")]
    assert parsed.saldo_devedor == "1ª: 74.972.148,69; 3ª: 75.348.895,75"
    got = [(m.grupo_tipo, m.grupo, m.item, m.valor_referencia, m.condicao_referencia, m.valor_apurado,
            m.condicao_apurada, m.situacao, m.data_verificacao, m.pagina) for m in parsed.monitoramentos]
    assert got == [
        ("Fundo", "Itaú RF Referenciado DI Grau de Investimento", "Fundo de Reserva", "3.682.650", "Mínimo", "688.586",
         "Desenquadrado", "nao_atendido", "09/2026", 2),
        ("Fundo", "Itaú Index Simples Selic RF FICFI", "Fundo de Reserva Tamboré", "1.188.770", "Mínimo", "1.174.354",
         "Enquadrado", "atendido", "09/2026", 2),
        ("Índice", "LTV", "Loan to Value (LTV)", "53%", "Máximo", "-", "Não Apurado", "nao_verificado", "09/2026", 3),
        ("Índice", "ICSD", "Índice de Cobertura do Serviço da Dívida (ICSD)", "120%", "Mínimo", "167%", "Enquadrado",
         "atendido", "09/2026", 3),
        ("Índice", "FM", "Fluxo Mínimo", "105%", "Mínimo", "126%", "Enquadrado", "atendido", "09/2026", 3),
    ]


def test_single_series_layout_and_report_without_monitoring():
    cover = ["RELATÓRIO MENSAL DE ACOMPANHAMENTO", "Setembro de 2026", "Código IF", "Data de Vencimento",
             "26C2473563", "22/02/2036", "Pagamento aos Investidores", "Saldo Devedor", "Quantidade",
             "Preço Unitário", "Saldo Devedor", "R$", "128.803", "1.035,40140068", "133.362.806,61"]
    parsed = parse_text(["\n".join(cover)])
    assert parsed.series == [("única", "26C2473563")]
    assert parsed.saldo_devedor == "133.362.806,61"
    rows = as_rows({"codigo_opea": "62"}, parsed)
    assert [(r["item"], r["situacao"], r["data_verificacao"], r["cetip_no_relatorio"]) for r in rows] == [
        ("(sem monitoramentos)", "", "09/2026", "26C2473563")]


def test_index_headers_in_other_orders_and_repeated_per_project():
    rgfm = ["Razão de Garantia do Fluxo Mensal - RGFM", "RGFM Apurado (Sem Aporte)", "RGFM Apurado (Com Aporte)",
            "Situação", "RGFM Mínimo", "Variáveis para Cálculo:", "Recebimentos", "Aporte", "."]
    page = [
        "Fundo de Reserva", "Itaú RF Referenciado DI Grau de Investimento", *FUND_HEAD, "Saldo Mínimo", "Situação",
        "R$", "2.077.442", "18.813", "(199.329)", "0", "1.896.926", "1.867.595", "Enquadrado",
        "Índice de Subordinação - IS", "IS Apurado", "IS Mínimo", "Situação", "Variáveis para Cálculo:",
        "Saldo CRI Subordinado", "Saldo CRI Sênior", ".", "50%", "50%", "Enquadrado", "nan", "R$ 21.878.632",
        "Parque Jardins", "Saldo Devedor da Carteira - Nominal", "Elegíveis", "R$ 48.101.277",
        *rgfm, "93%", "93%", "Desenquadrado", "120%", "nan", "R$ 387.520", "R$ 0",
        "Cidade Nova", "Saldo Devedor da Carteira - Nominal", "Elegíveis", "R$ 62.501.239",
        *rgfm, "106%", "106%", "Desenquadrado", "120%", "nan", "R$ 702.294", "R$ 0",
        "Razão de Garantia de Fluxo Mensal Sênior - RGFMS", "Apurado - Sem Aporte", "Apurado", "Mínimo", "Situação",
        "Variáveis para Cálculo:", "Crédito", ".", "241%", "241%", "120%", "Enquadrado", "nan", "R$ 434.032",
    ]
    got = [(m.grupo_tipo, m.grupo, m.item, m.valor_referencia, m.condicao_referencia, m.valor_apurado, m.situacao)
           for m in parse_text(["\n".join(COVER), "\n".join(page)]).monitoramentos]
    assert got == [
        ("Fundo", "Itaú RF Referenciado DI Grau de Investimento", "Fundo de Reserva", "1.867.595", "Mínimo",
         "1.896.926", "atendido"),
        ("Índice", "IS", "Índice de Subordinação", "50%", "Mínimo", "50%", "atendido"),
        ("Índice", "RGFM · Parque Jardins", "Razão de Garantia do Fluxo Mensal", "120%", "Mínimo",
         "93% (Sem Aporte); 93% (Com Aporte)", "nao_atendido"),
        ("Índice", "RGFM · Cidade Nova", "Razão de Garantia do Fluxo Mensal", "120%", "Mínimo",
         "106% (Sem Aporte); 106% (Com Aporte)", "nao_atendido"),
        ("Índice", "RGFMS", "Razão de Garantia de Fluxo Mensal Sênior", "120%", "Mínimo", "241% (Sem Aporte); 241% (Apurado)",
         "atendido"),
    ]


def test_old_power_bi_layout_with_status_column():
    page = [
        "Características Gerais da Emissão", "Fundo de Despesa", "R$", "Saldo inicial", "Rendimento (+)", "Resgate (-)",
        "Recomposição (+)", "Saldo final", "Saldo mínimo", "Situação", "64.894", "473", "0", "0", "65.368", "100.000",
        "Desenquadrado", "Power BI Desktop",
        "RGSD Apurado (%)", "junho", "julho", "2026", "135%", "68%",
        "Razão de Garantia do Saldo Devedor - RGSD", "RGSD Apurado", "RGSD Mínimo", "Status", "Variáveis para cálculo:",
        "Saldo Devedor", "Garantia Imobiliária", "Apuração", "68%", "135%", "Desenquadrado", ".", "25.038.794",
        "17.059.874", "Mensal",
    ]
    got = [(m.grupo_tipo, m.grupo, m.item, m.valor_referencia, m.condicao_referencia, m.valor_apurado, m.situacao)
           for m in parse_text(["\n".join(page)]).monitoramentos]
    assert got == [
        ("Fundo", "", "Fundo de Despesa", "100.000", "Mínimo", "65.368", "nao_atendido"),
        ("Índice", "RGSD", "Razão de Garantia do Saldo Devedor", "135%", "Mínimo", "68%", "nao_atendido"),
    ]


def test_status_normalization():
    assert [status(s) for s in ("Enquadrado", "Desenquadrado", "Não Apurado", "Sem referência", "-", "", "Vencido")] == [
        "atendido", "nao_atendido", "nao_verificado", "nao_se_aplica", "", "", "outro"]


def test_portal_helpers_pick_latest_monthly_report_and_live_emissions():
    files = [
        {"id": 2262, "tipo": "Relatorios", "nome_original": "011E_CRI Yvy Supreme-Relatório Mensal-08-2026.pdf",
         "enviado_em": "2026-09-28T20:07:01"},
        {"id": 2100, "tipo": "Relatorios", "nome_original": "011E_CRI Yvy Supreme-Relatório Anual-2025.pdf",
         "enviado_em": "2026-10-30T10:00:00"},
        {"id": 2484, "tipo": "Relatorios", "nome_original": "011E_CRI Yvy Supreme-Relatório Mensal-09-2026.pdf",
         "enviado_em": "2026-10-28T19:41:14"},
        {"id": 2095, "tipo": "Assembleia", "nome_original": "011E_CRI Yvy Supreme-Ata de Assembleia-09-10-2025.pdf",
         "enviado_em": "2026-09-18T17:13:36"},
    ]
    assert [(m, f["id"]) for m, f in monthly_reports(files)] == [("2026-09", 2484), ("2026-08", 2262)]
    assert display_label("2026-09").search("011E_CRI Yvy Supreme - Relatório Mensal - set/2026.pdf")
    assert recent_enough("2026-09", date(2026, 11, 3)) and not recent_enough("2026-04", date(2026, 11, 3))
    emissions = [
        {"emissao_id": 1, "emissao_tipo": "CRI", "detalhes": [{"situacao": "Encerrada"}, {"situacao": "Ativa"}]},
        {"emissao_id": 2, "emissao_tipo": "CRI", "detalhes": [{"situacao": "Não Iniciada"}]},
        {"emissao_id": 3, "emissao_tipo": "Debênture", "detalhes": [{"situacao": "Ativa"}]},
    ]
    assert [e["emissao_id"] for e in live_emissions(emissions)] == [1]
