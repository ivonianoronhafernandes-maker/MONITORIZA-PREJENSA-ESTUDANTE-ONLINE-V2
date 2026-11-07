"""Shared UI building blocks: design system (CSS), cards, badges, charts and small JS widgets."""
from __future__ import annotations

import html
import io
import json
from datetime import date, timedelta

import plotly.graph_objects as go
import qrcode
import streamlit as st

from src.core import browser
from src.services import settings_service
from src.core.config import now_local, settings
from src.ui.theme import ADMIN_CSS, STATIC_CSS, status_text as theme_status

# Chart palette (matches the status colours used everywhere: green present, amber late, red absent).
SERIES = ["#1d63ed", "#f5a524", "#16a34a"]
STATUS_COLORS = {"Present": "#16a34a", "Late": "#f5a524", "Absent": "#ef4444"}
AQUA = "#16a34a"
VIOLET = "#7c3aed"
FONT = '"Plus Jakarta Sans", system-ui, -apple-system, "Segoe UI", sans-serif'

STATE_BADGES = {
    "open": ("Loke", "badge-good"),
    "upcoming": ("Tuir mai", "badge-info"),
    "ended": ("Remata", "badge-muted"),
    "closed": ("Taka", "badge-bad"),
    "cancelled": ("Kansela", "badge-muted"),
}

