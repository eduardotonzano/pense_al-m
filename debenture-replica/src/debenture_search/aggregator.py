from .models import Debenture
from .providers.base import SearchProvider, CharacteristicsProvider

class AmbiguousSearchError(Exception): pass
class NotFoundError(Exception): pass

class DebentureAggregator:
    def __init__(self, providers): self.providers = list(providers)
    def search(self, query: str):
        results = []
        for p in sorted(self.providers, key=lambda x: x.priority):
            if not p.available() or not isinstance(p, SearchProvider): continue
            try: results.extend(p.search(query))
            except Exception: continue
        unique = {}
        for d in results:
            key = d.asset_code.value or d.isin.value
            if key: unique[key] = d
        return list(unique.values())
    def get(self, query: str):
        candidates = self.search(query)
        if not candidates: raise NotFoundError(query)
        if len(candidates) > 1: raise AmbiguousSearchError(query)
        result = candidates[0]
        code = result.asset_code.value
        for p in sorted(self.providers, key=lambda x: x.priority):
            if not p.available() or not isinstance(p, CharacteristicsProvider): continue
            try:
                incoming = p.characteristics(code)
                if incoming: result.merge_from(incoming)
            except Exception: continue
        return result
