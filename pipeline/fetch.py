"""Polite HTTP: one session, descriptive User-Agent, retries, small delays."""
from __future__ import annotations

import time

import requests

from .config import USER_AGENT


class Fetcher:
    def __init__(self, delay: float = 0.25, retries: int = 3):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = USER_AGENT
        self.delay = delay
        self.retries = retries
        self._last = 0.0
        self.count = 0

    def _wait(self):
        dt = time.time() - self._last
        if dt < self.delay:
            time.sleep(self.delay - dt)
        self._last = time.time()

    def get(self, url: str, **kw) -> requests.Response:
        kw.setdefault("timeout", 60)
        last_exc: Exception | None = None
        for attempt in range(self.retries):
            self._wait()
            try:
                r = self.s.get(url, **kw)
                self.count += 1
                if r.status_code in (429, 500, 502, 503, 504):
                    raise requests.HTTPError(f"{r.status_code} for {url}", response=r)
                r.raise_for_status()
                return r
            except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as e:
                last_exc = e
                time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"failed after {self.retries} attempts: {url}") from last_exc

    def post(self, url: str, **kw) -> requests.Response:
        kw.setdefault("timeout", 60)
        self._wait()
        r = self.s.post(url, **kw)
        self.count += 1
        r.raise_for_status()
        return r
