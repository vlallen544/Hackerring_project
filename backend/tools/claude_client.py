# Claude client (Anthropic SDK) for heavy tasks: reading whole courses and PDFs, reconciling sources.
# Returns the same validated Pydantic objects as the Agnes client, with structured JSON output and a local cache.
import copy
import hashlib
import json
import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5-5")
EFFORT = os.getenv("CLAUDE_EFFORT", "high")  # careful extraction is worth more thinking
MAX_TOKENS = 128000                          # large course outputs; needs streaming
CACHE = PROJECT_ROOT / ".cache" / "claude"
CACHE.mkdir(parents=True, exist_ok=True)

_client = None


class ClaudeOutputError(RuntimeError):
    """Claude finished without a usable answer (refused, or the output hit the length limit)."""


def available():
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(max_retries=4)  # reads ANTHROPIC_API_KEY; retries 429 / 5xx / network
    return _client


def _strict_schema(model):
    """Pydantic JSON schema -> structured-output schema: refs inlined, every object closed with all fields required."""
    schema = model.model_json_schema()
    defs = schema.pop("$defs", {})

    def walk(node):
        if isinstance(node, list):
            return [walk(item) for item in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            resolved = walk(copy.deepcopy(defs[node["$ref"].split("/")[-1]]))
            extra = {k: v for k, v in node.items() if k not in ("$ref", "title", "default")}
            return {**resolved, **extra}
        node = {k: walk(v) for k, v in node.items() if k not in ("title", "default")}
        if node.get("type") == "object":
            node["additionalProperties"] = False
            node["required"] = list(node.get("properties", {}))
        return node

    return walk(schema)


def chat_json(system: str, user: str, schema: type[BaseModel]) -> BaseModel:
    output_format = {"type": "json_schema", "schema": _strict_schema(schema)}
    request = json.dumps({"model": MODEL, "effort": EFFORT, "system": system, "user": user,
                          "format": output_format}, sort_keys=True, ensure_ascii=False)
    cache_file = CACHE / f"{hashlib.sha256(request.encode('utf-8')).hexdigest()}.json"
    if cache_file.exists():
        return schema.model_validate_json(cache_file.read_text(encoding="utf-8"))

    # Streaming keeps long requests clear of HTTP timeouts; fallbacks re-run a safety decline on the recommended model
    with _get_client().beta.messages.stream(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_config={"effort": EFFORT, "format": output_format},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    ) as stream:
        message = stream.get_final_message()

    if message.stop_reason == "refusal":
        raise ClaudeOutputError(f"Claude declined the request ({message.stop_details})")
    if message.stop_reason == "max_tokens":
        raise ClaudeOutputError("Claude's answer hit the output limit; use a smaller page range")
    text = "".join(block.text for block in message.content if block.type == "text")
    result = schema.model_validate_json(text)

    temporary_file = cache_file.with_suffix(".tmp")
    temporary_file.write_text(text, encoding="utf-8")
    temporary_file.replace(cache_file)
    return result
