# Phone nudges: when the agents change a student's path, the student gets the message on their phone (Telegram bot).
# Opt-in: the student opens the bot from a one-time link and taps Start; only then can the bot message them.
# Sending never breaks the app: every message is logged as sent or failed, and the path changes either way.
import json
import os
import secrets
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

from backend import auth, sql

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
API = os.getenv("TELEGRAM_API_BASE", "https://api.telegram.org").rstrip("/")  # overridable for tests
PUBLIC_URL = os.getenv("PUBLIC_URL", "").rstrip("/")  # e.g. https://<app>.up.railway.app, for links in messages
TIMEOUT_SECONDS = 8

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS phone_links (
    student_id TEXT PRIMARY KEY,
    chat_id TEXT,                  -- set once the student pressed Start in the bot
    link_code TEXT,                -- one-time code in the t.me link, until linked
    linked_at TEXT
);

CREATE TABLE IF NOT EXISTS nudges (
    id {sql.ID},
    student_id TEXT,
    course TEXT,
    kind TEXT,                     -- welcome / test / path_change / misconception
    text TEXT,
    status TEXT,                   -- sent / failed / not_linked
    error TEXT,
    created_at TEXT DEFAULT {sql.NOW}
);
"""

_schema_ready = False
_bot_username = None


def _conn():
    global _schema_ready
    conn = sql.connect(auth.AUTH_DB)  # shared by all courses: Postgres public schema, or the local accounts file
    if not _schema_ready:
        with sql.connect(auth.AUTH_DB) as c:
            c.script(SCHEMA)
        _schema_ready = True
    return conn


def configured():
    return bool(TOKEN)


def _call(method, payload=None):
    req = urllib.request.Request(f"{API}/bot{TOKEN}/{method}", data=json.dumps(payload or {}).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        data = json.loads(e.read() or b"{}")
    if not data.get("ok"):
        raise RuntimeError(data.get("description") or f"Telegram {method} failed")
    return data["result"]


def bot_username():
    global _bot_username
    if _bot_username is None and configured():
        _bot_username = _call("getMe")["username"]
    return _bot_username


# --------------------------------------------------------------------------- #
# Linking a student's phone
# --------------------------------------------------------------------------- #
def status(student_id, limit=8):
    with _conn() as conn:
        link = conn.execute("SELECT chat_id, linked_at FROM phone_links WHERE student_id = ?", (student_id,)).fetchone()
        recent = conn.execute("SELECT kind, text, status, error, course, created_at FROM nudges WHERE student_id = ? "
                              "ORDER BY id DESC LIMIT ?", (student_id, limit)).fetchall()
    linked = bool(link and link["chat_id"])
    return {"configured": configured(), "linked": linked, "linked_at": link["linked_at"] if linked else None,
            "recent": [dict(r) for r in recent]}


def start_link(student_id):
    """A one-time t.me link: opening it and pressing Start tells the bot who this phone belongs to."""
    code = secrets.token_urlsafe(9).replace("-", "a").replace("_", "b")  # Telegram start payload: A-Z a-z 0-9 _ -
    with _conn() as conn:
        conn.execute("INSERT INTO phone_links (student_id, link_code) VALUES (?, ?) "
                     "ON CONFLICT (student_id) DO UPDATE SET link_code = excluded.link_code", (student_id, code))
    return {"url": f"https://t.me/{bot_username()}?start={code}", "bot": bot_username()}


def finish_link(student_id, name):
    """Looks for '/start <code>' among the bot's recent messages and saves that chat."""
    with _conn() as conn:
        row = conn.execute("SELECT link_code FROM phone_links WHERE student_id = ?", (student_id,)).fetchone()
    if not row or not row["link_code"]:
        raise ValueError("Press Connect Telegram first")
    want = f"/start {row['link_code']}"
    chat_id = None
    for update in _call("getUpdates", {"allowed_updates": ["message"]}):
        msg = update.get("message") or {}
        if (msg.get("text") or "").strip() == want:
            chat_id = str(msg["chat"]["id"])
    if not chat_id:
        raise ValueError("Not found yet: open the bot from the link, tap Start, then try again")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    with _conn() as conn:
        conn.execute("UPDATE phone_links SET chat_id = ?, link_code = NULL, linked_at = ? WHERE student_id = ?",
                     (chat_id, now, student_id))
    send(student_id, "welcome", f"Hi {name}! VidyaPath will message you here when your learning path changes, "
                                "so you can fix a gap before it appears.")
    return status(student_id)


def unlink(student_id):
    with _conn() as conn:
        conn.execute("DELETE FROM phone_links WHERE student_id = ?", (student_id,))


# --------------------------------------------------------------------------- #
# Sending
# --------------------------------------------------------------------------- #
def send(student_id, kind, text, course=None, link_path=None):
    """Sends `text` to the student's phone if they connected one. Never raises: returns sent / failed / not_linked."""
    if not configured():
        return {"status": "not_configured"}
    try:
        with _conn() as conn:
            link = conn.execute("SELECT chat_id FROM phone_links WHERE student_id = ?", (student_id,)).fetchone()
        if not link or not link["chat_id"]:
            return {"status": "not_linked"}
        body = text + (f"\n\nOpen VidyaPath: {PUBLIC_URL}{link_path}" if PUBLIC_URL and link_path else "")
        status_, error = "sent", None
        try:
            _call("sendMessage", {"chat_id": link["chat_id"], "text": body, "disable_web_page_preview": True})
        except Exception as e:  # blocked bot, network, bad token...
            status_, error = "failed", str(e)[:300]
            print(f"Nudge to {student_id} failed: {error}", file=sys.stderr)
        with _conn() as conn:
            conn.execute("INSERT INTO nudges (student_id, course, kind, text, status, error) VALUES (?, ?, ?, ?, ?, ?)",
                         (student_id, course, kind, text, status_, error))
        return {"status": status_, "error": error}
    except Exception as e:  # even the log failing must not break the request that triggered the nudge
        print(f"Nudge to {student_id} not sent: {e}", file=sys.stderr)
        return {"status": "failed", "error": str(e)[:300]}
