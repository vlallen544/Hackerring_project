"""Request queue — rate limit, exponential backoff and response cache.

Sits between the API layer and the LLM so a burst of faculty uploads during a
class does not blow the Agnes RPM budget.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

DEFAULT_MAX_RPM = int(__import__("os").getenv("MAX_REQUESTS_PER_MINUTE", "60"))
DEFAULT_CONCURRENCY = 4
DEFAULT_TIMEOUT = float(__import__("os").getenv("REQUEST_TIMEOUT_SECONDS", "120"))
CACHE_CAP = 512


@dataclass
class QueueStats:
    enqueued: int = 0
    completed: int = 0
    failed: int = 0
    cache_hits: int = 0
    retries: int = 0
    _starts: list = field(default_factory=list)

    def snapshot(self) -> dict:
        now = time.time()
        recent = [t for t in self._starts if now - t < 60.0]
        return {
            "enqueued": self.enqueued,
            "completed": self.completed,
            "failed": self.failed,
            "cache_hits": self.cache_hits,
            "retries": self.retries,
            "rpm_in_use": len(recent),
        }


class RequestQueue:
    """Serialises LLM calls behind a sliding-window RPM limit."""

    def __init__(self, max_rpm: int = DEFAULT_MAX_RPM,
                 concurrency: int = DEFAULT_CONCURRENCY,
                 timeout: float = DEFAULT_TIMEOUT) -> None:
        self.max_rpm = max_rpm
        self.timeout = timeout
        self._sem = asyncio.Semaphore(concurrency)
        self._window: list[float] = []
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self.stats = QueueStats()

    # -- cache -----------------------------------------------------------
    @staticmethod
    def key(*args: Any, **kwargs: Any) -> str:
        blob = json.dumps({"a": args, "k": kwargs}, sort_keys=True, default=str)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def _cache_get(self, key: str) -> Any | None:
        if key in self._cache:
            self._cache.move_to_end(key)
            self.stats.cache_hits += 1
            return self._cache[key]
        return None

    def _cache_put(self, key: str, value: Any) -> None:
        self._cache[key] = value
        self._cache.move_to_end(key)
        while len(self._cache) > CACHE_CAP:
            self._cache.popitem(last=False)

    # -- rate limiting ---------------------------------------------------
    async def _acquire(self) -> None:
        while True:
            now = time.time()
            self._window = [t for t in self._window if now - t < 60.0]
            if len(self._window) < self.max_rpm:
                self._window.append(now)
                return
            await asyncio.sleep(max(0.05, 60.0 - (now - self._window[0])))

    # -- public API ------------------------------------------------------
    async def submit(self, fn: Callable[[], Awaitable[Any]], *,
                     cache_key: Optional[str] = None, retries: int = 3) -> Any:
        """Run `fn` under the RPM limit, with optional caching and backoff."""
        if cache_key:
            hit = self._cache_get(cache_key)
            if hit is not None:
                return hit

        self.stats.enqueued += 1
        last_error: Exception | None = None

        async with self._sem:
            for attempt in range(retries):
                try:
                    await self._acquire()
                    self._window.append(time.time())
                    self.stats._starts.append(time.time())
                    result = await asyncio.wait_for(fn(), timeout=self.timeout)
                    self.stats.completed += 1
                    if cache_key:
                        self._cache_put(cache_key, result)
                    return result
                except asyncio.TimeoutError as exc:
                    last_error = exc
                except Exception as exc:  # noqa: BLE001 — retried below
                    last_error = exc
                self.stats.retries += 1
                await asyncio.sleep(min(2 ** attempt, 8))

        self.stats.failed += 1
        raise last_error if last_error else RuntimeError("queue failure")
