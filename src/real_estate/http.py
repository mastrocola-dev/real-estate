import time
from urllib.parse import urlparse

import httpx

from real_estate import robots

USER_AGENT = 'real-estate-research/0.1 (personal, non-commercial; low rate)'
RETRY_STATUS = {429, 500, 502, 503, 504}


class Disallowed(Exception):
    pass


class Client:
    def __init__(self, interval: float = 2.0, retries: int = 3):
        self.interval = interval
        self.retries = retries
        self.last: dict[str, float] = {}
        self.rules: dict[str, str] = {}
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

    def robots(self, url: str) -> str:
        parsed = urlparse(url)
        if parsed.netloc not in self.rules:
            response = self.fetch(f'{parsed.scheme}://{parsed.netloc}/robots.txt')
            self.rules[parsed.netloc] = response.text if response.status_code == 200 else ''
        return self.rules[parsed.netloc]

    def get(self, url: str) -> httpx.Response:
        if not robots.allowed(self.robots(url), USER_AGENT, url):
            raise Disallowed(url)
        return self.fetch(url)

    def fetch(self, url: str) -> httpx.Response:
        host = urlparse(url).netloc
        for attempt in range(self.retries + 1):
            self.wait(host)
            response = self.http.get(url)
            if response.status_code not in RETRY_STATUS or attempt == self.retries:
                return response
            time.sleep(self.interval * 2**attempt)
        raise AssertionError('unreachable')
