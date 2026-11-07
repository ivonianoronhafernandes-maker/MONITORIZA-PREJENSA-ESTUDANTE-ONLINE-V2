"""Page chrome around every admin page: top bar (search, alerts, account) and sidebar status."""
from __future__ import annotations

import base64
import html
from datetime import datetime

import streamlit as st

from src.core.config import BASE_DIR
from src.services import settings_service, spark_analytics


_ICON_B64 = base64.b64encode((BASE_DIR / "assets" / "icon.svg").read_bytes()).decode()


def topbar() -> None:
    """Navy header with the system name on the left and the signed-in account on the right."""
    name = settings_service.get("system_name")
    with st.container(key="topbar"):
        title, account = st.columns([6, 1.4], vertical_alignment="center")
        title.markdown(
            f'<div class="tb-title"><img src="data:image/svg+xml;base64,{_ICON_B64}" alt="">'
            f"<span>{html.escape(name)}</span></div>",
            unsafe_allow_html=True,
        )
        account.markdown(
            '<div class="tb-user"><span class="tb-av">A</span><span>Admin</span></div>', unsafe_allow_html=True
        )


def sidebar_status() -> None:
    spark = spark_analytics.spark_status()
    snapshot = spark_analytics.load_snapshot() or {}
    stamp = snapshot.get("generated_at")
    try:
        updated = f"{datetime.fromisoformat(stamp):%d %b %Y %H:%M}" if stamp else "-"
    except ValueError:
        updated = str(stamp)
    state = ("on", "Sistema Ativu") if spark["online"] else ("on off", "Pipeline la ativu")
    with st.sidebar:
        st.markdown(
            f'<div class="side-status"><div class="{state[0]}">{state[1]}</div>'
            f"<small>Atualiza ikus: {html.escape(updated)}</small></div>",
            unsafe_allow_html=True,
        )


def register_pages(pages: dict) -> None:
    """App.py stores the page objects so any page can link to another one."""
    st.session_state["_pages"] = pages


def page(name: str):
    return st.session_state.get("_pages", {}).get(name)
