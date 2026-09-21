from __future__ import annotations
from datetime import datetime, timezone
import sqlite3
from credit_assets.models.asset import Asset

class AssetRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def upsert(self, asset: Asset) -> int:
        now = datetime.now(timezone.utc).isoformat()
        self.connection.execute(
            """INSERT INTO assets (codigo_cetip,tipo_ativo,securitizadora,cnpj_securitizadora,emissao,serie,devedor,cnpj_devedor,isin,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(codigo_cetip) DO UPDATE SET tipo_ativo=excluded.tipo_ativo,securitizadora=excluded.securitizadora,cnpj_securitizadora=excluded.cnpj_securitizadora,emissao=excluded.emissao,serie=excluded.serie,devedor=excluded.devedor,cnpj_devedor=excluded.cnpj_devedor,isin=COALESCE(NULLIF(excluded.isin, ''), assets.isin),updated_at=excluded.updated_at""",
            (asset.codigo_cetip,asset.tipo_ativo,asset.securitizadora,asset.cnpj_securitizadora,asset.emissao,asset.serie,asset.devedor,asset.cnpj_devedor,asset.isin or "",now,now),
        )
        self.connection.commit()
        row = self.connection.execute("SELECT asset_id FROM assets WHERE codigo_cetip=?", (asset.codigo_cetip,)).fetchone()
        return int(row["asset_id"])
