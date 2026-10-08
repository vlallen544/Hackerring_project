"""Shared agent plumbing.

Each agent is a plain async callable over a graph `state` dict. LangGraph owns
the orchestration; agents own prompts and the call into the Agnes client. Any
*numeric* verdict is delegated to `backend.engine`.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from backend.tools.agnes_client import build_context, chat, chat_json

#: System preamble shared by every agent — grounds answers in faculty material.
SYSTEM_PROMPT = (
    "You are VidyaPath, an expert teaching copilot for Indian higher education. "
    "Answer only from the provided source material. If the material does not "
    "support an answer, say so explicitly rather than inventing it. "
    "Match the requested language and the learner's level."
)


async def run(state: dict, *, instructions: str, json_mode: bool = False) -> Any:
    """Call the LLM with system + instructions + material already in `state`."""
    material = build_context(state.get("material_chunks", []))
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if material:
        messages.append({"role": "user", "content": f"SOURCE MATERIAL:\n{material}"})
    messages.append({"role": "user", "content": instructions})

    if json_mode:
        return await chat_json(messages)
    return await chat(messages)


def agent(name: str,
          handler: Callable[[dict], Awaitable[dict]]) -> Callable[[dict], Awaitable[dict]]:
    """Attach a name to an agent handler for the activity feed / SSE stream."""

    async def node(state: dict) -> dict:
        result = await handler(state)
        events = state.setdefault("events", [])
        events.append({"agent": name, "status": "done"})
        return result

    node.__name__ = name
    node.agent_name = name  # type: ignore[attr-defined]
    return node
