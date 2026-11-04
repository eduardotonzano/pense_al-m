from datetime import date

from credit_assets.vert_monthly_report import competencia_from_date, parse_monitoring, situation
from credit_assets.vert_portal import is_live, monthly_reports


def w(x, y, text, width=None):
    return (x, y, x + (width or 4.5 * len(text)), y + 7, text, 0, 0, 0)


def words_line(y, *pairs):
    """(x, texto) ou (x0, x1, texto), como no ``get_text('words')`` do PyMuPDF."""

    return [w(p[0], y, p[-1], p[1] - p[0] if len(p) == 3 else None) for p in pairs]


def test_horizontal_blocks_with_title_above_history_and_loose_currency():
    # layout da 54ª CRA (página 2): título sublinhado acima do cabeçalho, "R$" solto à esquerda do número
    page = (
        words_line(140, (25, "Indices"), (58, "e"), (64, "Acompanhamentos"))
        + words_line(152, (25, "Fundo"), (41, "de"), (49, "Despesas"))
        + words_line(160, (51, "Valor"), (65, "Atual"), (129, "Valor"), (143, "Mínimo"), (218, "Status"))
        + words_line(167, (28, "R$"), (79, "47.387,55"), (107, "R$"), (160, "40.000,00"), (212, "Enquadrado"))
        + words_line(182, (25, "Índice"), (55, "Financeiro"))
        + words_line(189, (53, "Data"), (75, "Base"), (138, "Índice"), (208, "Dívida"), (240, "Líquida*"),
                     (296, "EBITDA*"), (369, "Índice"), (400, "Apurado"), (460, "Status"))
        + words_line(197, (52, "31/03/2025"), (118, "Dívida"), (149, "Líquida"), (184, "/"), (190, "EBITDA"),
                     (238, "1.193.551,00"), (317, "1.165.468,00"), (382, "1,02"), (454, "Enquadrado"))
        + words_line(204, (52, "31/03/2026"), (118, "Dívida"), (149, "Líquida"), (184, "/"), (190, "EBITDA"),
                     (238, "1.570.675,00"), (320, "640.715,00"), (382, "2,45"), (454, "Desenquadrado"))
        + words_line(249, (25, "Fluxo"), (39, "Mínimo"), (70, "Anual"))
        + words_line(256, (45, 56, "Data"), (57, 82, "Verificação"), (120, 138, "Período"), (139, 145, "de"),
                     (147, 169, "Apuração"), (210, 222, "Fluxo"), (224, 240, "Anual"), (282, 294, "Fluxo"),
                     (295, 312, "mínimo"), (314, 330, "Anual"), (465, 469, "%"), (541, 555, "Status"))
        + words_line(264, (52, 76, "05/05/2026"), (128, 143, "06/05/25"), (144, 146, "-"), (148, 162, "05/05/26"),
                     (188, 194, "R$"), (232, 262, "729.130.592,19"), (269, 274, "R$"), (312, 343, "140.300.000,00"),
                     (459, 475, "519,7%"), (534, 562, "Enquadrado"))
        + words_line(300, (25, "Aviso"), (50, "aos"), (66, "Investidores:"))
    )
    items = parse_monitoring([[], page], [612, 612])
    assert [(i.grupo, i.item) for i in items] == [
        ("Fundo de Despesas", "Fundo de Despesas"),
        ("Índice Financeiro", "Dívida Líquida / EBITDA"),
        ("Fluxo Mínimo Anual", "Fluxo Mínimo Anual"),
    ]
    fundo, indice, fluxo = items
    assert (fundo.grupo_tipo, fundo.valor_referencia, fundo.condicao_referencia, fundo.valor_apurado, fundo.situacao,
            fundo.pagina) == ("Fundo", "R$ 40.000,00", "Mínimo", "R$ 47.387,55", "atendido", 2)
    # histórico: fica a linha mais recente
    assert (indice.valor_apurado, indice.data_verificacao, indice.condicao_apurada, indice.situacao) == (
        "2,45", "31/03/2026", "Desenquadrado", "nao_atendido")
    assert (fluxo.valor_referencia, fluxo.valor_apurado, fluxo.data_verificacao) == (
        "R$ 140.300.000,00", "R$ 729.130.592,19", "05/05/2026")


