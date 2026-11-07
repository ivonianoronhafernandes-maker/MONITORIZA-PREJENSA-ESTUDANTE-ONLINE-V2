"""Browser cookies from Streamlit.

Streamlit can read cookies (``st.context.cookies``) but cannot set them, so
they are written by a tiny script that runs in the page itself
(``st.html(..., unsafe_allow_javascript=True)``). Only our own fixed scripts
are injected; values are JSON-escaped. Cookies written this way reach the
server on the next page load / websocket connection.
"""
from __future__ import annotations

import json
import secrets

import streamlit as st

DEVICE_COOKIE = "att_device"
ADMIN_COOKIE = "att_admin"
_PENDING_KEY = "_pending_cookies"
_ONE_YEAR = 365 * 24 * 3600


def run_js(code: str) -> None:
    """Run a snippet of our own JavaScript in the page (wrapped so reruns never clash)."""
    st.html(f"<script>(() => {{ {code} }})();</script>", unsafe_allow_javascript=True)


def get_cookie(name: str) -> str | None:
    try:
        value = st.context.cookies.get(name)
    except Exception:
        return None
    return value if isinstance(value, str) and value else None


def client_ip() -> str | None:
    try:
        ip = st.context.ip_address
    except Exception:
        return None
    return ip if isinstance(ip, str) else None


def _cookie_js(name: str, value: str, max_age: int) -> str:
    return (
        f"document.cookie = {json.dumps(name)} + '=' + encodeURIComponent({json.dumps(value)})"
        f" + '; path=/; max-age={int(max_age)}; SameSite=Lax';"
    )


def queue_cookie(name: str, value: str, max_age: int) -> None:
    """Set a cookie on the next render (survives st.rerun)."""
    st.session_state.setdefault(_PENDING_KEY, []).append((name, value, max_age))


def queue_delete_cookie(name: str) -> None:
    queue_cookie(name, "", 0)


def flush_cookies() -> None:
    """Write queued cookies. Call once per script run, before page content."""
    pending = st.session_state.pop(_PENDING_KEY, [])
    if pending:
        run_js("".join(_cookie_js(n, v, a) for n, v, a in pending))


def ensure_device_id() -> str | None:
    """Return this browser's device id, creating it on first visit.

    On the first visit the cookie is written and the page reloads once so the
    server can read it. If the browser blocks cookies the reload is not
    repeated and ``None`` is returned after the caller shows a notice.
    """
    device_id = get_cookie(DEVICE_COOKIE)
    if device_id:
        return device_id

    new_id = secrets.token_urlsafe(16)
    run_js(
        f"""
        if (!document.cookie.includes({json.dumps(DEVICE_COOKIE + "=")})) {{
            {_cookie_js(DEVICE_COOKIE, new_id, _ONE_YEAR)}
        }}
        if (!sessionStorage.getItem("att_device_reloaded")) {{
            sessionStorage.setItem("att_device_reloaded", "1");
            window.location.reload();
        }}"""
    )
    return None
