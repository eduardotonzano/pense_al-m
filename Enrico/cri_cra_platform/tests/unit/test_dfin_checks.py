from __future__ import annotations

from credit_assets.dfin_checks import delivery_days, latest_by_certificate, opinion_severity, signals


def df(cert="C1", ref="2025-06-30", version="1", delivered="2025-09-20", opinion="Sem ressalva e com ênfase"):
    return {"Codigo_Identificacao_Certificado": cert, "Data_Referencia": ref, "Versao": version,
            "Data_Entrega": delivered, "Parecer_Auditor": opinion}


def test_opinion_severity():
    assert opinion_severity("Sem ressalva e com ênfase") == 0
    assert opinion_severity("Sem ressalva e sem ênfase") == 0
    assert opinion_severity("Com ressalva") == 2
    assert opinion_severity("Abstenção de Opinião") == 3
    assert opinion_severity("Opinião adversa") == 3
    assert opinion_severity("") is None and opinion_severity("outro texto") is None


def test_latest_by_certificate_keeps_highest_version_per_date_and_orders_recent_first():
    grouped = latest_by_certificate([df(), df(version="2", opinion="Com ressalva"), df(ref="2024-06-30")])
    history = grouped["C1"]
    assert [h["Data_Referencia"] for h in history] == ["2025-06-30", "2024-06-30"]
    assert history[0]["Parecer_Auditor"] == "Com ressalva"


def test_signals():
    assert signals([df()]) == []
    assert signals([df(opinion="Com ressalva"), df(ref="2024-06-30")]) == ["df_com_ressalva", "opiniao_piorou"]
    assert signals([df(opinion="Abstenção de Opinião")]) == ["df_abstencao_ou_adversa"]
    assert signals([df(delivered="2025-10-15")]) == ["df_entregue_apos_prazo"]
    assert delivery_days("2025-06-30", "2025-09-28") == 90
