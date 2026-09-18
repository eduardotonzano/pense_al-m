from ..models import Debenture, ManualInput, SourcedValue
from .base import CharacteristicsProvider

class ManualInputProvider(CharacteristicsProvider):
    name = "manual"
    priority = 1000
    def __init__(self, values: dict[str, ManualInput] | None = None): self.values = values or {}
    def search(self, query: str): return []
    def characteristics(self, asset_code: str):
        item = self.values.get(asset_code.upper())
        if not item: return None
        d = Debenture(asset_code=SourcedValue(asset_code.upper(), self.name))
        if item.rating is not None: d.rating = SourcedValue(item.rating, self.name)
        if item.rate is not None: d.spread = SourcedValue(item.rate, self.name)
        if item.outstanding_quantity is not None: d.outstanding_quantity = SourcedValue(item.outstanding_quantity, self.name)
        return d
