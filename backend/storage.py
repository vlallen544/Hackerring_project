# Files that must survive a redeploy. Railway's disk is wiped on every deploy, so when Postgres is configured each of
# these is also saved in Supabase, and restore() writes them back to disk at startup. The app keeps reading and writing
# ordinary files; call save()/delete() after changing one:
#   - JSON (source lists, built course data, faculty overrides): Postgres table public.saved_files
#   - uploaded documents: Supabase Storage (SUPABASE_URL + SUPABASE_SECRET_KEY), else the same Postgres table
# With local SQLite (no DATABASE_URL) the disk already persists, so these do nothing.
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from backend import sql

ROOT = Path.cwd().resolve()  # paths are saved relative to the folder the server runs in
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or ""
BUCKET = os.getenv("SUPABASE_BUCKET", "sources")

SCHEMA = """
CREATE TABLE IF NOT EXISTS saved_files (
    path TEXT PRIMARY KEY,         -- relative to the app folder, e.g. sample_data/sources.json
    content BYTEA,                 -- the file, unless it is in Supabase Storage
    in_storage BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TEXT DEFAULT (to_char(now() AT TIME ZONE 'utc', 'YYYY-MM-DD HH24:MI:SS'))
);
"""


def enabled():
    return sql.POSTGRES


def _use_storage():
    return bool(SUPABASE_URL and SUPABASE_KEY)


def _key(path):
    """The saved name of a file: its path inside the app folder (anything outside it is refused)."""
    return Path(path).resolve().relative_to(ROOT).as_posix()


_schema_ready = False


def _conn():
    global _schema_ready
    if not _schema_ready:
        with sql.connect(None) as conn:  # Postgres only: the public schema
            conn.script(SCHEMA)
        _schema_ready = True
    return sql.connect(None)


def save(path):
    """Saves the current contents of `path` so it survives the next deploy."""
    if not enabled():
        return
    key, data = _key(path), Path(path).read_bytes()
    in_storage = _use_storage() and not key.endswith(".json")
    if in_storage:
        _storage("POST", key, data)
    with _conn() as conn:
        conn.execute("INSERT INTO saved_files (path, content, in_storage) VALUES (?, ?, ?) ON CONFLICT (path) DO UPDATE "
                     "SET content = excluded.content, in_storage = excluded.in_storage, updated_at = excluded.updated_at",
                     (key, None if in_storage else data, in_storage))


def delete(path):
    """Forgets a saved file (after the app deleted it from disk)."""
    if not enabled():
        return
    key = _key(path)
    with _conn() as conn:
        row = conn.execute("DELETE FROM saved_files WHERE path = ? RETURNING in_storage", (key,)).fetchone()
    if row and row["in_storage"]:
        _storage("DELETE", key)


def restore():
    """At startup: writes every saved file back to disk (replacing the copy that came with the code)."""
    if not enabled():
        return
    with _conn() as conn:
        rows = conn.execute("SELECT path, content, in_storage FROM saved_files").fetchall()
    for row in rows:
        target = (ROOT / row["path"]).resolve()
        if not target.is_relative_to(ROOT):
            continue
        try:
            data = _storage("GET", row["path"]) if row["in_storage"] else bytes(row["content"])
        except Exception as e:  # keep starting: one missing file shouldn't take the whole site down
            print(f"Could not restore {row['path']}: {e}", file=sys.stderr)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    print(f"Restored {len(rows)} saved file(s) from Supabase", file=sys.stderr)


# --------------------------------------------------------------------------- #
# Supabase Storage (REST API)
# --------------------------------------------------------------------------- #
def _storage(method, key, data=None, _retry=True):
    url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{urllib.parse.quote(key)}"
    headers = {"apikey": SUPABASE_KEY}
    if SUPABASE_KEY.startswith("eyJ"):  # a legacy service_role JWT also goes in Authorization
        headers["Authorization"] = f"Bearer {SUPABASE_KEY}"
    if data is not None:
        headers.update({"Content-Type": "application/octet-stream", "x-upsert": "true"})
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers, method=method), timeout=120) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        if method == "DELETE" and e.code in (400, 404):
            return b""  # already gone
        if method == "POST" and _retry and "Bucket not found" in body:
            _create_bucket()
            return _storage(method, key, data, _retry=False)
        raise RuntimeError(f"Supabase Storage {method} {key} failed ({e.code}): {body[:200]}") from None


def _create_bucket():
    headers = {"apikey": SUPABASE_KEY, "Content-Type": "application/json"}
    if SUPABASE_KEY.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {SUPABASE_KEY}"
    body = json.dumps({"id": BUCKET, "name": BUCKET, "public": False}).encode()
    try:
        urllib.request.urlopen(urllib.request.Request(f"{SUPABASE_URL}/storage/v1/bucket", data=body, headers=headers,
                                                      method="POST"), timeout=30).read()
    except urllib.error.HTTPError as e:
        if e.code != 409 and "already exists" not in e.read().decode("utf-8", "replace"):
            raise RuntimeError(f"Could not create the Supabase Storage bucket '{BUCKET}' ({e.code})") from None
