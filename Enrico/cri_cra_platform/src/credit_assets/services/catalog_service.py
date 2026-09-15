from credit_assets.collectors.base_collector import BaseCollector
from credit_assets.models.asset import Asset

class CatalogService:
    def __init__(self, collector: BaseCollector):
        self.collector = collector

    def catalog(self, asset: Asset):
        return self.collector.collect_documents(asset)
