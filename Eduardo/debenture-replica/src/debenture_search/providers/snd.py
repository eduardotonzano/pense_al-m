import re
from html import unescape
from ..models import Debenture, Issuer, SourcedValue
from .base import SearchProvider, CharacteristicsProvider

class SndScraperProvider(SearchProvider, CharacteristicsProvider):
    name = "SND"
    priority = 100
    def __init__(self, http=None): self.http = http
    @staticmethod
    def normalize(text):
        import unicodedata
        return ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c)).casefold().strip()
    def search(self, query):
        # Network lookup is intentionally isolated here. Parsing helpers remain testable offline.
        return []
    def characteristics(self, asset_code): return None
    @classmethod
    def parse_issuer_options(cls, html):
        out=[]
        for value,label in re.findall(r'<option[^>]*value=["\']([^"\']+)["\'][^>]*>(.*?)</option>', html, re.I|re.S):
            label=re.sub('<[^>]+>','',unescape(label)).strip()
            if value.strip() and label: out.append((label,value.strip()))
        return out
    @classmethod
    def parse_characteristics(cls, html, asset_code):
        text=re.sub(r'\s+',' ',re.sub('<[^>]+>',' ',unescape(html)))
        d=Debenture(asset_code=SourcedValue(asset_code, cls.name))
        patterns={'isin':r'ISIN\s*[:\-]?\s*([A-Z]{2}[A-Z0-9]{10})','indexer':r'Indexador\s*[:\-]?\s*([^|;]{2,40})','rating':r'Rating\s*[:\-]?\s*([A-Za-z0-9+\-. ]{1,20})'}
        for field,pattern in patterns.items():
            m=re.search(pattern,text,re.I)
            if m: setattr(d,field,SourcedValue(m.group(1).strip(),cls.name))
        return d
