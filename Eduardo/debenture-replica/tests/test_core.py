from debenture_search.cache import SQLiteTTLCache
from debenture_search.models import Debenture, SourcedValue
from debenture_search.providers.snd import SndScraperProvider

def test_merge_does_not_replace_available_with_missing():
    d=Debenture(rating=SourcedValue("AAA","manual")); d.merge_from(Debenture()); assert d.rating.value=="AAA"
def test_parse_issuers():
    assert SndScraperProvider.parse_issuer_options('<select><option value="1">Empresa A</option></select>') == [("Empresa A","1")]
def test_cache(tmp_path):
    c=SQLiteTTLCache(tmp_path/"c.db"); c.set("x", {"a":1}, 30); assert c.get("x")=={"a":1}
