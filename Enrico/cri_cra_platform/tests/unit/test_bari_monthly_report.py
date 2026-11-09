from credit_assets.bari_monthly_report import Cell, read_stream, situation


def row(*cells):
    return [Cell(x, x + 40, text) for x, text in cells]


def read(rows, panels=False):
    items, missed = [], []
    read_stream(rows, 1, items, missed, panels=panels)
    return items, missed


def test_quadro_do_painel_le_exigido_apurado_e_situacao():
    items, _ = read([
        row((249, "FUNDO DE RESERVA")),
        row((243, "Saldo no mês anterior (R$)"), (346, "534.324,26")),
        row((243, "Saldo final (R$)"), (346, "565.529,87")),
        row((243, "Saldo mínimo exigido (R$)"), (346, "575.242,74")),
        row((243, "Recomposição necessária (R$)"), (356, "9.712,87")),
        row((243, "Situação"), (327, "DESENQUADRADO")),
    ], panels=True)
    assert [(i.item, i.valor_referencia, i.valor_apurado, i.situacao) for i in items] == [
        ("FUNDO DE RESERVA", "575.242,74", "565.529,87", "nao_atendido")]


def test_meses_lado_a_lado_usa_a_coluna_mais_recente():
    items, _ = read([
        row((89, "G) Razão de Garantia")),
        row((212, "mai/26"), (294, "jun/26"), (377, "jul/26")),
        row((130, "Atual"), (227, "149,03%"), (311, "152,21%"), (394, "153,76%")),
        row((127, "Mínimo"), (238, "130%"), (322, "130%"), (406, "130%")),
        row((125, "Situação"), (202, "Enquadrado"), (286, "Enquadrado"), (370, "Desenquadrado")),
    ])
    assert len(items) == 1
    assert (items[0].valor_apurado, items[0].valor_referencia, items[0].situacao, items[0].data_verificacao) == (
        "153,76%", "130%", "nao_atendido", "jul/26")


def test_tabela_com_cabecalho_atual_minimo_status():
    items, _ = read([
        row((20, "F) Saldo dos fundos")),
        row((265, "Valor atual"), (333, "Valor mínimo"), (449, "Status")),
        row((20, "a. Fundo de despesas"), (268, "78.377,73"), (347, "36.000,00"), (424, "Enquadrado")),
        row((20, "b. Fundo de reserva"), (262, "202.979,38"), (334, "1.150.292,07"), (408, "Desenquadrado")),
        row((20, "Total"), (262, "281.357,11")),
    ])
    assert [(i.item, i.valor_apurado, i.valor_referencia, i.situacao) for i in items] == [
        ("Fundo de despesas", "78.377,73", "36.000,00", "atendido"),
        ("Fundo de reserva", "202.979,38", "1.150.292,07", "nao_atendido")]


def test_linha_de_minimo_com_situacao_pega_o_saldo_da_linha_de_cima():
    items, _ = read([
        row((20, "D) Análise Fundos da Operação")),
        row((20, "c - Saldo Fundo Despesas"), (271, "5.071,82")),
        row((95, "Mínimo"), (274, "40.000,00"), (304, "Desenquadrado")),
    ])
    assert [(i.item, i.valor_apurado, i.valor_referencia, i.situacao) for i in items] == [
        ("Saldo Fundo Despesas", "5.071,82", "40.000,00", "nao_atendido")]


def test_situacao_informada_sem_deducao():
    assert situation("Desenquadrado - waiver") == "nao_atendido"
    assert situation("ENQUADRADO") == "atendido"
    assert situation("COBERTO") == "atendido"
    assert situation("-") == ""