# ------------------------------------------------------------------------------------------------
# Design system
# ------------------------------------------------------------------------------------------------
_CSS = """
<style>
:root {
  --brand-1: #2a78d6;
  --brand-2: #6d5dfc;
  --brand-grad: linear-gradient(135deg, #2a78d6 0%, #6d5dfc 100%);
  --ink: #0f172a;
  --muted: #64748b;
  --line: #e2e8f0;
  --card: #ffffff;
  --good: #0a8a3a;  --good-bg: #e7f7ee;
  --bad: #c62f3b;   --bad-bg: #fdecee;
  --warn: #c2541c;  --warn-bg: #fff1e8;
  --info: #2a62c9;  --info-bg: #eaf1fd;
  --shadow-sm: 0 1px 2px rgba(15, 23, 42, .04), 0 1px 3px rgba(15, 23, 42, .06);
  --shadow-md: 0 10px 30px -12px rgba(15, 23, 42, .18);
  --shadow-brand: 0 18px 40px -18px rgba(79, 70, 229, .55);
}

/* ---- canvas ---- */
[data-testid="stAppViewContainer"] {
  /* soft colour mesh + faint dot grid instead of a plain white page */
  background:
    radial-gradient(rgba(15, 23, 42, .07) 1px, transparent 1.2px) 0 0 / 22px 22px,
    radial-gradient(900px 520px at 100% -5%, rgba(109, 93, 252, .20), transparent 60%),
    radial-gradient(760px 520px at -5% 25%, rgba(20, 184, 166, .16), transparent 58%),
    radial-gradient(900px 600px at 55% 115%, rgba(42, 120, 214, .16), transparent 60%),
    linear-gradient(180deg, #eef2fb 0%, #f4f1fd 100%);
  background-attachment: fixed;
}
[data-testid="stHeader"] { background: transparent; }
[data-testid="stDecoration"] { display: none; }
[data-testid="stMainBlockContainer"] { padding-top: 2.6rem; padding-bottom: 3rem; max-width: 1220px; }

/* ---- headings ---- */
.app-head { display: flex; align-items: center; justify-content: space-between; gap: 1rem;
            flex-wrap: wrap; margin-bottom: 1.4rem; }
.app-head .left { display: flex; align-items: center; gap: .9rem; }
.app-head .ic { width: 48px; height: 48px; border-radius: 14px; background: var(--brand-grad);
                display: grid; place-items: center; font-size: 1.45rem; box-shadow: var(--shadow-brand); }
.app-head h1 { font-size: 1.65rem; font-weight: 800; letter-spacing: -.02em; margin: 0; padding: 0;
               color: var(--ink); line-height: 1.2; }
.app-head .sub { color: var(--muted); font-size: .92rem; margin-top: .15rem; }
.app-head .when { background: var(--card); border: 1px solid var(--line); border-radius: 999px;
                  padding: .45rem .9rem; font-size: .82rem; color: var(--muted); box-shadow: var(--shadow-sm);
                  font-weight: 600; }
.section-title { display: flex; align-items: baseline; gap: .6rem; margin: .4rem 0 .6rem; }
.section-title h3 { font-size: 1.05rem; font-weight: 800; margin: 0; padding: 0; color: var(--ink); }
.section-title span { color: var(--muted); font-size: .82rem; }
.card-title { font-weight: 800; font-size: .95rem; color: var(--ink); margin-bottom: .45rem;
              display: flex; align-items: center; gap: .5rem; }
.card-title::before { content: ""; width: 4px; height: 1.05rem; border-radius: 4px;
                      background: linear-gradient(180deg, #6d5dfc, #14b8a6); }

/* ---- class code box ---- */
.class-code { display: flex; align-items: baseline; flex-wrap: wrap; gap: .35rem .8rem; padding: .75rem 1rem;
              margin-bottom: .6rem; border-radius: 14px; background: var(--info-bg); border: 1px dashed #9cc0f0; }
.class-code span { font-size: .72rem; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; color: var(--info); }
.class-code b { font-family: ui-monospace, Consolas, monospace; font-size: 1.5rem; letter-spacing: .12em; color: var(--ink); }
.class-code small { flex-basis: 100%; color: var(--muted); font-size: .78rem; }

/* ---- dashboard hero banner ---- */
.dash-hero { position: relative; overflow: hidden; border-radius: 24px; padding: 1.5rem 1.6rem; margin-bottom: 1.1rem;
             color: #fff; background: linear-gradient(120deg, #0f172a 0%, #312e81 48%, #0e7490 100%);
             box-shadow: 0 24px 50px -24px rgba(49, 46, 129, .65); }
.dash-hero::before { content: ""; position: absolute; width: 340px; height: 340px; right: -90px; top: -150px;
                     border-radius: 50%; background: radial-gradient(circle, rgba(45, 212, 191, .45), transparent 65%); }
.dash-hero::after { content: ""; position: absolute; width: 300px; height: 300px; left: 30%; bottom: -200px;
                    border-radius: 50%; background: radial-gradient(circle, rgba(167, 139, 250, .40), transparent 65%); }
.dash-hero > * { position: relative; z-index: 1; }
.dash-hero .row { display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem; flex-wrap: wrap; }
.dash-hero h1 { color: #fff; font-size: 1.75rem; font-weight: 800; letter-spacing: -.02em; margin: 0; padding: 0; }
.dash-hero p { color: #c7d2fe; margin: .3rem 0 0; font-size: .92rem; }
.dash-hero .pills { display: flex; gap: .5rem; flex-wrap: wrap; }
.dash-hero .pill { background: rgba(255, 255, 255, .12); border: 1px solid rgba(255, 255, 255, .2); border-radius: 999px;
                   padding: .35rem .8rem; font-size: .8rem; font-weight: 700; backdrop-filter: blur(6px); }
.dash-hero .live { display: inline-flex; align-items: center; gap: .45rem; color: #99f6e4; }
.dash-hero .live::before { content: ""; width: 8px; height: 8px; border-radius: 50%; background: #2dd4bf;
                           box-shadow: 0 0 0 0 rgba(45, 212, 191, .7); animation: ping 1.6s infinite; }
@keyframes ping { 0% { box-shadow: 0 0 0 0 rgba(45, 212, 191, .7); } 80%, 100% { box-shadow: 0 0 0 10px rgba(45, 212, 191, 0); } }

/* ---- coloured KPI cards ---- */
.kpis { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: .9rem; margin: .2rem 0 1.1rem; }
@media (max-width: 1100px) { .kpis { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 640px)  { .kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
.kpi { position: relative; overflow: hidden; background: var(--card); border: 1px solid var(--line); border-radius: 20px;
       padding: 1rem 1.05rem; box-shadow: var(--shadow-sm); transition: transform .18s ease, box-shadow .18s ease; }
.kpi:hover { transform: translateY(-3px); box-shadow: var(--shadow-md); }
.kpi::after { content: ""; position: absolute; right: -30px; top: -30px; width: 110px; height: 110px; border-radius: 50%;
              background: var(--tint); opacity: .12; }
.kpi .top { display: flex; align-items: center; justify-content: space-between; }
.kpi .ico { width: 42px; height: 42px; border-radius: 13px; display: grid; place-items: center; font-size: 1.2rem;
            background: var(--grad); box-shadow: 0 10px 20px -10px var(--tint); }
.kpi .lbl { font-size: .72rem; font-weight: 800; letter-spacing: .07em; text-transform: uppercase; color: var(--muted); margin-top: .8rem; }
.kpi .val { font-size: 2rem; font-weight: 800; letter-spacing: -.03em; color: var(--ink); line-height: 1.15; }
.kpi .sub { font-size: .78rem; color: var(--muted); font-weight: 600; margin-top: .1rem; }
.kpi .bar { height: 6px; border-radius: 999px; background: #eef2f7; margin-top: .55rem; overflow: hidden; }
.kpi .bar span { display: block; height: 100%; border-radius: 999px; background: var(--grad); }
.kpi.blue   { --tint: #2a78d6; --grad: linear-gradient(135deg, #2a78d6, #60a5fa); }
.kpi.violet { --tint: #6d5dfc; --grad: linear-gradient(135deg, #6d5dfc, #a78bfa); }
.kpi.teal   { --tint: #0d9488; --grad: linear-gradient(135deg, #0d9488, #2dd4bf); }
.kpi.amber  { --tint: #d97706; --grad: linear-gradient(135deg, #f59e0b, #fcd34d); }
.kpi.rose   { --tint: #e11d48; --grad: linear-gradient(135deg, #e11d48, #fb7185); }

/* ---- cards ---- */
[class*="st-key-card"], .card, [data-testid="stForm"], [data-testid="stExpander"] details {
  background: var(--card); border: 1px solid var(--line) !important; border-radius: 18px;
  box-shadow: var(--shadow-sm);
}
[class*="st-key-card"] { padding: 1rem 1.15rem; }
.card { padding: 1.05rem 1.25rem; margin-bottom: 1rem; }
[data-testid="stForm"] { padding: 1.25rem 1.3rem; }
.card h3 { margin: 0 0 .35rem 0; font-size: 1.1rem; font-weight: 800; }

/* ---- KPI metrics ---- */
[data-testid="stMetric"] {
  position: relative; overflow: hidden; background: var(--card); border: 1px solid var(--line);
  border-radius: 18px; padding: 1rem 1.1rem .9rem; box-shadow: var(--shadow-sm);
  transition: transform .18s ease, box-shadow .18s ease;
}
[data-testid="stMetric"]::before { content: ""; position: absolute; inset: 0 0 auto 0; height: 4px;
                                   background: var(--brand-grad); }
[data-testid="stMetric"]:hover { transform: translateY(-2px); box-shadow: var(--shadow-md); }
[data-testid="stMetricLabel"] p { text-transform: uppercase; letter-spacing: .06em; font-size: .72rem !important;
                                  font-weight: 700; color: var(--muted); }
[data-testid="stMetricValue"] { font-weight: 800; letter-spacing: -.02em; }

/* ---- buttons ---- */
[data-testid^="stBaseButton-primary"] {
  background: var(--brand-grad) !important; border: none !important; color: #fff !important;
  font-weight: 700 !important; box-shadow: var(--shadow-brand); transition: transform .15s ease, filter .15s ease;
}
[data-testid^="stBaseButton-primary"]:hover { transform: translateY(-1px); filter: brightness(1.06); }
[data-testid^="stBaseButton-primary"]:active { transform: translateY(0); }
[data-testid^="stBaseButton-primary"]:disabled { opacity: .45; box-shadow: none; }
[data-testid^="stBaseButton-secondary"] { font-weight: 600; }

/* ---- inputs ---- */
[data-testid="stTextInputRootElement"]:focus-within { box-shadow: 0 0 0 4px rgba(42, 120, 214, .15); }

/* ---- tabs ---- */
[data-testid="stTabs"] [role="tablist"] { gap: .35rem; }
[data-testid="stTab"] { border-radius: 999px; padding: .35rem .9rem; }
[data-testid="stTab"][aria-selected="true"] { background: var(--info-bg); }

/* ---- sidebar ---- */
[data-testid="stSidebar"] { background: linear-gradient(180deg, #0f172a 0%, #111c36 100%); }
[data-testid="stSidebarNav"] a { border-radius: 10px; margin: 1px 0; }
[data-testid="stSidebarNav"] a:hover { background: rgba(148, 163, 184, .12); }
[data-testid="stNavSectionHeader"] { letter-spacing: .08em; text-transform: uppercase; font-size: .7rem !important;
                                     color: #64748b !important; }
.side-user { display: flex; align-items: center; gap: .6rem; padding: .7rem .8rem; border-radius: 14px;
             background: rgba(148, 163, 184, .10); margin-bottom: .6rem; }
.side-user .av { width: 34px; height: 34px; border-radius: 50%; background: var(--brand-grad); display: grid;
                 place-items: center; color: #fff; font-weight: 800; font-size: .85rem; }
.side-user b { color: #f1f5f9; font-size: .9rem; } .side-user small { color: #94a3b8; display: block; font-size: .72rem; }

/* ---- tables / charts ---- */
[data-testid="stDataFrame"] { border-radius: 14px; overflow: hidden; background: var(--card);
                              border: 1px solid var(--line); box-shadow: var(--shadow-sm); }
[class*="st-key-card"] [data-testid="stDataFrame"] { box-shadow: none; }
[data-testid="stPlotlyChart"] { border-radius: 14px; }

/* ---- badges ---- */
.badge { display: inline-flex; align-items: center; gap: .35rem; padding: .18rem .65rem; border-radius: 999px;
         font-size: .75rem; font-weight: 700; line-height: 1.5; }
.badge::before { content: ""; width: 6px; height: 6px; border-radius: 50%; background: currentColor; opacity: .85; }
.badge-good  { background: var(--good-bg); color: var(--good); }
.badge-bad   { background: var(--bad-bg);  color: var(--bad); }
.badge-warn  { background: var(--warn-bg); color: var(--warn); }
.badge-info  { background: var(--info-bg); color: var(--info); }
.badge-muted { background: #f1f5f9; color: var(--muted); }
.badge-live::before { animation: pulse 1.6s infinite; }

/* ---- meta grid ---- */
.meta { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: .75rem 1.2rem; margin-top: .75rem; }
.meta .k { font-size: .7rem; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); font-weight: 700; }
.meta .v { font-weight: 700; overflow-wrap: anywhere; color: var(--ink); margin-top: .1rem; }

/* ---- student profile ---- */
.profile { display: flex; align-items: center; gap: .9rem; }
.avatar { width: 56px; height: 56px; flex: 0 0 56px; border-radius: 18px; background: var(--brand-grad); color: #fff;
          display: grid; place-items: center; font-weight: 800; font-size: 1.15rem; box-shadow: var(--shadow-brand); }
.profile .name { font-size: 1.12rem; font-weight: 800; color: var(--ink); line-height: 1.25; }
.profile .nim { font-family: ui-monospace, "SFMono-Regular", Consolas, monospace; color: var(--muted); font-size: .85rem; }

/* ---- result cards ---- */
.result { display: flex; gap: 1rem; align-items: center; padding: 1.1rem 1.25rem; border-radius: 20px;
          background: var(--card); border: 1px solid var(--line); box-shadow: var(--shadow-md); margin: .25rem 0 1rem;
          animation: rise .45s cubic-bezier(.2, .8, .2, 1) both; }
.result .title { font-size: 1.35rem; font-weight: 800; letter-spacing: -.01em; line-height: 1.2; }
.result .text { color: var(--muted); font-size: .92rem; margin-top: .15rem; }
.result.ok { border-color: #bfe8cf; background: linear-gradient(180deg, #f3fcf6 0%, #ffffff 100%); }
.result.ok .title { color: var(--good); }
.result.bad { border-color: #f5c6cb; background: linear-gradient(180deg, #fff5f6 0%, #ffffff 100%);
              animation: rise .35s ease both, shake .45s .35s ease both; }
.result.bad .title { color: var(--bad); }
.result.warn { border-color: #fbd3b9; background: linear-gradient(180deg, #fff8f3 0%, #ffffff 100%); }
.result.warn .title { color: var(--warn); }
.result svg { flex: 0 0 56px; }
.check-circle { stroke-dasharray: 166; stroke-dashoffset: 166; animation: draw .6s .1s ease forwards; }
.check-mark { stroke-dasharray: 48; stroke-dashoffset: 48; animation: draw .35s .6s ease forwards; }

@keyframes draw { to { stroke-dashoffset: 0; } }
@keyframes rise { from { opacity: 0; transform: translateY(10px) scale(.98); } to { opacity: 1; transform: none; } }
@keyframes shake { 20%, 60% { transform: translateX(-6px); } 40%, 80% { transform: translateX(6px); } }
@keyframes pulse { 0% { box-shadow: 0 0 0 0 currentColor; } 70% { box-shadow: 0 0 0 6px transparent; } 100% { box-shadow: 0 0 0 0 transparent; } }
@keyframes float { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-8px); } }

.footer { text-align: center; color: #94a3b8; font-size: .78rem; margin-top: 1.6rem; }
</style>
"""

