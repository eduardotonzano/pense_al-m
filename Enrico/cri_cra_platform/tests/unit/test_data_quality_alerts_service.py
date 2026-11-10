import json
from pathlib import Path

from credit_assets.services.data_quality_alerts_service import (
    balance_reconciliation,
    key_party_changed,
    return_outlier,
    status_vs_delinquency,
)

ROOT = Path(__file__).resolve().parents[2]
RULES = json.loads(
    (ROOT / "config" / "alert_rules" / "data_quality_informe_mensal_cra.json").read_text(encoding="utf-8")
)["rules"]
R = "/InformeMensalCRA"


def _row(value, state=None, key=None, scale="1"):
    if state is None:
        state = "zero" if value == "0" else "present_value"
    return {"normalized_value": value, "field_state": state, "instance_key": key, "scale": scale}


def _month(month, fields, report_id=1):
    values = {}
    for path, row in fields.items():
        values[(path, row["instance_key"])] = row
    return {"report_id": report_id, "month": month, "values": values}


DELINQUENCY_ZERO = {path: _row("0") for path in RULES["status_vs_delinquency"]["delinquency_paths"]}


def test_status_em_atraso_with_zero_delinquency_is_flagged():
    month = _month("2026-04", {
        RULES["status_vs_delinquency"]["status_path"]: _row("Em atraso", key="1"),
        **DELINQUENCY_ZERO,
    })
    alerts = status_vs_delinquency([month], RULES["status_vs_delinquency"])
    assert len(alerts) == 1 and "Em atraso" in alerts[0]["message"]


def test_status_consistent_is_not_flagged():
    month = _month("2026-03", {
        RULES["status_vs_delinquency"]["status_path"]: _row("Adimplente", key="1"),
        **DELINQUENCY_ZERO,
    })
    assert status_vs_delinquency([month], RULES["status_vs_delinquency"]) == []


def _balance_months(saldo_atual, scale="1"):
    rule = RULES["balance_reconciliation"]
    previous = _month("2026-01", {rule["balance_path"]: _row("1000", scale=scale),
                                  rule["series_count_path"]: _row("1", scale=None)})
    current = _month("2026-02", {
        rule["balance_path"]: _row(saldo_atual),
        rule["return_path"]: _row("0.01", key="1", scale=None),
        rule["payments_path"]: _row("100"),
        rule["series_count_path"]: _row("1", scale=None),
    }, report_id=2)
    return [previous, current]


def test_balance_reconciliation_flags_only_beyond_tolerance():
    rule = RULES["balance_reconciliation"]
    assert balance_reconciliation(_balance_months("910"), rule) == []          # 1000*1.01-100
    assert balance_reconciliation(_balance_months("910.5"), rule) == []        # 0.05%
    assert len(balance_reconciliation(_balance_months("915"), rule)) == 1      # 0.5%


def test_balance_reconciliation_skips_unknown_scale():
    assert balance_reconciliation(_balance_months("2000", scale="unknown"), RULES["balance_reconciliation"]) == []


def test_return_outlier_uses_own_history():
    rule = RULES["return_outlier"]
    path = rule["return_path"]
    normal = ["0.012", "0.013", "0.014", "0.0125", "0.0135", "0.0145", "0.012", "0.013",
              "0.014", "0.0125", "0.0135", "0.0145"]
    months = [_month(f"2025-{i + 1:02d}", {path: _row(v, key="1", scale=None)}, i) for i, v in enumerate(normal)]
    months.append(_month("2026-01", {path: _row("0.8076", key="1", scale=None)}, 99))
    alerts = return_outlier(months, rule)
    assert [a["report_id"] for a in alerts] == [99]
    assert return_outlier(months[:5], rule) == []  # histórico curto demais


def test_key_party_change_is_info():
    path = RULES["key_party_changed"]["paths"][0]
    months = [_month("2022-10", {path: _row("23.357.072/0001-81", scale=None)}),
              _month("2022-11", {path: _row("31.943.818/0001-71", scale=None)}, 2)]
    alerts = key_party_changed(months, RULES["key_party_changed"])
    assert len(alerts) == 1 and alerts[0]["month"] == "2022-11"
