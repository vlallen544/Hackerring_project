<<<<<<< HEAD
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
=======
import hashlib
import json
import os
import re
import threading
import time
from collections import deque
from pathlib import Path

from dotenv import load_dotenv
from openai import APIConnectionError, APITimeoutError, InternalServerError, OpenAI, RateLimitError
from pydantic import BaseModel, ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

MODEL = os.getenv("AGNES_TEXT_MODEL", "agnes-3.0-flash")
CACHE = PROJECT_ROOT / ".cache"
CACHE.mkdir(exist_ok=True)

_calls = deque()
_rate_limit_lock = threading.Lock()
_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("AGNES_API_KEY")
        if not api_key:
            raise RuntimeError("AGNES_API_KEY is missing. Copy .env.example to .env and add your key.")
        _client = OpenAI(
            api_key=api_key,
            base_url=os.getenv("AGNES_BASE_URL", "https://apihub.agnes-ai.com/v1"),
        )
    return _client


def _wait_for_slot() -> None:
    while True:
        with _rate_limit_lock:
            now = time.time()
            while _calls and now - _calls[0] >= 60:
                _calls.popleft()
            if len(_calls) < 9:
                _calls.append(now)
                return
            delay = 60 - (now - _calls[0]) + 0.1
        time.sleep(delay)


@retry(
    retry=retry_if_exception_type(
        (APIConnectionError, APITimeoutError, InternalServerError, RateLimitError)
    ),
    stop=stop_after_attempt(5),
    wait=wait_exponential(min=4, max=60),
    reraise=True,
)
def _call_agnes(messages: list[dict[str, str]]) -> str:
    _wait_for_slot()
    response = _get_client().chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.2,
    )
    content = response.choices[0].message.content
    if content is None:
        raise ValueError("Agnes returned an empty response.")
    return content


def chat_text(system: str, user: str) -> str:
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    request = json.dumps({"model": MODEL, "messages": messages}, sort_keys=True, ensure_ascii=False)
    key = hashlib.sha256(request.encode("utf-8")).hexdigest()
    cache_file = CACHE / f"{key}.txt"
    if cache_file.exists():
        return cache_file.read_text(encoding="utf-8")

    answer = _call_agnes(messages)
    temporary_file = cache_file.with_suffix(".tmp")
    temporary_file.write_text(answer, encoding="utf-8")
    temporary_file.replace(cache_file)
    return answer


def _extract_json(text: str) -> dict:
    cleaned = re.sub(r"```(?:json)?", "", text, flags=re.IGNORECASE).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end < start:
        raise ValueError("Response did not contain a JSON object.")
    value = json.loads(cleaned[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("Response JSON must be an object.")
    return value


def chat_json(system: str, user: str, schema: type[BaseModel]) -> BaseModel:
    instruction = (
        f"{system}\n\nReply with ONLY valid JSON matching this schema:\n"
        f"{json.dumps(schema.model_json_schema(), ensure_ascii=False)}"
    )
    raw = chat_text(instruction, user)
    try:
        return schema.model_validate(_extract_json(raw))
    except (ValueError, ValidationError) as error:
        repair_prompt = (
            f"{user}\n\nYour last reply was invalid ({error}). "
            "Return corrected JSON only, matching the schema."
        )
        repaired = chat_text(instruction, repair_prompt)
        return schema.model_validate(_extract_json(repaired))
>>>>>>> 2057f69ca03c5caebdba6c4835b05860d7c98f8a
