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
        row(Codigo_Identificacao_Certificado="BRABC1", Codigo_ISIN="BRABCDCRA011", CNPJ_Emissora="1", Numero_Serie="1", Data_Referencia="2026-08-01"),
        row(Codigo_Identificacao_Certificado="BRABC1", Codigo_ISIN="BRABCDCRA029", CNPJ_Emissora="1", Numero_Serie="2", Data_Referencia="2026-08-01"),
        row(Codigo_Identificacao_Certificado="CRA023X", Codigo_ISIN="BRABCDCRA011", CNPJ_Emissora="1", Numero_Serie="1", Data_Referencia="2025-01-01"),
        row(Codigo_Identificacao_Certificado="OUTRA", Codigo_ISIN="BRABCDCRA094", CNPJ_Emissora="1", Numero_Serie="1", Data_Referencia="2026-08-01"),
        row(Codigo_Identificacao_Certificado="DOUTRA", Codigo_ISIN="BRABCDCRA011", CNPJ_Emissora="2", Numero_Serie="1", Data_Referencia="2026-08-01"),
    ]
    last = {"BRABC1": "2026-08-01", "CRA023X": "2025-01-01", "OUTRA": "2026-08-01", "DOUTRA": "2026-08-01"}
    merged, filing, aliases = merge_alias_certificates(rows, last)
    ids = {r["Codigo_Identificacao_Certificado"] for r in merged}
    assert ids == {"BRABC1", "OUTRA", "DOUTRA"}  # CRA023X virou alias de BRABC1; outra securitizadora não une
    assert sorted(aliases["BRABC1"]) == ["BRABC1", "CRA023X"] and filing["BRABC1"] == "2026-08-01"
    assert sum(1 for r in merged if r["Codigo_Identificacao_Certificado"] == "BRABC1") == 2  # S1 deduplicado, S2 mantido
    assert len(rows) == 5  # entrada não é alterada


def test_placeholder_isin_does_not_merge_emissions_or_series():
    from credit_assets.market_checks import merge_alias_certificates
    # Leverage: várias emissões com séries sem ISIN informado ("00000") não são a mesma emissão
    rows = [
        row(Codigo_Identificacao_Certificado="BRLSECCRI0Q9", Codigo_ISIN="BRLSECCRI0Q9", CNPJ_Emissora="1", Numero_Serie="2"),
        row(Codigo_Identificacao_Certificado="BRLSECCRI0Q9", Codigo_ISIN="00000", CNPJ_Emissora="1", Numero_Serie="3"),
        row(Codigo_Identificacao_Certificado="BRLSECCRI2L6", Codigo_ISIN="00000", CNPJ_Emissora="1", Numero_Serie="1"),
        row(Codigo_Identificacao_Certificado="BRLSECCRI2L6", Codigo_ISIN="BRLSECCRI2L6", CNPJ_Emissora="1", Numero_Serie="1"),
        row(Codigo_Identificacao_Certificado="OUTRA", Codigo_ISIN="00000", CNPJ_Emissora="2", Numero_Serie="1"),
    ]
    last = {c: REF for c in ("BRLSECCRI0Q9", "BRLSECCRI2L6", "OUTRA")}
    merged, _, aliases = merge_alias_certificates(rows, last)
    assert aliases["BRLSECCRI0Q9"] == ["BRLSECCRI0Q9"] and aliases["BRLSECCRI2L6"] == ["BRLSECCRI2L6"]
    # série 3 sem ISIN fica; a série 1 do BRLSECCRI2L6 publicada também com "00000" conta uma vez só
    assert sorted((r["Codigo_Identificacao_Certificado"], r["Numero_Serie"]) for r in merged) == [
        ("BRLSECCRI0Q9", "2"), ("BRLSECCRI0Q9", "3"), ("BRLSECCRI2L6", "1"), ("OUTRA", "1")]
    assert next(r for r in merged if r["Codigo_Identificacao_Certificado"] == "BRLSECCRI2L6")["Codigo_ISIN"] == "BRLSECCRI2L6"
    ranking = {i["certificado"]: i for i in rank_emissions(rows, REF, last)}
    assert all("isin_repetido" not in i["flags"] and "identificador_duplicado" not in i["flags"] for i in ranking.values())


def test_balance_incompatible_with_paid_in_is_flagged_and_left_out_of_totals():
    from credit_assets.market_checks import balance_is_suspect, trusted_balance
    leverage = row(Valor_Certificados="340422343379.18", Valor_Total_Integralizado="16525000.00")
    assert balance_is_suspect(leverage) and trusted_balance(leverage) == Decimal(0)
    assert "saldo_incompativel" in series_flags(leverage, REF)
    normal = row(Valor_Certificados="127906324.22", Total_Integralizado="123599000.00")
    assert not balance_is_suspect(normal) and trusted_balance(normal) == Decimal("127906324.22")
    assert not balance_is_suspect(row())  # sem integralizado informado não se julga


def test_mixed_situation_within_same_class_flags_emission_once():
    def s(cert, isin, situation, klass="Sênior", balance="100"):
        return row(Codigo_Identificacao_Certificado=cert, Codigo_ISIN=isin, Situacao=situation, Classe=klass,
                   Valor_Certificados=balance)
    rows = [
        s("MISTA", "BRM000000001", "Adimplente"), s("MISTA", "BRM000000002", "Em atraso"), s("MISTA", "BRM000000003", "Em atraso"),
        s("CLASSES", "BRC000000001", "Adimplente"), s("CLASSES", "BRC000000002", "Em atraso", klass="Subordinada"),
        s("ZERADA", "BRZ000000001", "Adimplente", balance="0"), s("ZERADA", "BRZ000000002", "Em atraso"),
    ]
    by = {i["certificado"]: i for i in rank_emissions(rows, REF, {c: REF for c in ("MISTA", "CLASSES", "ZERADA")})}
    assert by["MISTA"]["flags"]["situacao_mista_na_classe"] == 1 and by["MISTA"]["score"] == 5 + 3
    assert "situacao_mista_na_classe" not in by["CLASSES"]["flags"]  # classes diferentes podem ter fluxos diferentes
    assert "situacao_mista_na_classe" not in by["ZERADA"]["flags"]  # série sem saldo não conta
