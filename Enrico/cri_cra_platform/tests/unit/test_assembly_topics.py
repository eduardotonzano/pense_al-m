from __future__ import annotations

from credit_assets.assembly_topics import classify, relevant


def test_relevant_topics_are_found_with_excerpt():
    text = ("Ordem do dia: (i) a não declaração do vencimento antecipado do CDCA; (ii) concessão de anuência prévia "
            "para o descumprimento do índice financeiro; (iii) a alteração da Data de Vencimento e novo cronograma de "
            "amortização; (iv) o pagamento de waiver fee de 0,75%.")
    hits, marks = classify(text)
    topics = relevant(hits)
    assert {"vencimento_antecipado", "waiver", "prorrogacao_repactuacao"} <= set(topics)
    assert all(h.excerpt for h in hits)
    assert not marks["nao_instalada"]


def test_routine_dfs_and_not_installed_second_call():
    text = ("Edital de segunda convocação. Ordem do dia: deliberar sobre as demonstrações financeiras do Patrimônio "
            "Separado. Não houve a presença de investidores representativos do quórum mínimo de instalação.")
    hits, marks = classify(text)
    assert relevant(hits) == []
    assert [h.topic for h in hits] == ["aprovacao_dfs"]
    assert marks == {"nao_instalada": True, "segunda_convocacao": True}


def test_debtor_distress_and_guarantee_topics():
    hits, _ = classify("A Devedora ajuizou pedido de recuperação judicial. Deliberar sobre a substituição das garantias.")
    assert set(relevant(hits)) == {"inadimplencia_devedor", "garantias"}