def test_name_limit_situation_table_and_title_inline_with_header():
    # "Indicadores de Monitoramento" (175ª CRI) e "Fundo de Despesas  Valor Atual  Valor Mínimo  Status" (136ª CRI)
    page = (
        words_line(101, (180, 214, "Nome"), (218, 232, "do"), (236, 270, "Índice"), (455, 484, "Valor"),
                   (488, 543, "Calculado"), (640, 675, "Limite"), (753, 801, "Situação"))
        + words_line(131, (158, 187, "Razão"), (190, 202, "de"), (205, 246, "Garantia"), (249, 280, "Sênior"),
                     (481, 501, "1,25"), (642, 649, ">"), (652, 672, "1,20"), (751, 809, "Enquadrado"))
        + words_line(162, (169, 206, "Reserva"), (209, 221, "de"), (224, 269, "Despesas"), (465, 517, "116.048,24"),
                     (617, 632, ">="), (635, 647, "R$"), (651, 697, "56.000,00"), (751, 809, "Enquadrado"))
        + words_line(326, (27, "Fundo"), (42, "de"), (49, "Reserva"), (279, "Valor"), (292, "Atual"), (365, "Valor"),
                     (378, "Máximo"), (441, "Status"))
        + words_line(333, (236, 241, "R$"), (324, 347, "888.898,26"), (354, 359, "R$"), (384, 406, "682.039,24"),
                     (435, 446, "Não"), (449, 474, "Enquadrado"))
    )
    items = parse_monitoring([page], [947])
    assert [(i.grupo_tipo, i.item, i.valor_referencia, i.condicao_referencia, i.valor_apurado, i.situacao) for i in items] == [
        ("Garantia", "Razão de Garantia Sênior", "> 1,20", "Mínimo", "1,25", "atendido"),
        ("Fundo", "Reserva de Despesas", ">= R$ 56.000,00", "Mínimo", "116.048,24", "atendido"),
        ("Fundo", "Fundo de Reserva", "R$ 682.039,24", "Máximo", "R$ 888.898,26", "nao_atendido"),
    ]


def test_vertical_block_with_two_years_keeps_latest():
    # "Índices Financeiros" da 79ª CRA: rótulos à esquerda, um ano por coluna, "Situação" na última linha
    page = (
        words_line(14, (20, "Índices"), (50, "Finaceiros"))
        + words_line(29, (81, "Data"), (92, "base"), (174, "31/12/2022"), (367, "31/12/2023"))
        + [x for y in range(38, 165, 9) for x in words_line(y, (81, "Linha"), (174, "R$"), (179, "1,00"),
                                                            (305, "Linha"), (454, "R$"), (459, "1,00"))]
        + words_line(172, (81, "Dívida"), (92, "Líquida"), (174, "R$"), (179, "1.677.486,00"), (305, "Dívida"),
                     (316, "Líquida"), (454, "R$"), (459, "1.560.609,00"))
        + words_line(181, (81, "EBITDA"), (174, "R$"), (179, "655.089,00"), (305, "EBITDA"), (454, "R$"), (459, "352.776,00"))
        + words_line(189, (81, "Índice"), (174, "2,56"), (305, "Índice"), (454, "4,42"))
        + words_line(197, (81, "Situação"), (174, "ENQUADRADO"), (305, "Situação"), (454, "DESENQUADRADO"))
    )
    (item,) = parse_monitoring([page], [595])
    assert (item.grupo, item.item, item.valor_apurado, item.data_verificacao, item.situacao) == (
        "Índices Finaceiros", "Índices Finaceiros", "4,42", "31/12/2023", "nao_atendido")  # "Índice" é rótulo genérico


def test_vertical_block_with_threshold():
    page = (
        words_line(587, (79, "Indices"), (110, "Financeiros"))
        + words_line(596, (104, "Data"), (118, "base"), (190, "2025"))
        + words_line(605, (101, "Dívida"), (117, "Líquida"), (178, "R$"), (186, "1.457.339,00"))
        + words_line(614, (108, "EBITDA"), (180, "R$"), (188, "640.715,00"))
        + words_line(623, (88, "Dívida"), (104, "Líquida"), (123, "/"), (127, "EBITDA"), (190, "2,27"))
        + words_line(632, (105, "Threshold"), (192, "3,50"))
        + words_line(641, (104, "Verificação"), (182, "Enquadrado"))
    )
    (item,) = parse_monitoring([page], [612])
    assert (item.grupo, item.item, item.valor_referencia, item.valor_apurado, item.data_verificacao, item.situacao) == (
        "Indices Financeiros", "Dívida Líquida / EBITDA", "3,50", "2,27", "2025", "atendido")


