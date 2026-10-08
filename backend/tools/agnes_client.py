"""Agnes AI client — OpenAI-compatible SDK pointed at the Agnes API.

Handles rate limiting, retries with exponential backoff, and response caching.
`agnes-3.0-flash` takes text and image-URL input only: speech-to-text and
text-to-speech stay in the browser (Web Speech API).
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections import OrderedDict
from typing import Any, Iterable

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

BASE_URL = os.getenv("AGNES_BASE_URL", "https://apihub.agnes-ai.com/v1")
TEXT_MODEL = os.getenv("AGNES_TEXT_MODEL", "agnes-3.0-flash")
IMAGE_MODEL = os.getenv("AGNES_IMAGE_MODEL", "agnes-image-2.5-flash")
MAX_RPM = int(os.getenv("MAX_REQUESTS_PER_MINUTE", "60"))
CACHE_SIZE = 256

#: Rolling window of request timestamps for the client-side RPM guard.
_request_times: list[float] = []
#: Simple memo keyed on a hash of (model, messages).
_cache: OrderedDict[str, dict] = OrderedDict()


class RateLimitExceeded(Exception):
    """Raised when the local RPM window is full."""


def _get_client() -> "OpenAI":
    if OpenAI is None:
        raise RuntimeError("openai package not installed: pip install openai")
    api_key = os.getenv("AGNES_API_KEY")
    if not api_key:
        raise RuntimeError("AGNES_API_KEY is not set — see .env.example")
    return OpenAI(base_url=BASE_URL, api_key=api_key)


def _throttle() -> None:
    now = time.time()
    window = [t for t in _request_times if now - t < 60.0]
    _request_times[:] = window
    if len(_request_times) >= MAX_RPM:
        raise RateLimitExceeded(f"local RPM cap of {MAX_RPM} reached")
    _request_times.append(now)


def _cache_key(model: str, messages: list[dict]) -> str:
    payload = json.dumps({"m": model, "x": messages}, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _cache_get(key: str) -> dict | None:
    if key in _cache:
        _cache.move_to_end(key)
        return _cache[key]
    return None


def _cache_put(key: str, value: dict) -> None:
    _cache[key] = value
    _cache.move_to_end(key)
    while len(_cache) > CACHE_SIZE:
        _cache.popitem(last=False)


@retry(
    retry=retry_if_exception_type(Exception),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    stop=stop_after_attempt(4),
    reraise=True,
)
def chat(messages: list[dict], *, model: str = TEXT_MODEL,
         use_cache: bool = True) -> str:
    """Single-turn completion with throttle, backoff and cache."""
    key = _cache_key(model, messages)
    if use_cache:
        hit = _cache_get(key)
        if hit is not None:
            return hit["content"]

    _throttle()
    client = _get_client()
    response = client.chat.completions.create(
        model=model,
        messages=messages,  # type: ignore[arg-type]
        temperature=0.2,
    )
    content = response.choices[0].message.content or ""
    if use_cache:
        _cache_put(key, {"content": content})
    return content


def chat_json(messages: list[dict], *, model: str = TEXT_MODEL) -> Any:
    """`chat()` that parses the reply as JSON, stripping ``` fences."""
    raw = chat(messages, model=model).strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        if raw.endswith("```"):
            raw = raw[:-3]
    return json.loads(raw.strip())


def generate_image(prompt: str) -> str:
    """Return an image URL for a diagram / visual aid."""
    _throttle()
    client = _get_client()
    result = client.images.generate(model=IMAGE_MODEL, prompt=prompt, n=1)
    return result.data[0].url


def build_context(documents: Iterable[str], *, max_chars: int = 24_000) -> str:
    """Assemble retrieved material into a bounded prompt section."""
    parts, used = [], 0
    for doc in documents:
        if used + len(doc) > max_chars:
            break
        parts.append(doc)
        used += len(doc)
    return "\n\n---\n\n".join(parts)
