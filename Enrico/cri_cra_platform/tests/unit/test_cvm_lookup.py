from __future__ import annotations

import sqlite3

from credit_assets.cvm_lookup import emission


def database() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("CREATE TABLE cri_classe_vigente (CNPJ_Emissora, Codigo_Identificacao_Certificado, Data_Referencia, "
                       "Numero_Serie, Codigo_ISIN, Valor_Certificados)")
    connection.execute("CREATE TABLE cri_geral_vigente (Codigo_Identificacao_Certificado, Data_Referencia, Data_Emissao)")
    rows = [
        # emissão 11: série 2 com ISIN, série 3 sem ISIN ("00000")
        ("1", "BRLSECCRI0Q9", "2026-08-01", "2", "BRLSECCRI0Q9", "9"),
        ("1", "BRLSECCRI0Q9", "2026-08-01", "3", "00000", "2"),
        # emissão 32: a série 1 publicada duas vezes, com ISIN e com "00000"
        ("1", "BRLSECCRI2L6", "2026-08-01", "1", "00000", "44"),
        ("1", "BRLSECCRI2L6", "2026-08-01", "1", "BRLSECCRI2L6", "44"),
    ]
    connection.executemany("INSERT INTO cri_classe_vigente VALUES (?, ?, ?, ?, ?, ?)", rows)
    connection.executemany("INSERT INTO cri_geral_vigente VALUES (?, ?, ?)",
                           [("BRLSECCRI0Q9", "2026-08-01", "2024-05-27"), ("BRLSECCRI2L6", "2026-08-01", "2025-03-07")])
    return connection


def test_placeholder_isin_does_not_join_emissions():
    connection = database()
    first = emission(connection, "cri", "BRLSECCRI0Q9")
    assert first["codes"] == ["BRLSECCRI0Q9"]
    assert sorted((s["Numero_Serie"], s["Codigo_ISIN"]) for s in first["series"]) == [("2", "BRLSECCRI0Q9"), ("3", "00000")]
    second = emission(connection, "cri", "BRLSECCRI2L6")
    assert second["codes"] == ["BRLSECCRI2L6"] and second["data_emissao"] == "2025-03-07"
    assert [(s["Numero_Serie"], s["Codigo_ISIN"]) for s in second["series"]] == [("1", "BRLSECCRI2L6")]
