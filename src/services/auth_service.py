"""Admin accounts and sign-in.

Passwords are stored as salted PBKDF2 hashes. A successful sign-in creates a
server-side session whose random token lives in a browser cookie, so the
admin stays signed in after a page refresh until signing out or expiry.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import timedelta

import streamlit as st

from src.core.config import now_local, settings
from src.data import database as db
from src.core import browser

_SESSION_KEY = "admin_authenticated"
_ITERATIONS = 200_000
MIN_PASSWORD_LENGTH = 8


# ---- password hashing ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _ITERATIONS).hex()
    return f"pbkdf2_sha256${_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt, digest = stored.split("$")
    except ValueError:
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations)).hex()
    return hmac.compare_digest(candidate, digest)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ---- accounts -----------------------------------------------------------------------------------

def ensure_default_admin() -> None:
    """Create the first admin only with a configured strong password."""
    if not db.fetch_one("SELECT 1 FROM admins LIMIT 1"):
        password = settings.admin_password

        if not password or len(password) < 12:
            raise RuntimeError(
                "Set ADMIN_PASSWORD to a strong password "
                "of at least 12 characters before starting."
            )

        if password == "admin123":
            raise RuntimeError("Default admin password is not allowed.")

        create_admin(settings.admin_username, password)


def create_admin(username: str, password: str, *, validate: bool = True) -> None:
    username = username.strip()
    if not username:
        raise ValueError("Naran uzuáriu obrigatóriu.")
    if validate and len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password tenke iha karakter {MIN_PASSWORD_LENGTH} ka liu.")
    if db.fetch_one("SELECT 1 FROM admins WHERE username = ?", (username,)):
        raise ValueError(f"Admin '{username}' iha ona.")
    db.execute(
        "INSERT INTO admins (username, password_hash, created_at) VALUES (?, ?, ?)",
        (username, hash_password(password), now_local().isoformat(sep=" ")),
    )


def change_password(username: str, current: str, new: str) -> None:
    row = db.fetch_one("SELECT password_hash FROM admins WHERE username = ?", (username,))
    if not row or not verify_password(current, row["password_hash"]):
        raise ValueError("Password agora sala.")
    if len(new) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password foun tenke iha karakter {MIN_PASSWORD_LENGTH} ka liu.")
    db.execute("UPDATE admins SET password_hash = ? WHERE username = ?", (hash_password(new), username))


def delete_admin(username: str, *, current_user: str) -> None:
    if username == current_user:
        raise ValueError("Ita labele hamoos konta ne'ebé ita uza agora.")
    db.execute("DELETE FROM admins WHERE username = ?", (username,))


def list_admins() -> list[dict]:
    return db.fetch_df("SELECT username, created_at FROM admins ORDER BY username").to_dict("records")


def uses_default_password(username: str) -> bool:
    row = db.fetch_one("SELECT password_hash FROM admins WHERE username = ?", (username,))
    return bool(row) and verify_password("admin123", row["password_hash"])


# ---- sign-in state ------------------------------------------------------------------------------

def _set_signed_in(username: str) -> None:
    st.session_state[_SESSION_KEY] = True
    st.session_state["admin_username"] = username


def login(username: str, password: str) -> bool:
    username = username.strip()
    row = db.fetch_one("SELECT password_hash FROM admins WHERE username = ?", (username,))
    if not row or not verify_password(password, row["password_hash"]):
        st.session_state[_SESSION_KEY] = False
        return False

    token = secrets.token_urlsafe(32)
    expires = now_local() + timedelta(days=settings.admin_session_days)
    db.execute("DELETE FROM admin_sessions WHERE expires_at < ?", (now_local().isoformat(sep=" "),))
    db.execute(
        "INSERT INTO admin_sessions (token_hash, username, expires_at) VALUES (?, ?, ?)",
        (_token_hash(token), username, expires.isoformat(sep=" ")),
    )
    browser.queue_cookie(browser.ADMIN_COOKIE, token, settings.admin_session_days * 24 * 3600)
    _set_signed_in(username)
    return True


def restore_from_cookie() -> None:
    """Sign the admin back in after a page refresh, using the session cookie."""
    if st.session_state.get(_SESSION_KEY):
        return
    token = browser.get_cookie(browser.ADMIN_COOKIE)
    if not token:
        return
    row = db.fetch_one(
        "SELECT username FROM admin_sessions WHERE token_hash = ? AND expires_at > ?",
        (_token_hash(token), now_local().isoformat(sep=" ")),
    )
    if row:
        _set_signed_in(row["username"])


def logout() -> None:
    token = browser.get_cookie(browser.ADMIN_COOKIE)
    if token:
        db.execute("DELETE FROM admin_sessions WHERE token_hash = ?", (_token_hash(token),))
    browser.queue_delete_cookie(browser.ADMIN_COOKIE)
    st.session_state.pop(_SESSION_KEY, None)
    st.session_state.pop("admin_username", None)


def is_authenticated() -> bool:
    return bool(st.session_state.get(_SESSION_KEY))


def current_user() -> str | None:
    return st.session_state.get("admin_username") if is_authenticated() else None
