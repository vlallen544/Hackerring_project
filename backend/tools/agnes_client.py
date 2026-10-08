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