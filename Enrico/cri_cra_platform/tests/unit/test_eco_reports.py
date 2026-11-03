from credit_assets.eco_reports import money, parse_follow_up, report_links


def test_follow_up_balance_is_the_sum_of_classes():
    text = ("CONCENTRAÇÃO MÁXIMA DE RECEBÍVEIS POR SACADO Sênior R$ 78.361.403,62 Mezanino R$ 5.249.823,87 "
            "Subordinada R$ 20.051.396,99 SALDO DEVEDOR: Série Sênior - 75% Aderente Não Aderente")
    fields = parse_follow_up([[]], text)
    assert (fields["saldo_senior"], fields["saldo_mezanino"], fields["saldo_subordinada"]) == (
        "R$ 78.361.403,62", "R$ 5.249.823,87", "R$ 20.051.396,99")
    assert fields["saldo_devedor"] == "R$ 103.662.624,48"
    assert money(fields["saldo_devedor"]) == 103662624.48
    assert (fields["aderencia_itens"], fields["aderencia_nao_aderentes"]) == ("2", "1")


def test_report_links_by_kind_most_recent_first():
    html = ('<a href="https://ecoagro.agr.br/public/storage/Arquivo/1792172867Relat%C3%B3rio%20de%20Acompanhamento%20Mensal'
            '%20-%20229%C2%AA%20Emiss%C3%A3o.pdf">a</a>'
            '<a href="https://ecoagro.agr.br/public/storage/Arquivo/1790000000Setembro_2026-Relatorio%20Mensal.pdf">g</a>'
            '<a href="https://ecoagro.agr.br/public/storage/Arquivo/1780000000AGT_15052026.pdf">ata</a>')
    assert [(link.kind, link.uploaded) for link in report_links(html)] == [
        ("acompanhamento", 1792172867), ("gestao", 1790000000)]
