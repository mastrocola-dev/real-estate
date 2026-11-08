import time
from urllib.parse import urlparse

import httpx

USER_AGENT = 'real-estate-research/0.1 (personal, non-commercial; low rate)'
RETRY_STATUS = {429, 500, 502, 503, 504}


class Client:
    def __init__(self, interval: float = 2.0, retries: int = 3):
        self.interval = interval
        self.retries = retries
        self.last: dict[str, float] = {}
        self.http = httpx.Client(
            headers={'user-agent': USER_AGENT, 'accept-language': 'pt-BR,pt;q=0.9'},
            follow_redirects=True,
            timeout=30,
        )

    def wait(self, host: str):
        elapsed = time.monotonic() - self.last.get(host, 0)
        if elapsed < self.interval:
            time.sleep(self.interval - elapsed)
        self.last[host] = time.monotonic()

    def get(self, url: str) -> httpx.Response:
        host = urlparse(url).netloc
        for attempt in range(self.retries + 1):
            self.wait(host)
            response = self.http.get(url)
            if response.status_code not in RETRY_STATUS or attempt == self.retries:
                return response
            time.sleep(self.interval * 2**attempt)
        raise AssertionError('unreachable')
