# Model router: heavy tasks (reading whole courses and PDFs, reconciling sources) go to Claude;
# interactive tasks (viva, tutor, gap messages) call the Agnes client directly.
# Heavy tasks fall back to Agnes when Claude is not configured or a Claude call fails.
import logging
import os

import anthropic
from pydantic import ValidationError

from backend.tools import agnes_client, claude_client

log = logging.getLogger("vidyapath.llm")
last_model = None  # the model that actually answered the most recent heavy call (after any fallback)


def heavy_provider():
    """'claude' when HEAVY_LLM_PROVIDER=claude (the default) and ANTHROPIC_API_KEY is set, else 'agnes'."""
    wanted = os.getenv("HEAVY_LLM_PROVIDER", "claude").lower()
    return "claude" if wanted == "claude" and claude_client.available() else "agnes"


def heavy_model():
    return claude_client.MODEL if heavy_provider() == "claude" else agnes_client.MODEL


def heavy_json(system, user, schema):
    global last_model
    if heavy_provider() == "claude":
        try:
            result = claude_client.chat_json(system, user, schema)
            last_model = claude_client.MODEL
            return result
        except (anthropic.APIError, claude_client.ClaudeOutputError, ValidationError) as err:
            log.warning("Claude call failed (%s); falling back to Agnes", err)
    result = agnes_client.chat_json(system, user, schema)
    last_model = agnes_client.MODEL
    return result
