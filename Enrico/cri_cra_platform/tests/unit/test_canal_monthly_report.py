from datetime import date

from credit_assets.canal_monthly_report import as_rows, parse_fundos, parse_garantias, parse_words, status
from credit_assets.canal_portal import competencia, is_live, monthly_reports, parse_catalog_page, parse_documents


def w(x, y, text):
    return (x, y, x + 5 * len(text), y + 8, text, 0, 0, 0)


def words_line(y, *pairs):
    return [w(x, y, t) for x, t in pairs]


# modelo atual (2025 em diante): quadro GARANTIAS em colunas e, à direita, os saldos das contas
GARANTIAS = (
    words_line(415, (20, "GARANTIAS"), (517, "SALDO"), (546, "DE"), (558, "CONTA"), (587, "E"), (594, "APLICAÇÕES"),
               (645, "VINCULADAS"))
    + words_line(437, (206, "Limite"), (230, "Mínimo"), (293, "Razão"), (315, "(%)"), (377, "Status"), (517, "Saldos"),
                 (541, "finais"), (562, "em:"), (587, "31/03/2026"), (666, "Aplicação/Fundo:"))
    + words_line(448, (29, "Fundo"), (51, "de"), (61, "Reserva*"), (208, "R$"), (218, "400.000,00"), (304, "N/A"),
                 (355, "Desenquadrado"), (517, "Centralizada:"), (587, "R$"), (597, "6.352.410,13"), (666, "Reserva"),
                 (744, "R$"), (754, "460.675,14"))
    + words_line(459, (29, "Fundo"), (51, "de"), (61, "Despesa"), (210, "R$"), (220, "35.000,00"), (304, "N/A"),
                 (369, "Enquadrado"), (666, "Despesas"), (744, "R$"), (754, "28.969,63"))
    + words_line(468, (27, "ILG"), (218, "1,30"), (295, "1,37"), (360, "Enquadrado"), (666, "Fundo"), (688, "de"),
                 (698, "Obras"), (744, "R$"), (754, "51.617.247,78"))
    + words_line(477, (29, "LTV"), (224, "0,75"), (369, "Enquadrado"))
    + words_line(490, (29, "*AGT"), (52, "convocada"))
    + words_line(560, (60, "Série"), (85, "3"), (200, "Série"), (225, "1"))
)

RESUMO = (
    words_line(54, (18, "Relatório"), (59, "Mensal"))
    + words_line(63, (18, "2ªE"), (43, "CRI"), (59, "Gafisa"), (92, "03/2026"))
    + words_line(123, (27, "Código"), (51, "CETIP"), (205, "22E1273339"), (296, "23E0884935"), (373, "23E3611801"),
                 (450, "N/A"))
    + words_line(132, (27, "Código"), (51, "ISIN"), (200, "BRCASCCRI018"), (290, "NÃO"), (310, "TEM"),
                 (368, "BRCASCCRI3S4"), (450, "N/A"))
    + words_line(214, (27, "Data"), (43, "emissão"), (207, "31/05/2022"), (296, "02/05/2023"))
    + words_line(378, (27, "Saldo"), (46, "devedor"), (74, "após"), (91, "pagamento"), (202, "R$"), (212, "107.797.092,03"),
                 (292, "R$"), (302, "1.171,71"), (383, "R$"), (393, "28.158.472,26"), (461, "R$"), (470, "1.129,32"),
                 (538, "R$"), (548, "16.154.661,06"), (615, "R$"), (625, "1.076,98"), (714, "R$"), (724, "0,00"),
                 (791, "R$"), (801, "0,00"))
)


def test_garantias_columns_footnotes_and_balances():
    items = parse_garantias([[], GARANTIAS])
    checked = [i for i in items if i.grupo_tipo != "Saldo de conta"]
    assert [(i.grupo_tipo, i.item, i.valor_referencia, i.valor_apurado, i.situacao) for i in checked] == [
        ("Fundo", "Fundo de Reserva", "R$ 400.000,00", "N/A", "nao_atendido"),
        ("Fundo", "Fundo de Despesa", "R$ 35.000,00", "N/A", "atendido"),
        ("Índice", "ILG", "1,30", "1,37", "atendido"),
        ("Índice", "LTV", "0,75", "", "atendido"),
    ]
    reserve = checked[0]
    assert reserve.condicao_apurada == "Desenquadrado (*AGT convocada)"  # nota do asterisco vai junto
    assert (reserve.condicao_referencia, reserve.data_verificacao, reserve.pagina) == ("Limite Mínimo", "31/03/2026", 2)
    assert reserve.grupo == "SALDO DE CONTA E APLICAÇÕES VINCULADAS"
    balances = {(i.item, i.valor_apurado) for i in items if i.grupo_tipo == "Saldo de conta"}
    assert balances == {("Centralizada", "R$ 6.352.410,13"), ("Reserva", "R$ 460.675,14"), ("Despesas", "R$ 28.969,63"),
                        ("Fundo de Obras", "R$ 51.617.247,78")}
    assert all(i.situacao == "" for i in items if i.grupo_tipo == "Saldo de conta")  # saldo não é pareado com limite


