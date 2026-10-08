# Authentication: user accounts (faculty + students), salted password hashes, JWT tokens and profiles.
# Accounts are global (one login works for every course); student progress stays in each course's database.
import hashlib
import hmac
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

AUTH_DB = Path("data/auth.db")
SECRET_FILE = Path("data/.jwt_secret")  # generated once if JWT_SECRET is not set in .env (gitignored)
TOKEN_HOURS = 12
HASH_ITERATIONS = 200_000
DEFAULT_ADMIN = ("admin", "admin123")  # master faculty login, created on first start
STUDENT_FIELDS = ("name", "stated_style", "pace", "target_role")
PROFILE_FIELDS = ("name", "department", "email", "bio", "photo")
MAX_PHOTO_CHARS = 400_000  # the UI shrinks photos to a small JPEG data URL first

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    role TEXT NOT NULL,              -- faculty / student
    password_hash TEXT NOT NULL,
    student_id TEXT,                 -- for students: their id in every course database
    created_by TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS student_registry (
    id TEXT PRIMARY KEY,             -- students created by faculty, copied into every course database
    name TEXT NOT NULL,
    stated_style TEXT,
    pace TEXT,
    target_role TEXT
);

CREATE TABLE IF NOT EXISTS profiles (
    username TEXT PRIMARY KEY,
    name TEXT, department TEXT, email TEXT, bio TEXT, photo TEXT,
    updated_at TEXT
);
"""


_schema_ready = False


def _conn():
    global _schema_ready
    AUTH_DB.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(AUTH_DB)
    conn.row_factory = sqlite3.Row
    if not _schema_ready:  # scripts may use accounts before the API's startup ran
        conn.executescript(SCHEMA)
        _schema_ready = True
    return conn


def _secret():
    if os.getenv("JWT_SECRET"):
        return os.getenv("JWT_SECRET")
    if not SECRET_FILE.exists():
        SECRET_FILE.parent.mkdir(exist_ok=True)
        SECRET_FILE.write_text(secrets.token_hex(32), encoding="utf-8")
        SECRET_FILE.chmod(0o600)
    return SECRET_FILE.read_text(encoding="utf-8").strip()


# --------------------------------------------------------------------------- #
# Passwords and tokens
# --------------------------------------------------------------------------- #
def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, HASH_ITERATIONS)
    return f"pbkdf2_sha256${HASH_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password, stored):
    try:
        _, iterations, salt, expected = stored.split("$")
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), int(iterations))
    return hmac.compare_digest(digest.hex(), expected)


def create_token(user):
    now = datetime.now(timezone.utc)
    claims = {"sub": user["username"], "role": user["role"], "sid": user["student_id"],
              "iat": now, "exp": now + timedelta(hours=TOKEN_HOURS)}
    return jwt.encode(claims, _secret(), algorithm="HS256")


def _public(user):
    return {"username": user["username"], "role": user["role"], "student_id": user["student_id"]}


# --------------------------------------------------------------------------- #
# Accounts
# --------------------------------------------------------------------------- #
def init_auth():
    """Creates the tables and the master faculty login (admin / admin123) if no faculty account exists."""
    with _conn() as conn:
        conn.executescript(SCHEMA)
        if not conn.execute("SELECT 1 FROM users WHERE role = 'faculty'").fetchone():
            username, password = DEFAULT_ADMIN
            conn.execute("INSERT INTO users (username, role, password_hash, created_by, created_at) VALUES (?,?,?,?,?)",
                         (username, "faculty", hash_password(password), "system", datetime.now().isoformat(timespec="seconds")))
            print(f"Created master faculty login '{username}' with the default password. Change it on the profile page.")


def authenticate(username, password):
    with _conn() as conn:
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username.strip().lower(),)).fetchone()
    if not user or not verify_password(password, user["password_hash"]):
        return None
    return _public(user)


def get_user(username):
    with _conn() as conn:
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    return _public(user) if user else None


def student_logins():
    """{student_id: username} for every student that has a login."""
    with _conn() as conn:
        return {r["student_id"]: r["username"] for r in conn.execute("SELECT username, student_id FROM users WHERE role = 'student'")}


def registered_students():
    with _conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM student_registry")]


def register_student(student):
    with _conn() as conn:
        conn.execute("INSERT OR REPLACE INTO student_registry (id, name, stated_style, pace, target_role) "
                     "VALUES (?,?,?,?,?)", (student["id"], *(student[f] for f in STUDENT_FIELDS)))


def create_student_login(student_id, password, created_by):
    """The login name of a student is their student id."""
    username = student_id.lower()
    with _conn() as conn:
        if conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
            raise ValueError(f"A login named '{username}' already exists")
        conn.execute("INSERT INTO users (username, role, password_hash, student_id, created_by, created_at) VALUES (?,?,?,?,?,?)",
                     (username, "student", hash_password(password), student_id, created_by,
                      datetime.now().isoformat(timespec="seconds")))
    return username


def set_password(username, password):
    with _conn() as conn:
        changed = conn.execute("UPDATE users SET password_hash = ? WHERE username = ?",
                               (hash_password(password), username)).rowcount
    if not changed:
        raise ValueError(f"No login named '{username}'")


def delete_login(username):
    with _conn() as conn:
        conn.execute("DELETE FROM users WHERE username = ? AND role = 'student'", (username,))
        conn.execute("DELETE FROM profiles WHERE username = ?", (username,))


def get_profile(username):
    with _conn() as conn:
        row = conn.execute("SELECT * FROM profiles WHERE username = ?", (username,)).fetchone()
    return {f: (row[f] if row else None) for f in PROFILE_FIELDS}


def save_profile(username, data):
    photo = data.get("photo") or None
    if photo and (not photo.startswith("data:image/") or len(photo) > MAX_PHOTO_CHARS):
        raise ValueError("Photo must be a small image")
    values = [str(data.get(f) or "").strip()[:2000] if f != "photo" else photo for f in PROFILE_FIELDS]
    with _conn() as conn:
        conn.execute(f"INSERT OR REPLACE INTO profiles (username, {', '.join(PROFILE_FIELDS)}, updated_at) "
                     f"VALUES (?, {', '.join('?' * len(PROFILE_FIELDS))}, ?)",
                     (username, *values, datetime.now().isoformat(timespec="seconds")))
    return get_profile(username)


# --------------------------------------------------------------------------- #
# FastAPI dependencies: who is calling, and may they see this?
# --------------------------------------------------------------------------- #
_bearer = HTTPBearer(auto_error=False)


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)):
    if credentials is None:
        raise HTTPException(401, "Please log in", headers={"WWW-Authenticate": "Bearer"})
    try:
        claims = jwt.decode(credentials.credentials, _secret(), algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Your session has expired. Please log in again.", headers={"WWW-Authenticate": "Bearer"})
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid login token", headers={"WWW-Authenticate": "Bearer"})
    user = get_user(claims["sub"])  # the account may have been removed since the token was issued
    if not user:
        raise HTTPException(401, "This login no longer exists", headers={"WWW-Authenticate": "Bearer"})
    return user


def require_faculty(user=Depends(current_user)):
    if user["role"] != "faculty":
        raise HTTPException(403, "Faculty only")
    return user


def check_student_access(user, student_id):
    """Faculty may open any student; a student only themselves."""
    if user["role"] != "faculty" and user["student_id"] != student_id:
        raise HTTPException(403, "You can only access your own data")

