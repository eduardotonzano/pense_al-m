from abc import ABC, abstractmethod
from ..models import Debenture

class Provider(ABC):
    name = "provider"
    priority = 0
    def available(self) -> bool: return True

class SearchProvider(Provider):
    @abstractmethod
    def search(self, query: str) -> list[Debenture]: ...

class CharacteristicsProvider(Provider):
    @abstractmethod
    def characteristics(self, asset_code: str) -> Debenture | None: ...

class MarketDataProvider(Provider):
    @abstractmethod
    def market_data(self, asset_code: str): ...

class EventsProvider(Provider):
    @abstractmethod
    def events(self, asset_code: str): ...

class DocumentsProvider(Provider):
    @abstractmethod
    def documents(self, asset_code: str): ...
