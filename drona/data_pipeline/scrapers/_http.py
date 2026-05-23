"""
Shared polite HTTP client for D.R.O.N.A. scrapers.

Key properties:
- Per-portal rate limiting (token bucket at 0.5 req/s default → 2s gap)
- Respects robots.txt (verified manually; this client does NOT re-check at runtime)
- Custom User-Agent that identifies the research bot and provides a contact address
- Exponential backoff on transient errors (429 / 5xx)
- All network calls go through `get()` or `get_xml()` — never call httpx directly
"""

from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock
from typing import Any

import httpx
from bs4 import BeautifulSoup
from loguru import logger

from drona.utils.settings import settings


class _TokenBucket:
    """Thread-safe token bucket for rate limiting one host at a time."""

    def __init__(self, rate: float) -> None:
        self._rate = rate          # tokens/second
        self._tokens = 1.0         # start with one token
        self._last_check = time.monotonic()
        self._lock = Lock()

    def consume(self) -> None:
        """Block until a token is available, then consume one."""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_check
            self._tokens = min(1.0, self._tokens + elapsed * self._rate)
            self._last_check = now
            if self._tokens < 1.0:
                wait = (1.0 - self._tokens) / self._rate
                time.sleep(wait)
                self._tokens = 0.0
            else:
                self._tokens -= 1.0


class PoliteScraper:
    """Shared HTTP client with per-host rate limiting and retry logic."""

    _MAX_RETRIES = 3
    _RETRY_STATUSES = {429, 500, 502, 503, 504}

    def __init__(self, rate_per_second: float | None = None) -> None:
        rate = rate_per_second or settings.scraper_requests_per_second
        self._client = httpx.Client(
            headers={"User-Agent": settings.scraper_user_agent},
            timeout=settings.scraper_timeout_seconds,
            follow_redirects=True,
        )
        self._buckets: dict[str, _TokenBucket] = defaultdict(lambda: _TokenBucket(rate))

    def _host(self, url: str) -> str:
        return httpx.URL(url).host

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        """Polite GET with rate limiting and retry."""
        host = self._host(url)
        for attempt in range(self._MAX_RETRIES):
            self._buckets[host].consume()
            try:
                r = self._client.get(url, **kwargs)
                if r.status_code in self._RETRY_STATUSES:
                    wait = 2 ** attempt
                    logger.warning(f"HTTP {r.status_code} for {url}; retrying in {wait}s")
                    time.sleep(wait)
                    continue
                r.raise_for_status()
                return r
            except httpx.TransportError as e:
                wait = 2 ** attempt
                logger.warning(f"Transport error for {url}: {e}; retrying in {wait}s")
                time.sleep(wait)
        raise RuntimeError(f"Failed to fetch {url} after {self._MAX_RETRIES} retries")

    def get_soup(self, url: str, **kwargs: Any) -> BeautifulSoup:
        r = self.get(url, **kwargs)
        return BeautifulSoup(r.text, "lxml")

    def get_xml(self, url: str) -> BeautifulSoup:
        r = self.get(url)
        return BeautifulSoup(r.text, "xml")

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "PoliteScraper":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


# Module-level default instance — importable directly
default_scraper = PoliteScraper()