def test_period_columns_use_latest_and_limit_in_the_name():
    # "Covenants Financeiros Vigentes" da 124ª CRI: um período por coluna, o status vale para o mais recente
    page = (
        words_line(201.7, (26, 51, "Covenants"), (53, 80, "Financeiros"), (81, 102, "Vigentes"), (304, 321, "dez/25"),
                   (398, 415, "mar/26"), (468, 483, "jun/26"), (534, 548, "Status"))
        + words_line(209.7, (26, 40, "Dívida"), (41, 57, "Líquida"), (59, 61, "/"), (62, 76, "Ebitda"),
                     (110, 156, "(Desenquadramento:"), (158, 171, ">4,00"), (172, 179, "em"), (181, 183, "2"),
                     (185, 206, "trimestres)"), (308, 317, "2,50"), (402, 411, "2,88"), (471, 480, "3,39"),
                     (527, 555, "Enquadrado"))
    )
    (item,) = parse_monitoring([page], [612])
    assert (item.item, item.valor_referencia, item.condicao_referencia, item.valor_apurado, item.data_verificacao) == (
        "Dívida Líquida / Ebitda (Desenquadramento: >4,00 em 2 trimestres)", ">4,00", "Máximo", "3,39", "jun/26")


def test_table_header_at_the_end_of_one_page_and_rows_on_the_next():
    first = (
        words_line(760, (17, 33, "Fundo"), (35, 41, "de"), (43, 67, "Despesas"), (178, 191, "Valor"),
                   (193, 212, "Mínimo"), (300, 312, "Valor"), (314, 345, "Financeiro"), (354, 384, "Status"))
        + words_line(830, (563, 578, "[RESTRITO]"))
    )
    second = words_line(13, (149, 155, "R$"), (201, 224, "67.165,78"), (232, 238, "R$"), (300, 324, "74.999,02"),
                        (354, 384, "Enquadrado"))
    (item,) = parse_monitoring([first, second], [595, 595])
    assert (item.item, item.valor_referencia, item.valor_apurado, item.situacao, item.pagina) == (
        "Fundo de Despesas", "R$ 67.165,78", "R$ 74.999,02", "atendido", 2)


def test_status_table_needs_enquadrado_and_ignores_rating():
    page = (
        words_line(668, (107, "Agência"), (190, "CNPJ"), (261, "Status"), (302, "Data"))
        + words_line(677, (79, "Standard"), (173, "02.295.585/0001-40"), (259, "brA+(sf)"), (319, "15/08/2026"))
    )
    assert parse_monitoring([page], [612]) == []


def test_situation_normalization():
    assert [situation(t) for t in ("Enquadrado", "DESENQUADRADO³", "Não Enquadrado", "N/A", "Pendente", "Waiver", "")] == [
        "atendido", "nao_atendido", "nao_atendido", "nao_se_aplica", "nao_verificado", "outro", ""]
    assert competencia_from_date("2026-09-30") == "Setembro/2026"


def test_portal_live_emissions_and_monthly_reports():
    emission = {"financialTitle": "CRI", "series": [{"isClosed": True, "due_date": "2030-01-01"},
                                                   {"isClosed": False, "due_date": "2029-01-01 03:00:00 +0000 UTC"}]}
    today = date(2026, 11, 3)
    assert is_live(emission, today)
    assert not is_live({**emission, "financialTitle": "DEB"}, today)
    assert not is_live({"financialTitle": "CRA", "series": [{"isClosed": False, "due_date": "2026-10-01"}]}, today)
    docs = [
        {"id": 1, "name": "Relatório Mensal de Acompanhamento (2026.08)", "referenceDate": "2026-08-31",
         "s3PublicUrl": "https://x/a.pdf?X-Amz=1"},
        {"id": 2, "name": "Relatório Mensal de Acompanhamento (2026.09) - Excel", "referenceDate": "2026-09-30",
         "s3PublicUrl": "https://x/b.xlsx?X-Amz=1"},
        {"id": 3, "name": "Relatório Mensal de Acompanhamento  (2026.09)", "referenceDate": "2026-09-30",
         "s3PublicUrl": "https://x/c.pdf?X-Amz=1"},
        {"id": 4, "name": "Relatório Anual do Agente Fiduciário", "referenceDate": "2026-10-01", "s3PublicUrl": "https://x/d.pdf"},
        {"id": 5, "name": "Relatório Mensal de Acompanhamento (2024.06)", "referenceDate": "2024-06-28",
         "s3PublicUrl": "https://x/e.pdf"},
    ]
    assert [d["id"] for d in monthly_reports(docs, today)] == [3, 1]
