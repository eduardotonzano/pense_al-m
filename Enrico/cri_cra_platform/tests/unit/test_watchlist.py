from __future__ import annotations

from credit_assets.watchlist import AssetSignals, classify

SINCE = "2025-08-01"


def test_severe_ata_decision_wins_regardless_of_date():
    signals = AssetSignals(late_series=2, ata_decisions=[("2024-04-24", "vencimento_antecipado_declarado")])
    level, reasons = classify(signals, SINCE)
    assert level == 1 and reasons[0] == "ata de 2024-04-24: vencimento antecipado declarado"


def test_rejected_decisions_are_not_severe_except_rejecting_the_waiver_of_acceleration():
    assert classify(AssetSignals(ata_decisions=[("2026-01-01", "dacao_em_pagamento_rejeitado")]), SINCE)[0] == 5
    rejected_waiver = AssetSignals(ata_decisions=[("2026-01-01", "nao_declaracao_do_vencimento_antecipado_rejeitada")])
    assert classify(rejected_waiver, SINCE)[0] == 1
    # "não declarado" não é o mesmo que "declarado"
    assert classify(AssetSignals(ata_decisions=[("2026-01-01", "vencimento_antecipado_nao_declarado")]), SINCE)[0] == 3


def test_late_series_then_recent_stress_then_other_signals():
    assert classify(AssetSignals(late_series=1), SINCE)[0] == 2
    old_waiver = AssetSignals(ata_decisions=[("2024-01-10", "waiver_aprovado")])
    assert classify(old_waiver, SINCE) == (5, [])  # waiver de mais de 12 meses não conta
    assert classify(AssetSignals(df_flags=["df_com_ressalva"], df_opinion="Com ressalva"), SINCE) == (3, ["DF: Com ressalva"])
    assert classify(AssetSignals(contagion=True), SINCE)[0] == 3
    level, reasons = classify(AssetSignals(informe_events=["2026-07 taxa_mudou"], ranking_score=4), SINCE)
    assert level == 4 and reasons == ["Informe em 12 meses: taxa_mudou", "ranking de triagem: 4 pontos"]
