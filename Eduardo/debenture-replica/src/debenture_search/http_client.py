import time
from urllib.request import Request, urlopen

class RateLimitedHttpClient:
    def __init__(self, min_interval=1.0, timeout=15):
        self.min_interval, self.timeout, self._last = min_interval, timeout, 0.0
    def get(self, url, headers=None):
        wait = self.min_interval - (time.monotonic()-self._last)
        if wait > 0: time.sleep(wait)
        req = Request(url, headers=headers or {"User-Agent":"debenture-search/0.1"})
        with urlopen(req, timeout=self.timeout) as r: data = r.read()
        self._last = time.monotonic()
        return data