# Extra styles only for the student (phone) pages.
_STUDENT_CSS = """
<style>
[data-testid="stMainBlockContainer"] { max-width: 560px; padding-top: 1.6rem; }
/* campus photo behind the student page, darkened so cards and text stay readable */
[data-testid="stAppViewContainer"] {
  background:
    linear-gradient(180deg, rgba(15, 23, 42, .55) 0%, rgba(15, 23, 42, .78) 55%, rgba(15, 23, 42, .92) 100%),
    url("/app/static/campus.jpg") center / cover no-repeat fixed;
}
.brand-mini { flex-direction: column; color: #f8fafc !important; font-size: 1rem !important; gap: .55rem !important;
              text-shadow: 0 2px 10px rgba(0, 0, 0, .45); }
.brand-mini img { width: 64px; height: auto; filter: drop-shadow(0 6px 14px rgba(0, 0, 0, .45)); }
.brand-mini small { display: block; font-weight: 600; font-size: .75rem; color: #cbd5e1; letter-spacing: .08em;
                    text-transform: uppercase; }
.footer { color: #cbd5e1 !important; }
.empty h2, .empty p { color: #f8fafc !important; }
.hero { position: relative; overflow: hidden; color: #fff; border-radius: 26px; padding: 1.35rem 1.35rem 1.2rem;
        background: var(--brand-grad); box-shadow: var(--shadow-brand); margin-bottom: 1rem;
        animation: rise .5s cubic-bezier(.2, .8, .2, 1) both; }
.hero::before, .hero::after { content: ""; position: absolute; border-radius: 50%; background: rgba(255, 255, 255, .12); }
.hero::before { width: 220px; height: 220px; right: -70px; top: -90px; animation: float 7s ease-in-out infinite; }
.hero::after  { width: 140px; height: 140px; right: 60px; bottom: -80px; animation: float 9s ease-in-out infinite; }
.hero > * { position: relative; z-index: 1; }
.hero .eyebrow { font-size: .72rem; letter-spacing: .14em; text-transform: uppercase; opacity: .85; font-weight: 700; }
.hero h2 { color: #fff; font-size: 1.45rem; font-weight: 800; letter-spacing: -.02em; margin: .35rem 0 .15rem; padding: 0; line-height: 1.25; }
.hero .who { opacity: .9; font-size: .92rem; }
.chips { display: flex; flex-wrap: wrap; gap: .45rem; margin-top: .9rem; }
.chip { background: rgba(255, 255, 255, .16); border: 1px solid rgba(255, 255, 255, .22); backdrop-filter: blur(6px);
        border-radius: 999px; padding: .28rem .7rem; font-size: .8rem; font-weight: 600; }
.hero .status { position: absolute; top: 1.1rem; right: 1.1rem; }
.hero .badge { background: rgba(255, 255, 255, .95); }
[data-testid="stForm"] { border-radius: 22px; box-shadow: var(--shadow-md); }
[data-testid="stTextInput"] input { font-size: 1.1rem; font-weight: 600; letter-spacing: .02em; padding-top: .7rem; padding-bottom: .7rem; }
[data-testid^="stBaseButton-primaryFormSubmit"] { min-height: 3rem; font-size: 1rem !important; }
.brand-mini { display: flex; align-items: center; justify-content: center; gap: .5rem; margin-bottom: 1rem;
              color: var(--muted); font-weight: 700; font-size: .85rem; letter-spacing: .02em; }
.brand-mini .dot { width: 26px; height: 26px; border-radius: 9px; background: var(--brand-grad); display: grid;
                   place-items: center; font-size: .85rem; }
.empty { text-align: center; padding: 2.2rem 1rem 1rem; }
.empty .big { font-size: 3rem; animation: float 4s ease-in-out infinite; }
.empty h2 { font-weight: 800; letter-spacing: -.02em; margin: .4rem 0 .2rem; }
.empty p { color: var(--muted); }
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS + ADMIN_CSS + STATIC_CSS, unsafe_allow_html=True)


def inject_student_css() -> None:
    st.markdown(_CSS + _STUDENT_CSS + STATIC_CSS, unsafe_allow_html=True)


# ------------------------------------------------------------------------------------------------
# Headers & layout pieces
# ------------------------------------------------------------------------------------------------

def page_header(title: str, subtitle: str = "", icon: str = "") -> None:
    """Plain page title with a grey subtitle (``icon`` is kept for old callers and ignored)."""
    st.markdown(
        f"""<div class="app-head"><h1>{html.escape(title)}</h1>
            {f'<div class="sub">{html.escape(subtitle)}</div>' if subtitle else ''}</div>""",
        unsafe_allow_html=True,
    )


def section_title(title: str, hint: str = "") -> None:
    st.markdown(
        f'<div class="section-title"><h3>{html.escape(title)}</h3>'
        f'{f"<span>{html.escape(hint)}</span>" if hint else ""}</div>',
        unsafe_allow_html=True,
    )


def card_title(title: str) -> None:
    st.markdown(f'<div class="card-title">{html.escape(title)}</div>', unsafe_allow_html=True)


def badge(text: str, kind: str = "badge-info") -> str:
    return f'<span class="badge {kind}">{html.escape(text)}</span>'


def state_badge(state: str) -> str:
    label, kind = STATE_BADGES.get(state, (state.title(), "badge-muted"))
    return badge(label, kind + (" badge-live" if state == "open" else ""))


def meta_grid(items: dict[str, str]) -> str:
    cells = "".join(
        f'<div><div class="k">{html.escape(k)}</div><div class="v">{html.escape(str(v) or "-")}</div></div>'
        for k, v in items.items()
    )
    return f'<div class="meta">{cells}</div>'


def card(inner_html: str, extra_class: str = "") -> None:
    st.markdown(f'<div class="card {extra_class}">{inner_html}</div>', unsafe_allow_html=True)


def initials(name: str) -> str:
    parts = [p for p in str(name).split() if p[:1].isalpha()]
    return ((parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")) if parts else "?").upper()


def student_card(student: dict, record: dict | None = None, extra_class: str = "") -> None:
    items = {
        "Fakuldade": student["faculty"],
        "Departamentu": student["department"],
        "Turno": student["cohort"],
        "Sexu": {"Male": "Mane", "Female": "Feto"}.get(student["gender"], student["gender"]),
    }
    if record:
        items["Oras check-in"] = str(record["checked_in_at"])[11:19]
        items["Status"] = theme_status(record["status"])
    card(
        f'<div class="profile"><div class="avatar">{html.escape(initials(student["name"]))}</div>'
        f'<div><div class="name">{html.escape(student["name"])}</div>'
        f'<div class="nim">NIM {html.escape(student["nim"])}</div></div></div>{meta_grid(items)}',
        extra_class,
    )


# ------------------------------------------------------------------------------------------------
# Student result cards (animated)
# ------------------------------------------------------------------------------------------------
_ICON_OK = """<svg width="56" height="56" viewBox="0 0 56 56" aria-hidden="true">
  <circle class="check-circle" cx="28" cy="28" r="26" fill="none" stroke="#16a34a" stroke-width="3"/>
  <path class="check-mark" d="M17 29 l7 7 l15 -16" fill="none" stroke="#16a34a" stroke-width="4"
        stroke-linecap="round" stroke-linejoin="round"/></svg>"""
_ICON_BAD = """<svg width="56" height="56" viewBox="0 0 56 56" aria-hidden="true">
  <circle cx="28" cy="28" r="26" fill="#fdecee" stroke="#e11d48" stroke-width="3"/>
  <path d="M20 20 L36 36 M36 20 L20 36" stroke="#e11d48" stroke-width="4" stroke-linecap="round"/></svg>"""
_ICON_WARN = """<svg width="56" height="56" viewBox="0 0 56 56" aria-hidden="true">
  <circle cx="28" cy="28" r="26" fill="#fff1e8" stroke="#ea580c" stroke-width="3"/>
  <path d="M28 16 V31" stroke="#ea580c" stroke-width="4" stroke-linecap="round"/>
  <circle cx="28" cy="39" r="2.6" fill="#ea580c"/></svg>"""


def result_card(kind: str, title: str, text_html: str) -> None:
    """kind: ok | bad | warn"""
    icon = {"ok": _ICON_OK, "bad": _ICON_BAD, "warn": _ICON_WARN}[kind]
    st.markdown(
        f'<div class="result {kind}">{icon}<div><div class="title">{html.escape(title)}</div>'
        f'<div class="text">{text_html}</div></div></div>',
        unsafe_allow_html=True,
    )


# ------------------------------------------------------------------------------------------------
# Small JavaScript widgets
# ------------------------------------------------------------------------------------------------

def live_clock(seconds_to_late: int | None, seconds_to_close: int | None) -> None:
    """Ticking clock with 'on time until' / 'closes in' countdowns (runs in the browser)."""
    data = json.dumps({"late": seconds_to_late, "close": seconds_to_close})
    # An iframe (not st.html) so each rerun replaces the widget and its timer.
    st.iframe(
        f"""
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@600;700;800&display=swap" rel="stylesheet">
<style>
  body {{ margin: 0; font-family: {FONT}; }}
  .bar {{ display: flex; align-items: center; justify-content: space-between; gap: .6rem; padding: .55rem .9rem;
          background: #fff; border: 1px solid #e2e8f0; border-radius: 16px; box-shadow: 0 1px 3px rgba(15,23,42,.06); }}
  .clock {{ font-weight: 800; font-size: 1.15rem; color: #0f172a; font-variant-numeric: tabular-nums; }}
  .clock small {{ display: block; font-size: .66rem; color: #64748b; letter-spacing: .08em; text-transform: uppercase; }}
  .cd {{ text-align: right; font-size: .78rem; color: #64748b; font-weight: 600; }}
  .cd b {{ color: #0f172a; font-variant-numeric: tabular-nums; }}
  .cd .late b {{ color: #c2541c; }}
</style>
<div class="bar"><div class="clock"><small>Now</small><span id="t">--:--:--</span></div><div class="cd" id="cd"></div></div>
<script>
  const d = {data}; const start = Date.now();
  const pad = n => String(n).padStart(2, "0");
  // durations read as "9m 05s" / "1h 34m" so they are never mistaken for a clock time
  const fmt = s => s >= 3600 ? Math.floor(s/3600) + "h " + pad(Math.floor(s%3600/60)) + "m"
                             : Math.floor(s/60) + "m " + pad(s%60) + "s";
  function tick() {{
    const now = new Date(); const el = (Date.now() - start) / 1000;
    document.getElementById("t").textContent = pad(now.getHours()) + ":" + pad(now.getMinutes()) + ":" + pad(now.getSeconds());
    const parts = [];
    if (d.late !== null) {{ const s = Math.round(d.late - el);
      parts.push(s > 0 ? "Tuir oras to'o <b>" + fmt(s) + "</b>" : "<span class='late'><b>Atrazu</b> check-in agora</span>"); }}
    if (d.close !== null) {{ const s = Math.round(d.close - el);
      parts.push(s > 0 ? "Taka iha <b>" + fmt(s) + "</b>" : "<b>Taka ona</b>"); }}
    document.getElementById("cd").innerHTML = parts.join("<br>");
  }}
  tick(); setInterval(tick, 1000);
</script>""",
        height=66,
    )


def celebrate() -> None:
    """Confetti burst + short vibration on phones (canvas-confetti, loaded on demand)."""
    browser.run_js(
        """
  const fire = () => {
    const colors = ["#2a78d6", "#6d5dfc", "#1baf7a", "#eda100", "#e87ba4"];
    window.confetti({ particleCount: 110, spread: 75, startVelocity: 38, origin: { y: 0.35 }, colors, zIndex: 9999 });
    setTimeout(() => window.confetti({ particleCount: 60, spread: 110, origin: { y: 0.3 }, colors, zIndex: 9999 }), 250);
  };
  try { if (navigator.vibrate) navigator.vibrate([40, 30, 60]); } catch (e) {}
  if (window.confetti) { fire(); }
  else {
    const s = document.createElement("script");
    s.src = "https://cdn.jsdelivr.net/npm/canvas-confetti@1.9.3/dist/confetti.browser.min.js";
    s.onload = fire; document.head.appendChild(s);
  }"""
    )


# ------------------------------------------------------------------------------------------------
# Misc
# ------------------------------------------------------------------------------------------------

def qr_png(data: str) -> bytes:
    img = qrcode.make(data, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def style_fig(fig: go.Figure, height: int = 320, percent_x: bool = False, percent_y: bool = False) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title=None),
        bargap=0.35,
        hoverlabel=dict(namelength=-1, font_family=FONT, bgcolor="#0f172a", font_color="#f8fafc", bordercolor="#0f172a"),
        font=dict(family=FONT, color="#475569"),
    )
    grid = "rgba(148,163,184,0.25)"
    fig.update_xaxes(showgrid=False, linecolor=grid, title=None)
    fig.update_yaxes(gridcolor=grid, zeroline=False, title=None)
    if percent_x:
        fig.update_xaxes(tickformat=".0%", range=[0, 1.05], showgrid=True, gridcolor=grid)
    if percent_y:
        fig.update_yaxes(tickformat=".0%", range=[0, 1.05])
    fig.update_traces(marker_line_width=0, selector=dict(type="bar"))
    fig.update_traces(marker_cornerradius=3, selector=dict(type="bar"))
    return fig


def integer_axis(fig: go.Figure, axis: str, max_value: float) -> go.Figure:
    """Whole-number ticks for count axes (no '0, 0, 1, 1' when counts are small)."""
    opts = dict(rangemode="tozero", tickformat=",d")
    if max_value <= 10:
        opts.update(tick0=0, dtick=1)
    (fig.update_yaxes if axis == "y" else fig.update_xaxes)(**opts)
    return fig


def date_range_picker(key: str, default: str = "Today") -> tuple[date, date, str]:
    """Preset range selector (Today / 7 / 30 days / custom)."""
    today = now_local().date()
    presets = ["Today", "Last 7 days", "Last 30 days", "Custom"]
    col_a, col_b = st.columns([1, 2])
    choice = col_a.selectbox("Period", presets, index=presets.index(default), key=f"{key}_preset")
    if choice == "Today":
        return today, today, choice
    if choice == "Last 7 days":
        return today - timedelta(days=6), today, choice
    if choice == "Last 30 days":
        return today - timedelta(days=29), today, choice
    picked = col_b.date_input("Custom range", (today - timedelta(days=6), today), key=f"{key}_custom")
    if isinstance(picked, tuple) and len(picked) == 2:
        return picked[0], picked[1], choice
    return today, today, choice


def app_footer() -> None:
    st.markdown(
        f'<div class="footer">{html.escape(settings_service.get("system_name"))} · {now_local():%d %b %Y %H:%M} '
        f"(UTC+{settings.utc_offset_hours})</div>",
        unsafe_allow_html=True,
    )
