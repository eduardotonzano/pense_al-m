from credit_assets.opea_monthly_report import parse_monitoring
from credit_assets.opea_portal import monthly_reports


def w(x, y, text):
    return (x, y, x + 5 * len(text), y + 8, text, 0, 0, 0)


def words_line(y, *pairs):
    return [w(x, y, t) for x, t in pairs]


HEADER = (
    words_line(285, (152, "Valor"), (221, "Condição"), (362, "Condição"), (441, "Data"), (462, "de"), (520, "Próxima"))
    + words_line(290, (55, "Descrição"), (302, "Valor"))  # "Valor" de "Valor Apurado" alguns pontos abaixo
    + words_line(296, (142, "Referência"), (218, "Referência"), (295, "Apurado"), (364, "Apurada"),
                 (435, "Verificação"), (514, "Verificação"))
)


def test_monitoring_table_with_groups_wrapped_cells_and_split_header():
    page = (
        words_line(228, (68, "Monitoramentos")) + HEADER
        + words_line(324, (30, "Garantia:"), (68, "Fundo"), (95, "de"), (107, "Despesa"))
        + words_line(353, (41, "Fundo"), (63, "de"), (74, "Despesas"), (138, "R$"), (150, "210.000,00"), (227, "Mínimo"),
                     (287, "R$"), (299, "207.658,19"), (358, "Nao"), (374, "atendido"), (438, "28/09/2026"), (516, "28/10/2026"))
        # título de grupo comprido, que passa da coluna de descrição
        + words_line(381, (30, "Obrigaçao:"), (74, "Relatório"), (111, "Gerencial"), (150, "Direitos"), (181, "Creditórios"))
        # item com descrição em três linhas, ancorado na do meio
        + words_line(554, (29, "Relatório"), (61, "de"), (71, "Destinação"), (111, "de"))
        + words_line(560, (158, "n/a"), (216, "Nao"), (232, "se"), (242, "Aplica"), (290, "Não"), (305, "recebido"),
                     (358, "Nao"), (374, "atendido"), (438, "30/08/2026"), (516, "28/02/2027"))
        + words_line(565, (58, "Recursos"))
        + words_line(664, (15, "Este"), (29, "relatório"), (55, "foi"), (64, "elaborado"))
    )
    items = parse_monitoring([[], page])
    assert [(i.grupo_tipo, i.grupo, i.item) for i in items] == [
        ("Garantia", "Fundo de Despesa", "Fundo de Despesas"),
        ("Obrigaçao", "Relatório Gerencial Direitos Creditórios", "Relatório de Destinação de Recursos"),
    ]
    first, second = items
    assert (first.valor_referencia, first.condicao_referencia, first.valor_apurado) == ("R$ 210.000,00", "Mínimo", "R$ 207.658,19")
    assert (first.situacao, first.data_verificacao, first.proxima_verificacao, first.pagina) == (
        "nao_atendido", "28/09/2026", "28/10/2026", 2)
    assert (second.valor_apurado, second.situacao) == ("Não recebido", "nao_atendido")


def test_table_ends_at_disclaimer_and_needs_monitoring_title():
    page = HEADER + words_line(353, (41, "Fundo"), (358, "Atendido"), (438, "28/09/2026"))
    assert parse_monitoring([page]) == []  # sem o título "Monitoramentos" não é a tabela


def test_monthly_reports_are_ordered_most_recent_first():
    events = [
        {"id": 1, "titulo": "Relatório Mensal Gestão Fiduciária - 08/2026"},
        {"id": 2, "titulo": "Informe Mensal CVM - 09/2026"},
        {"id": 3, "titulo": "Relatório Mensal Gestão Fiduciária - 09/2026"},
        {"id": 4, "titulo": "Relatório Mensal Gestão Fiduciária - 12/2025"},
    ]
    assert [(month, e["id"]) for month, e in monthly_reports(events)] == [("2026-09", 3), ("2026-08", 1), ("2025-12", 4)]
