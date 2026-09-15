from __future__ import annotations
import logging
from credit_assets.collectors.base_collector import BaseCollector
from credit_assets.models.asset import Asset
from credit_assets.models.document import Document

logger = logging.getLogger(__name__)

class FundosNetCollector(BaseCollector):
    """Primeiro conector real. O endpoint de listagem será integrado após a captura XHR/HAR."""
    def collect_documents(self, asset: Asset) -> list[Document]:
        logger.warning("Fundos.NET ainda sem endpoint de listagem confirmado para %s", asset.codigo_cetip)
        return []
