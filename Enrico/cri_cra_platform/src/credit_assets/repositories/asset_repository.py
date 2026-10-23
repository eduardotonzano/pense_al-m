from __future__ import annotations

from datetime import datetime, timezone
import sqlite3
import unicodedata
import re

from credit_assets.models.asset import Asset


_ISIN_PATTERN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")


class AssetRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def upsert(self, asset: Asset) -> int:
        codigo_cetip = self._normalize_identifier(asset.codigo_cetip)
        isin = self._normalize_identifier(asset.isin)
        if isin and not _ISIN_PATTERN.fullmatch(isin):
            raise ValueError(f"ISIN inválido: {asset.isin!r}")
        if codigo_cetip and codigo_cetip == isin:
            raise ValueError("codigo_cetip não pode ser igual ao ISIN")
        if not codigo_cetip and not isin:
            raise ValueError("Informe codigo_cetip ou ISIN para identificar o ativo")

        by_isin = self._find_by_normalized("isin", isin) if isin else None
        by_cetip = (
            self._find_by_normalized("codigo_cetip", codigo_cetip)
            if codigo_cetip
            else None
        )
        if by_isin and by_cetip and by_isin["asset_id"] != by_cetip["asset_id"]:
            raise ValueError(
                "Conflito de identidade: ISIN e codigo_cetip correspondem a "
                f"ativos diferentes (asset_id={by_isin['asset_id']} e "
                f"asset_id={by_cetip['asset_id']})"
            )
        existing = by_isin or by_cetip
        now = datetime.now(timezone.utc).isoformat()
        stored_cetip = codigo_cetip or (
            self._normalize_identifier(existing["codigo_cetip"]) if existing else None
        )
        stored_isin = isin or (
            self._normalize_identifier(existing["isin"]) if existing else None
        )
        # CNPJ em branco na entrada (o CSV do piloto) nao apaga o que o banco ja
        # tem, como o CNPJ resolvido pela CVM; CNPJ preenchido vale como antes.
        stored_cnpj_securitizadora = asset.cnpj_securitizadora.strip() or (
            (existing["cnpj_securitizadora"] or "").strip() if existing else ""
        )
        stored_cnpj_devedor = asset.cnpj_devedor.strip() or (
            ((existing["cnpj_devedor"] or "").strip() or None) if existing else None
        )
        values = (
            stored_cetip,
            asset.tipo_ativo.strip().upper(),
            asset.securitizadora.strip(),
            stored_cnpj_securitizadora,
            asset.emissao.strip(),
            self._normalize_series(asset.serie),
            asset.devedor.strip() or None,
            stored_cnpj_devedor,
            stored_isin,
            now,
        )
        if existing:
            self.connection.execute(
                """UPDATE assets SET codigo_cetip = ?, tipo_ativo = ?,
                   securitizadora = ?, cnpj_securitizadora = ?, emissao = ?,
                   serie = ?, devedor = ?, cnpj_devedor = ?, isin = ?,
                   updated_at = ? WHERE asset_id = ?""",
                values + (existing["asset_id"],),
            )
            return int(existing["asset_id"])

        cursor = self.connection.execute(
            """INSERT INTO assets (
                codigo_cetip, tipo_ativo, securitizadora, cnpj_securitizadora,
                emissao, serie, devedor, cnpj_devedor, isin, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            values[:9] + (now, now),
        )
        return int(cursor.lastrowid)

    def _find_by_normalized(self, column: str, identifier: str):
        if column not in {"codigo_cetip", "isin"}:
            raise ValueError(f"Coluna de identificador inválida: {column}")
        matches = [
            row
            for row in self.connection.execute(f"SELECT * FROM assets WHERE {column} IS NOT NULL")
            if self._normalize_identifier(row[column]) == identifier
        ]
        if len(matches) > 1:
            raise ValueError(
                f"Identificador duplicado após normalização: {column}={identifier}"
            )
        return matches[0] if matches else None

    @staticmethod
    def _normalize_identifier(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = "".join(
            character
            for character in value
            if not character.isspace()
            and unicodedata.category(character) not in {"Cf", "Cc"}
        ).upper()
        return normalized or None

    @staticmethod
    def _normalize_series(value: str) -> str:
        normalized = value.strip()
        if normalized.casefold() in {"única", "unica"}:
            return "1"
        return normalized