def test_report_series_isin_and_balance_per_series():
    report = parse_words([RESUMO + GARANTIAS], "\nRelatório Mensal\n 2ªE CRI Gafisa 03/2026\nRESUMO\n31/05/2022\n")
    assert report.competencia == "Março/2026"
    assert report.modelo == "garantias"
    assert [(s.cetip, s.isin, s.saldo_devedor) for s in report.series] == [
        ("22E1273339", "BRCASCCRI018", "R$ 107.797.092,03"),
        ("23E0884935", "", "R$ 28.158.472,26"),  # "NÃO TEM" não desloca as colunas
        ("23E3611801", "BRCASCCRI3S4", "R$ 16.154.661,06"),
    ]
    rows = as_rows({"codigo_opea": "2", "codigo_cetip": "23E3611801", "isin": ""}, report)
    assert {(r["isin"], r["cetip_no_relatorio"], r["saldo_devedor"]) for r in rows} == {
        ("BRCASCCRI3S4", "23E3611801", "R$ 16.154.661,06")}
    assert rows[0]["competencia"] == "Março/2026"


def test_old_model_fund_blocks_and_index():
    page = (
        words_line(88, (253, "Fundos"))
        + words_line(108, (49, "Fundo"), (67, "de"), (76, "Despesas"), (276, "jun-24"))
        + words_line(116, (19, "(a)"), (26, "Saldo"), (285, "R$"), (293, "89.415,82"))
        + words_line(125, (19, "(b)"), (26, "Valor"), (41, "Mínimo"), (60, "do"), (68, "Fundo"), (283, "R$"), (291, "59.668,65"))
        + words_line(142, (19, "Situação"), (42, "do"), (51, "Fundo"), (268, "Enquadrado"))
        + words_line(167, (50, "Fundo"), (68, "de"), (77, "Reservas"), (276, "jun-24"))
        + words_line(176, (19, "(a)"), (26, "Saldo"), (283, "R$"), (291, "214.165,04"))
        + words_line(184, (19, "(b)"), (26, "Valor"), (41, "Mínimo"), (60, "do"), (68, "Fundo"), (282, "R$"), (290, "321.869,42"))
        + words_line(201, (19, "Situação"), (42, "do"), (51, "Fundo"), (263, "Desenquadrado"))
        + words_line(235, (94, "Índice"), (111, "de"), (119, "Liquidez"), (143, "de"), (151, "Garantias"), (276, "jun-24"))
        + words_line(244, (19, "(a)"), (26, "Valor"), (40, "Presente"), (277, "R$"), (286, "4.949.162,80"))
        + words_line(321, (19, "(j)"), (25, "Índice"), (42, "(e)/(i)"), (298, "165,4%"))
        + words_line(329, (19, "Situação"), (42, "do"), (51, "Índice"), (268, "Enquadrado"))
    )
    items = parse_fundos([[], [], [], page])
    assert [(i.grupo_tipo, i.item, i.valor_referencia, i.condicao_referencia, i.valor_apurado, i.situacao,
             i.data_verificacao, i.pagina) for i in items] == [
        ("Fundo", "Fundo de Despesas", "R$ 59.668,65", "Valor Mínimo do Fundo", "R$ 89.415,82", "atendido", "jun-24", 4),
        ("Fundo", "Fundo de Reservas", "R$ 321.869,42", "Valor Mínimo do Fundo", "R$ 214.165,04", "nao_atendido", "jun-24", 4),
        ("Índice", "Índice de Liquidez de Garantias", "", "", "165,4%", "atendido", "jun-24", 4),
    ]
    text = "Relatório Mensal\nRelatório Mensal da 1ª Série da 99ª Emissão - CRI MAGEN\njunho de 2024\n07/05/2024"
    assert parse_words([[], [], [], page], text).competencia == "Junho/2024"


def test_report_without_items_gives_placeholder_row():
    report = parse_words([RESUMO], "Relatório Mensal\n 2ªE CRI Gafisa 03/2026\n")
    rows = as_rows({"codigo_opea": "2", "codigo_cetip": "22E1273339", "isin": ""}, report)
    assert [r["item"] for r in rows] == ["(sem monitoramentos)"]
    assert rows[0]["isin"] == "BRCASCCRI018"


