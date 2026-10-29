from __future__ import annotations

from decimal import Decimal

from credit_assets.market_checks import (
    base_months, rank_emissions, reference_competence, series_flags,
)

REF = "2026-08-01"


def row(**kw):
    base = {"Codigo_Identificacao_Certificado": "C1", "CNPJ_Emissora": "1", "Codigo_ISIN": "BRXXXXXXXXX1",
            "Situacao": "Adimplente", "Valor_Certificados": "100.00", "Data_Vencimento": "2030-12-18",
            "Pagamento_Periodicidade": "Semestral", "Pagamento_Mes_Base": "Junho e Dezembro"}
    base.update(kw)
    return base


def test_reference_competence_skips_partial_last_month():
    assert reference_competence({"2026-07-01": 100, "2026-08-01": 98, "2026-09-01": 20}) == "2026-08-01"
    assert reference_competence({"2026-07-01": 100, "2026-08-01": 50}) == "2026-07-01"


def test_base_months_reads_only_named_months():
    assert base_months("Junho e Dezembro") == [5, 11]
    assert base_months("Abril e Outubro") == [3, 9]
    assert base_months("46265") == [] and base_months("Ao Longo dos Meses") == []
    assert base_months("Março") == [2]


def test_series_flags():
    assert series_flags(row(), REF) == []
    assert "vencimento_fora_mes_base" in series_flags(row(Data_Vencimento="2029-07-16"), REF)
    assert "em_atraso" in series_flags(row(Situacao="Em atraso"), REF)
    assert "vencido_com_saldo_adimplente" in series_flags(row(Data_Vencimento="2025-10-15"), REF)
    assert "vencido_com_saldo_adimplente" not in series_flags(
        row(Data_Vencimento="2025-10-15", Valor_Certificados="0"), REF)
    assert "serie_sem_isin" in series_flags(row(Codigo_ISIN=""), REF)
    assert "isin_invalido" in series_flags(row(Codigo_ISIN="0000"), REF)
    assert "isin_invalido" not in series_flags(row(Codigo_ISIN="BRECOACRALJ8"), REF)
    # mensal ou campo numérico não gera falso positivo
    assert series_flags(row(Pagamento_Periodicidade="Mensal", Data_Vencimento="2029-07-16"), REF) == []
    assert series_flags(row(Pagamento_Mes_Base="46265", Data_Vencimento="2029-07-16"), REF) == []


def test_rank_orders_by_score_then_balance_and_flags_stale_and_duplicate_isin():
    rows = [
        row(Codigo_Identificacao_Certificado="OK", Codigo_ISIN="BRAAAAAAAAA1"),
        row(Codigo_Identificacao_Certificado="ATRASO", Codigo_ISIN="BRBBBBBBBBB1", Situacao="Em atraso", Valor_Certificados="50"),
        row(Codigo_Identificacao_Certificado="GRANDE", Codigo_ISIN="BRCCCCCCCCC1", Situacao="Em atraso", Valor_Certificados="900"),
        row(Codigo_Identificacao_Certificado="DUP1", Codigo_ISIN="BRDDDDDDDDD1", CNPJ_Emissora="1"),
        row(Codigo_Identificacao_Certificado="DUP2", Codigo_ISIN="BRDDDDDDDDD1", CNPJ_Emissora="2"),
        row(Codigo_Identificacao_Certificado="ALIAS1", Codigo_ISIN="BRFFFFFFFFF1", CNPJ_Emissora="3"),
        row(Codigo_Identificacao_Certificado="ALIAS2", Codigo_ISIN="BRFFFFFFFFF1", CNPJ_Emissora="3"),
        row(Codigo_Identificacao_Certificado="SUMIU", Codigo_ISIN="BREEEEEEEEE1", Valor_Certificados="10"),
    ]
    last = {c: REF for c in ("OK", "ATRASO", "GRANDE", "DUP1", "DUP2", "ALIAS1", "ALIAS2")}
    last["SUMIU"] = "2026-03-01"
    ranking = rank_emissions(rows, REF, last)
    order = [item["certificado"] for item in ranking]
    assert order[:2] == ["GRANDE", "ATRASO"]  # mesmo score 5: maior saldo primeiro
    by = {item["certificado"]: item for item in ranking}
    assert by["SUMIU"]["flags"]["informe_defasado"] == 1 and by["SUMIU"]["saldo"] == Decimal(0)
    assert by["DUP1"]["flags"]["isin_repetido"] == 1 and by["DUP2"]["flags"]["isin_repetido"] == 1
    assert "identificador_duplicado" in by["ALIAS1"]["flags"] and "isin_repetido" not in by["ALIAS1"]["flags"]
    assert by["OK"]["score"] == 0


def test_merge_alias_certificates_unites_isin_and_cetip_codes():
    from credit_assets.market_checks import merge_alias_certificates
    rows = [
        row(Codigo_Identificacao_Certificado="BRABC1", Codigo_ISIN="S1", CNPJ_Emissora="1", Numero_Serie="1", Data_Referencia="2026-08-01"),
        row(Codigo_Identificacao_Certificado="BRABC1", Codigo_ISIN="S2", CNPJ_Emissora="1", Numero_Serie="2", Data_Referencia="2026-08-01"),
        row(Codigo_Identificacao_Certificado="CRA023X", Codigo_ISIN="S1", CNPJ_Emissora="1", Numero_Serie="1", Data_Referencia="2025-01-01"),
        row(Codigo_Identificacao_Certificado="OUTRA", Codigo_ISIN="S9", CNPJ_Emissora="1", Numero_Serie="1", Data_Referencia="2026-08-01"),
        row(Codigo_Identificacao_Certificado="DOUTRA", Codigo_ISIN="S1", CNPJ_Emissora="2", Numero_Serie="1", Data_Referencia="2026-08-01"),
    ]
    last = {"BRABC1": "2026-08-01", "CRA023X": "2025-01-01", "OUTRA": "2026-08-01", "DOUTRA": "2026-08-01"}
    merged, filing, aliases = merge_alias_certificates(rows, last)
    ids = {r["Codigo_Identificacao_Certificado"] for r in merged}
    assert ids == {"BRABC1", "OUTRA", "DOUTRA"}  # CRA023X virou alias de BRABC1; outra securitizadora não une
    assert sorted(aliases["BRABC1"]) == ["BRABC1", "CRA023X"] and filing["BRABC1"] == "2026-08-01"
    assert sum(1 for r in merged if r["Codigo_Identificacao_Certificado"] == "BRABC1") == 2  # S1 deduplicado, S2 mantido
    assert len(rows) == 5  # entrada não é alterada
