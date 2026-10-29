"""Consultas à base de dados abertos da CVM (data/cvm_open.db) por ISIN de um ativo do catálogo.

Uma emissão pode aparecer com mais de um código de certificado (um tipo ISIN e outro tipo CETIP) na mesma
securitizadora; as consultas juntam os códigos que compartilham ISIN de série.
"""
from __future__ import annotations

import sqlite3
from typing import Any


def emission_codes(connection: sqlite3.Connection, kind: str, isin: str) -> tuple[str, list[str]] | None:
    row = connection.execute(
        f"SELECT CNPJ_Emissora, Codigo_Identificacao_Certificado FROM {kind}_classe_vigente WHERE Codigo_ISIN = ? "
        "ORDER BY Data_Referencia DESC LIMIT 1", (isin,)).fetchone()
    if row is None:
        return None
    cnpj, cert = row[0], row[1]
    isins = [r[0] for r in connection.execute(
        f"SELECT DISTINCT Codigo_ISIN FROM {kind}_classe_vigente WHERE Codigo_Identificacao_Certificado = ? AND Codigo_ISIN <> ''",
        (cert,))]
    codes = {cert}
    if isins:
        codes |= {r[0] for r in connection.execute(
            f"SELECT DISTINCT Codigo_Identificacao_Certificado FROM {kind}_classe_vigente WHERE CNPJ_Emissora = ? "
            f"AND Codigo_ISIN IN ({','.join('?' * len(isins))})", (cnpj, *isins))}
    return cnpj, sorted(codes)


def emission(connection: sqlite3.Connection, kind: str, isin: str) -> dict[str, Any] | None:
    """Última competência da emissão: séries (uma linha por ISIN), data de emissão e códigos do certificado."""

    found = emission_codes(connection, kind, isin)
    if found is None:
        return None
    cnpj, codes = found
    marks = ",".join("?" * len(codes))
    last = connection.execute(
        f"SELECT MAX(Data_Referencia) FROM {kind}_classe_vigente WHERE Codigo_Identificacao_Certificado IN ({marks})",
        tuple(codes)).fetchone()[0]
    series: dict[str, dict] = {}
    for r in connection.execute(
            f"SELECT * FROM {kind}_classe_vigente WHERE Codigo_Identificacao_Certificado IN ({marks}) AND Data_Referencia = ?",
            (*codes, last)):
        series[r["Codigo_ISIN"] or str(r["Numero_Serie"])] = dict(r)
    geral = connection.execute(
        f"SELECT * FROM {kind}_geral_vigente WHERE Codigo_Identificacao_Certificado IN ({marks}) "
        "ORDER BY Data_Referencia DESC LIMIT 1", tuple(codes)).fetchone()
    return {"cnpj": cnpj, "codes": codes, "last": last, "series": list(series.values()),
            "geral": dict(geral) if geral else {}, "data_emissao": ((geral["Data_Emissao"] if geral else "") or "")[:10]}


def history(connection: sqlite3.Connection, kind: str, codes: list[str], since: str) -> list[dict[str, Any]]:
    marks = ",".join("?" * len(codes))
    return [dict(r) for r in connection.execute(
        f"SELECT * FROM {kind}_classe_vigente WHERE Codigo_Identificacao_Certificado IN ({marks}) "
        "AND Data_Referencia >= ? ORDER BY Data_Referencia", (*codes, since))]
