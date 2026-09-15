from abc import ABC, abstractmethod
from credit_assets.models.asset import Asset
from credit_assets.models.document import Document

class BaseCollector(ABC):
    @abstractmethod
    def collect_documents(self, asset: Asset) -> list[Document]:
        raise NotImplementedError