def test_status_normalization():
    assert [status(s) for s in ("Enquadrado", "DESENQUADRADO", "N/A", "", "Em análise")] == [
        "atendido", "nao_atendido", "nao_se_aplica", "", "outro"]


CATALOG = """
<a class="emissao-bloco-home grid-4" href="https://www.canalsecuritizadora.com.br/emissao/24j2139130">
  <div class="emissao-home-header"><div class="emissao-home-header-info">24J2139130 BRGD S.A.</div></div>
  <div class="emissao-home-line"><label>Emissão</label><span>121</span></div>
  <div class="emissao-home-line"><label>Série</label><span>1</span></div>
  <div class="emissao-home-line"><label>Categoria</label><span>CRI</span></div>
  <div class="emissao-home-line"><label>Volume emitido</label><span>R$ <span class="valor">106000000.00</span></span></div>
  <div class="emissao-home-line"><label>Data Vencimento</label><span>10/10/2035</span></div>
</a>
<nav><a href='https://www.canalsecuritizadora.com.br/emissoes?p=2'>2</a>
<a href='https://www.canalsecuritizadora.com.br/emissoes?p=22' aria-label='Last'>&raquo;</a></nav>
"""

DOCUMENTS = """
<a href="https://www.canalsecuritizadora.com.br/uploads/emissoes_documentos/14812/Relatório investidor 121ªE CRI BRGD 05_2026.pdf" class="grid-6" download>
  <div class="download-bl-tit">Relatório Mensal Maio/2026</div></a>
<a href="https://www.canalsecuritizadora.com.br/uploads/emissoes_documentos/14220/Relatório investidor 121ªE CRI BRGD 04_2026.pdf" class="grid-6" download>
  <div class="download-bl-tit">Relatório Mensal Abril/2026</div></a>
<a href="https://www.canalsecuritizadora.com.br/uploads/emissoes_documentos/14900/Relatório investidor 121ªE CRI BRGD 05_2026 v2.pdf" class="grid-6" download>
  <div class="download-bl-tit">Relatório Mensal Maio/2026</div></a>
<a href="https://www.canalsecuritizadora.com.br/uploads/emissoes_documentos/5565/R-922-25_E121 Forgreen IV 06.2025.pdf" class="grid-6" download>
  <div class="download-bl-tit">Demonstrações Financeiras 06/2025</div></a>
<a href="https://www.canalsecuritizadora.com.br/uploads/emissoes_documentos/9000/CRI Blend 173ªE - Relatório Investidor - 12.2025.pdf" class="grid-6" download>
  <div class="download-bl-tit">Documento</div></a>
"""


def test_catalog_cards_and_last_page():
    cards, last = parse_catalog_page(CATALOG)
    assert last == 22
    assert cards == [{"codigo_cetip": "24J2139130", "devedor": "BRGD S.A.", "emissao": "121", "serie": "1",
                      "categoria": "CRI", "volume_emitido": "R$ 106000000.00", "data_vencimento": "10/10/2035"}]
    assert is_live(cards[0], date(2026, 11, 3)) and not is_live(cards[0], date(2035, 10, 11))


def test_documents_url_encoding_competencia_and_order():
    docs = parse_documents(DOCUMENTS)
    first = next(d for d in docs if d["document_id"] == 14812)
    assert first["url"].endswith("/14812/Relat%C3%B3rio%20investidor%20121%C2%AAE%20CRI%20BRGD%2005_2026.pdf")
    assert first["competencia"] == "2026-05"
    assert next(d for d in docs if d["document_id"] == 9000)["competencia"] == "2025-12"  # pelo nome do arquivo
    recent = monthly_reports(docs, date(2026, 11, 3), max_age_days=365)
    # na mesma competência, o upload mais novo primeiro; DF e relatório de mais de 365 dias ficam de fora
    assert [d["document_id"] for d in recent] == [14900, 14812, 14220, 9000]
    # a idade conta do último dia da competência: abril/2026 (30/04) já passa de 180 dias em 03/11/2026
    assert [d["document_id"] for d in monthly_reports(docs, date(2026, 11, 3), max_age_days=180)] == [14900, 14812]
    assert competencia("Relatório Mensal Março/2026") == "2026-03"
    assert competencia("", "https://x/uploads/emissoes_documentos/1/Relatorio%20investidor_06_2024_99%C2%AAE.pdf") == "2024-06"
