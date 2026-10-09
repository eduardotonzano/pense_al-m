from credit_assets.collectors.base_collector import BaseCollector
from credit_assets.models.asset import Asset


class CatalogService:
    def __init__(self, collector: BaseCollector):
        self.collector = collector

    def catalog(self, asset: Asset, run_id: str):
        if not run_id or not run_id.strip():
            raise ValueError("run_id é obrigatório para catalogar documentos")
        documents = self.collector.collect_documents(asset, run_id)
        if any(document.run_id != run_id for document in documents):
            raise ValueError("o coletor retornou documento de outra execução")
        return documents

    def catalog_with_metrics(self, asset: Asset, run_id: str):
        if not run_id or not run_id.strip():
            raise ValueError("run_id é obrigatório para catalogar documentos")
        collect_with_metrics = getattr(self.collector, "collect_with_metrics", None)
        if collect_with_metrics is None:
            raise TypeError("coletor não oferece métricas de coleta")
        result = collect_with_metrics(asset, run_id)
        if any(document.run_id != run_id for document in result.documents):
            raise ValueError("o coletor retornou documento de outra execução")
        return result
