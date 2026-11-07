"""Admin look & feel: navy sidebar, pastel KPI cards, white panels, status pills and charts.

Everything here is presentation only. Pages pass in data and get HTML back.
"""
from __future__ import annotations

import html
import zlib

import plotly.graph_objects as go

GREEN = "#16a34a"
RED = "#ef4444"
AMBER = "#f5a524"
BLUE = "#1d63ed"
STATUS_COLOR = {"Present": GREEN, "Absent": RED, "Late": AMBER}
STATUS_TEXT = {"Present": "Prezente", "Absent": "Falta", "Late": "Atrazu", "Active": "Ativu"}  # display only; the stored value stays English


def status_text(status: str) -> str:
    return STATUS_TEXT.get(status, status)

ADMIN_CSS = """
<style>
:root {
  --brand-1: #1d63ed; --brand-2: #3b82f6;
  --brand-grad: linear-gradient(135deg, #1d63ed 0%, #3b82f6 100%);
  --ink: #0f1f3d; --muted: #64748b; --line: #e3e9f4; --navy: #0a1f4d;
  --shadow-sm: 0 1px 2px rgba(10, 31, 77, .05), 0 2px 8px rgba(10, 31, 77, .04);
  --shadow-md: 0 10px 28px -14px rgba(10, 31, 77, .25);
  --shadow-brand: none;
}

/* ---- canvas ---- */
[data-testid="stAppViewContainer"] { background: #f4f7fc; }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stMainBlockContainer"] { max-width: 1400px; padding-top: 1.1rem; padding-bottom: 2.5rem; }

/* ---- sidebar ---- */
[data-testid="stSidebar"] { background: var(--navy); border-right: none; }
[data-testid="stSidebarContent"] { display: flex; flex-direction: column; }
[data-testid="stSidebarUserContent"] { margin-top: auto; }
[data-testid="stSidebarNav"] { padding-top: .4rem; }
[data-testid="stSidebarNav"] a, [data-testid="stSidebarNavLink"] {
  border-radius: 8px; margin: 3px 0; padding-top: .5rem; padding-bottom: .5rem; color: #dbe6fb;
}
[data-testid="stSidebarNav"] a:hover, [data-testid="stSidebarNavLink"]:hover { background: rgba(255, 255, 255, .08); }
[data-testid="stSidebarNav"] a[aria-current="page"], [data-testid="stSidebarNavLink"][aria-current="page"] {
  background: #1d63ed; color: #fff; font-weight: 700;
}
[data-testid="stSidebarNav"] a[aria-current="page"] *, [data-testid="stSidebarNavLink"][aria-current="page"] * { color: #fff !important; }
.side-status { padding: .8rem .4rem .4rem; font-size: .76rem; color: #b6c6e8; line-height: 1.5; }
.side-status .on { display: flex; align-items: center; gap: .45rem; color: #e8f0ff; font-weight: 600; }
.side-status .on::before { content: ""; width: 8px; height: 8px; border-radius: 50%; background: #22c55e; }
.side-status .off::before { background: #ef4444; }
.side-status small { color: #8da2cf; font-size: .7rem; }

/* ---- top bar ---- */
[class*="st-key-topbar"] { background: #fff; border: 1px solid var(--line); border-radius: 12px; padding: .45rem .8rem;
                           box-shadow: var(--shadow-sm); margin-bottom: 1.1rem; }
[class*="st-key-topbar"] [data-testid="stTextInputRootElement"] { background: #f1f6fe; border-color: #dce8fb; }
[class*="st-key-topbar"] [data-testid="stTextInput"] input { font-size: .85rem; }
[class*="st-key-topbar"] button { border: none !important; background: transparent !important; box-shadow: none !important; }
[class*="st-key-bell"] button { position: relative; }
.bell-badge { display: inline-grid; place-items: center; min-width: 17px; height: 17px; padding: 0 4px; border-radius: 99px;
              background: #ef4444; color: #fff; font-size: .66rem; font-weight: 800; margin-left: .3rem; }

/* ---- page header ---- */
.app-head { margin-bottom: 1rem; }
.app-head h1 { font-size: 1.55rem; font-weight: 800; letter-spacing: -.02em; color: var(--ink); }
.app-head .sub { color: var(--muted); font-size: .88rem; margin-top: .1rem; }

/* ---- pastel KPI cards ---- */
.pc-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 1rem; margin: 0 0 1.1rem; }
@media (max-width: 1320px) { .pc-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 640px)  { .pc-grid { grid-template-columns: minmax(0, 1fr); } }
.pc { display: flex; gap: .9rem; align-items: flex-start; padding: 1rem 1.1rem; border-radius: 12px;
      background: var(--bg); border: 1px solid var(--bd); box-shadow: var(--shadow-sm); }
.pc .ico { flex: 0 0 44px; width: 44px; height: 44px; border-radius: 50%; background: var(--fg); display: grid; place-items: center; }
.pc .ico svg { width: 23px; height: 23px; fill: #fff; }
.pc .lbl { font-size: .8rem; font-weight: 700; color: var(--fg); }
.pc .val { font-size: 2.05rem; font-weight: 800; letter-spacing: -.03em; color: var(--ink); line-height: 1.12; }
.pc .sub { font-size: .74rem; color: var(--muted); font-weight: 600; margin-top: .1rem; }
.pc > div:last-child { min-width: 0; flex: 1; }
.pc .lbl { white-space: nowrap; }
.pc .pair { display: flex; gap: 1rem; align-items: flex-start; }
.pc .pair > div { min-width: 0; }
.pc .pair .lbl { white-space: normal; }
.pc .pair .val { font-size: 1.55rem; }
.pc .pair .sub { font-size: .7rem; }
.pc.blue  { --bg: #eaf2ff; --bd: #cfe0fb; --fg: #1d63ed; }
.pc.green { --bg: #e7f7ed; --bd: #c4ebd2; --fg: #16a34a; }
.pc.red   { --bg: #fdeded; --bd: #f8cdcd; --fg: #ef4444; }
.pc.amber { --bg: linear-gradient(120deg, #fff5dc 0%, #fdeef0 100%); --bd: #f5e1ad; --fg: #f5a524; }
.pc.violet { --bg: #f1edff; --bd: #dcd2fb; --fg: #7c3aed; }

/* ---- panels (white cards) ---- */
[class*="st-key-card"], [data-testid="stForm"], [data-testid="stExpander"] details {
  border-radius: 12px; box-shadow: var(--shadow-sm);
}
.card-title { font-size: .98rem; margin-bottom: .1rem; }
.card-title::before { display: none; }
.card-sub { color: var(--muted); font-size: .76rem; margin: 0 0 .5rem; }
[data-testid="stMetric"] { border-radius: 12px; box-shadow: var(--shadow-sm); }
[data-testid="stMetric"]::before { display: none; }
[data-testid="stMetric"]:hover { transform: none; box-shadow: var(--shadow-sm); }

/* ---- buttons / inputs ---- */
[data-testid^="stBaseButton-primary"] { background: #1d63ed !important; box-shadow: none; border-radius: 8px; }
[data-testid^="stBaseButton-primary"]:hover { transform: none; filter: brightness(1.08); }
[data-testid^="stBaseButton-secondary"] { border-radius: 8px; }
[data-testid="stSelectbox"] [data-baseweb="select"] > div, [data-testid="stDateInput"] > div > div,
[data-testid="stTextInputRootElement"], [data-testid="stMultiSelect"] [data-baseweb="select"] > div { border-radius: 8px; }
[data-testid="stTab"] { border-radius: 8px; }
[data-testid="stTab"][aria-selected="true"] { background: #e8f0ff; }

/* ---- tables ---- */
.dt-wrap { overflow-x: auto; }
table.dt { width: 100%; border-collapse: collapse; font-size: .8rem; color: var(--ink); }
table.dt th { text-align: left; font-size: .7rem; font-weight: 700; color: #64748b; background: #f5f8fd; padding: .55rem .7rem;
              border-bottom: 1px solid var(--line); white-space: nowrap; }
table.dt td { padding: .55rem .7rem; border-bottom: 1px solid #eef2f9; vertical-align: middle; }
table.dt tr:last-child td { border-bottom: none; }
table.dt .mono { font-family: ui-monospace, Consolas, monospace; font-size: .76rem; color: #475569; }
table.dt .num { text-align: right; font-variant-numeric: tabular-nums; }
.who { display: flex; align-items: center; gap: .55rem; font-weight: 600; }
.av-sm { width: 30px; height: 30px; flex: 0 0 30px; border-radius: 50%; display: grid; place-items: center; color: #fff;
         font-size: .68rem; font-weight: 800; }
.st-pill { display: inline-block; padding: .14rem .6rem; border-radius: 6px; font-size: .7rem; font-weight: 700; }
.st-pill.present, .st-pill.active { background: #dcf5e5; color: #15803d; }
.st-pill.late { background: #fff0cc; color: #b45309; }
.st-pill.absent { background: #fde3e3; color: #b91c1c; }
.st-pill.muted { background: #eef2f8; color: #64748b; }
.rate { display: flex; align-items: center; gap: .55rem; min-width: 120px; }
.rate .bar { flex: 1; height: 6px; border-radius: 99px; background: #e8eef8; overflow: hidden; }
.rate .bar span { display: block; height: 100%; border-radius: 99px; background: #16a34a; }
.rate.mid .bar span { background: #f5a524; }
.rate.low .bar span { background: #ef4444; }
.rate b { font-size: .76rem; min-width: 42px; text-align: right; font-variant-numeric: tabular-nums; }

/* ---- legend next to donut ---- */
.legend { display: grid; gap: .55rem; padding-top: .6rem; font-size: .8rem; }
.legend .row { display: grid; grid-template-columns: 12px 1fr auto auto; gap: .55rem; align-items: center; }
.legend .dot { width: 10px; height: 10px; border-radius: 50%; }
.legend .n { font-weight: 700; } .legend .p { color: var(--muted); min-width: 44px; text-align: right; }
.legend .total { border-top: 1px solid var(--line); padding-top: .5rem; color: var(--muted); display: flex; justify-content: space-between; }

/* ---- settings menu (radio rendered as a vertical list) ---- */
[class*="settings-menu"] [role="radiogroup"] { gap: .25rem; }
[class*="settings-menu"] label { padding: .55rem .8rem; border-radius: 8px; width: 100%; cursor: pointer; }
[class*="settings-menu"] label:has(input:checked) { background: #1d63ed; }
[class*="settings-menu"] label:has(input:checked) * { color: #fff !important; }
[class*="settings-menu"] label > div:first-child { display: none; }
/* ---- static, uniform look: no animation, no hover movement, one font ---- */
*, *::before, *::after { animation: none !important; transition: none !important; }
.kpi:hover, [data-testid="stMetric"]:hover, [data-testid^="stBaseButton-primary"]:hover { transform: none !important; }
html, body, .stApp, button, input, select, textarea { font-family: "Plus Jakarta Sans", system-ui, "Segoe UI", sans-serif; }

/* ---- navy top bar (system name + account) ---- */
[class*="st-key-topbar"] { background: var(--navy); border: none; border-radius: 12px; padding: .5rem 1rem; margin-bottom: 1.1rem; }
[class*="st-key-topbar"] .tb-title { display: flex; align-items: center; gap: .7rem; color: #fff; font-weight: 800; font-size: 1.02rem; }
[class*="st-key-topbar"] .tb-title img { width: 34px; height: 34px; padding: 5px; border-radius: 9px; background: #1d63ed; }
[class*="st-key-topbar"] button, [class*="st-key-topbar"] button * { color: #fff !important; }
[class*="st-key-topbar"] button:hover { background: rgba(255, 255, 255, .1) !important; }

[class*="st-key-topbar"] .tb-user { display: flex; align-items: center; justify-content: flex-end; gap: .55rem; color: #fff; font-weight: 700; font-size: .88rem; }
[class*="st-key-topbar"] .tb-av { width: 30px; height: 30px; border-radius: 50%; background: #1d63ed; display: grid; place-items: center; font-size: .8rem; }

/* ---- header row with date pill ---- */
.date-pill { display: flex; align-items: center; justify-content: space-between; gap: .6rem; background: #fff; border: 1px solid var(--line);
             border-radius: 8px; padding: .5rem .8rem; font-size: .8rem; color: var(--ink); font-weight: 600; box-shadow: var(--shadow-sm); }
.date-pill svg { width: 16px; height: 16px; fill: #1d63ed; }

/* ---- Good / Medium / Low pills and coloured rate text ---- */
.st-pill.good { background: #dcf5e5; color: #15803d; }
.st-pill.medium { background: #fff0cc; color: #b45309; }
.st-pill.low { background: #fde3e3; color: #b91c1c; }
.rate-txt { font-weight: 700; font-variant-numeric: tabular-nums; }
.rate-txt.good { color: #16a34a; } .rate-txt.medium { color: #f59e0b; } .rate-txt.low { color: #ef4444; }
table.dt .act { color: #1d63ed; letter-spacing: .5rem; font-size: .9rem; white-space: nowrap; }
table.dt td.c, table.dt th.c { text-align: center; }
.empty-row { text-align: center; color: var(--muted); font-size: .85rem; padding: 1.6rem 0 1.2rem; }

/* ---- attendance by class: coloured progress rows ---- */
.cbars { display: grid; gap: .85rem; padding: .3rem 0 .2rem; }
.cbars .row { display: grid; grid-template-columns: 62px 1fr 44px; gap: .7rem; align-items: center; font-size: .8rem; font-weight: 600; }
.cbars .track { height: 11px; border-radius: 99px; background: #e8eef8; overflow: hidden; }
.cbars .track span { display: block; height: 100%; border-radius: 99px; }
.cbars .pct { text-align: right; font-weight: 700; font-variant-numeric: tabular-nums; }

/* ---- small white KPI tiles (Analytics) ---- */
.mini-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: .8rem; }
.mini { display: flex; align-items: center; gap: .7rem; padding: .85rem .9rem; border-radius: 12px; background: #fff;
        border: 1px solid var(--line); box-shadow: var(--shadow-sm); }
.mini .ico { width: 38px; height: 38px; flex: 0 0 38px; border-radius: 10px; display: grid; place-items: center; background: var(--bg); }
.mini .ico svg { width: 20px; height: 20px; fill: var(--fg); }
.mini .lbl { font-size: .72rem; font-weight: 700; color: var(--fg); }
.mini .val { font-size: 1.45rem; font-weight: 800; color: var(--ink); line-height: 1.1; }
.mini.blue { --bg: #eaf2ff; --fg: #1d63ed; } .mini.green { --bg: #e7f7ed; --fg: #16a34a; }
.mini.red { --bg: #fdeded; --fg: #ef4444; } .mini.amber { --bg: #fff3dc; --fg: #f5a524; }
@media (max-width: 900px) { .mini-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }

/* ---- report summary rows ---- */
.sum-rows .r { display: flex; align-items: center; gap: .7rem; padding: .62rem 0; border-bottom: 1px solid #eef2f9; font-size: .84rem; font-weight: 600; }
.sum-rows .r:last-child { border-bottom: none; }
.sum-rows .ico { width: 30px; height: 30px; border-radius: 8px; display: grid; place-items: center; background: var(--bg); }
.sum-rows .ico svg { width: 17px; height: 17px; fill: var(--fg); }
.sum-rows .v { margin-left: auto; font-weight: 800; font-size: .95rem; color: var(--fg); font-variant-numeric: tabular-nums; }
.sum-rows .blue { --bg: #eaf2ff; --fg: #1d63ed; } .sum-rows .green { --bg: #e7f7ed; --fg: #16a34a; }
.sum-rows .red { --bg: #fdeded; --fg: #ef4444; } .sum-rows .amber { --bg: #fff3dc; --fg: #f5a524; }
.sum-rows .teal { --bg: #e3f5f2; --fg: #0d9488; }

/* ---- pager ---- */
[class*="st-key-pager-"] button { min-height: 2rem; padding: 0 .2rem; border-radius: 8px; }
.pg-dots { text-align: center; color: var(--muted); line-height: 2rem; }

/* ---- info panels (Settings > General) ---- */
.kv { display: grid; grid-template-columns: 110px 1fr; gap: .45rem .8rem; font-size: .82rem; }
.kv .k { color: var(--muted); } .kv .v { color: var(--ink); font-weight: 600; word-break: break-all; }
.dot-ok { display: inline-flex; align-items: center; gap: .4rem; color: #15803d; font-weight: 700; font-size: .78rem; }
.dot-ok::before { content: ""; width: 8px; height: 8px; border-radius: 50%; background: #22c55e; }
.dot-ok.off { color: #b91c1c; } .dot-ok.off::before { background: #ef4444; }

/* ---- settings tabs ---- */
[data-testid="stTabs"] [role="tablist"] { border-bottom: 1px solid var(--line); }
[data-testid="stTab"] { border-radius: 0; padding: .5rem 1rem; }
[data-testid="stTab"][aria-selected="true"] { background: transparent; box-shadow: inset 0 -2px 0 #1d63ed; color: #1d63ed; font-weight: 700; }
</style>
"""

_ICONS = {
    "people": "M16 11a3 3 0 1 0-3-3 3 3 0 0 0 3 3zM8 11a3 3 0 1 0-3-3 3 3 0 0 0 3 3zm0 2c-2.3 0-7 1.2-7 3.5V19h14v-2.5C15 14.2 10.3 13 8 13zm8 0c-.3 0-.6 0-1 .1 1.2.8 2 1.9 2 3.4V19h6v-2.5c0-2.3-4.7-3.5-7-3.5z",
    "check": "M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm-2 15-5-5 1.4-1.4L10 14.2l7.6-7.6L19 8z",
    "cancel": "M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm5 13.6L15.6 17 12 13.4 8.4 17 7 15.6 10.6 12 7 8.4 8.4 7 12 10.6 15.6 7 17 8.4 13.4 12z",
    "clock": "M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm4.2 14.2L11 13V7h1.5v5.2l4.5 2.7z",
    "trend": "M3.5 18.5l6-6 4 4L22 7.9 20.6 6.5l-7.1 7.1-4-4L2 17z",
    "up": "M7 14l5-5 5 5z",
    "down": "M7 10l5 5 5-5z",
    "list": "M3 5h2v2H3zm4 0h14v2H7zM3 11h2v2H3zm4 0h14v2H7zM3 17h2v2H3zm4 0h14v2H7z",
    "calendar": "M19 4h-1V2h-2v2H8V2H6v2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2zm0 16H5V10h14zM5 8V6h14v2z",
}


def static_css() -> str:
    return STATIC_CSS


def icon(name: str) -> str:
    return f'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="{_ICONS[name]}"/></svg>'


def pastel_cards(items: list[dict]) -> str:
    """Row of pastel KPI cards. Item: tone, icon, label, value, sub, optional ``second`` = (label, value, sub)."""
    out = []
    for it in items:
        first = (
            f'<div><div class="lbl">{html.escape(it["label"])}</div>'
            f'<div class="val">{html.escape(str(it["value"]))}</div>'
            f'<div class="sub">{html.escape(it.get("sub", ""))}</div></div>'
        )
        body = first
        if it.get("second"):
            label, value, sub = it["second"]
            body = (
                f'<div class="pair">{first}<div><div class="lbl">{html.escape(label)}</div>'
                f'<div class="val">{html.escape(str(value))}</div><div class="sub">{html.escape(sub)}</div></div></div>'
            )
        out.append(
            f'<div class="pc {it["tone"]}"><div class="ico">{icon(it["icon"])}</div><div>{body}</div></div>'
        )
    return f'<div class="pc-grid">{"".join(out)}</div>'


def level(rate: float) -> str:
    """Good (80% and up), Medium (70-79%) or Low (below 70%), as in the Students table."""
    return "good" if rate >= 0.80 else "medium" if rate >= 0.70 else "low"


LEVEL_TEXT = {"good": "Diak", "medium": "Média", "low": "Ki'ik"}


def level_pill(rate: float) -> str:
    kind = level(rate)
    return f'<span class="st-pill {kind}">{LEVEL_TEXT[kind]}</span>'


def rate_text(rate: float) -> str:
    return f'<span class="rate-txt {level(rate)}">{rate:.0%}</span>'


def date_pill(text: str) -> str:
    return f'<div class="date-pill"><span>{html.escape(text)}</span>{icon("calendar")}</div>'


def mini_cards(items: list[dict]) -> str:
    """White KPI tiles. Item: tone, icon, label, value."""
    cells = "".join(
        f'<div class="mini {it["tone"]}"><div class="ico">{icon(it["icon"])}</div>'
        f'<div><div class="lbl">{html.escape(it["label"])}</div><div class="val">{html.escape(str(it["value"]))}</div></div></div>'
        for it in items
    )
    return f'<div class="mini-grid">{cells}</div>'


CLASS_BAR_COLORS = ["#1d63ed", "#16a34a", "#f5a524", "#7c3aed", "#0891b2", "#db2777"]


def class_bars(rows: list[tuple[str, float]]) -> str:
    """Horizontal progress rows: (class name, rate 0..1)."""
    out = []
    for i, (name, rate) in enumerate(rows):
        color = CLASS_BAR_COLORS[i % len(CLASS_BAR_COLORS)]
        width = max(0.0, min(1.0, rate)) * 100
        out.append(
            f'<div class="row"><span>{html.escape(str(name))}</span>'
            f'<div class="track"><span style="width:{width:.0f}%;background:{color}"></span></div>'
            f'<span class="pct">{rate:.0%}</span></div>'
        )
    return f'<div class="cbars">{"".join(out)}</div>'


def summary_rows(items: list[tuple[str, str, str, str]]) -> str:
    """Rows of (tone, icon, label, value) for the Reports summary card."""
    rows = "".join(
        f'<div class="r {tone}"><span class="ico">{icon(ic)}</span><span>{html.escape(label)}</span>'
        f'<span class="v">{html.escape(str(value))}</span></div>'
        for tone, ic, label, value in items
    )
    return f'<div class="sum-rows">{rows}</div>'


def avatar(name: str) -> str:
    parts = [p for p in str(name).split() if p[:1].isalpha()]
    text = ((parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")) if parts else "?").upper()
    hue = zlib.crc32(str(name).encode()) % 360
    return f'<span class="av-sm" style="background:hsl({hue} 55% 46%)">{html.escape(text)}</span>'


def person(name: str) -> str:
    return f'<div class="who">{avatar(name)}<span>{html.escape(str(name))}</span></div>'


def pill(status: str) -> str:
    kind = {"Present": "present", "Late": "late", "Absent": "absent", "Active": "active"}.get(status, "muted")
    return f'<span class="st-pill {kind}">{html.escape(status_text(status))}</span>'


def rate_bar(rate: float) -> str:
    tone = "" if rate >= 0.75 else "mid" if rate >= 0.5 else "low"
    width = max(0.0, min(1.0, rate)) * 100
    return f'<div class="rate {tone}"><div class="bar"><span style="width:{width:.0f}%"></span></div><b>{rate:.1%}</b></div>'


def table(headers: list[str], rows: list[list[str]], classes: list[str] | None = None) -> str:
    """HTML table. Cells are trusted HTML: escape user text with html.escape() before passing it in."""
    classes = classes or [""] * len(headers)
    head = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
    body = "".join(
        "<tr>" + "".join(f'<td class="{c}">{cell}</td>' for cell, c in zip(row, classes)) + "</tr>" for row in rows
    )
    return f'<div class="dt-wrap"><table class="dt"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def empty_table(headers: list[str], message: str) -> str:
    """Table header with one centred message row (nothing to list yet). ``message`` is trusted HTML."""
    head = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
    return (
        f'<div class="dt-wrap"><table class="dt"><thead><tr>{head}</tr></thead><tbody><tr>'
        f'<td colspan="{len(headers)}" class="empty-row">{message}</td></tr></tbody></table></div>'
    )


def esc(value: object) -> str:
    return html.escape(str(value))


def donut(present: int, late: int, absent: int, centre_text: str, height: int = 230, centre_sub: str = "Tama") -> go.Figure:
    values = [present, absent, late]
    fig = go.Figure(
        go.Pie(
            labels=[status_text("Present"), status_text("Absent"), status_text("Late")], values=values if sum(values) else [1],
            hole=0.74, sort=False, direction="clockwise", textinfo="none",
            marker=dict(colors=[GREEN, RED, AMBER] if sum(values) else ["#e5ebf5"], line=dict(color="#fff", width=2)),
            hovertemplate="%{label}: %{value} (%{percent})<extra></extra>" if sum(values) else "<extra></extra>",
        )
    )
    fig.update_layout(
        height=height, margin=dict(l=0, r=0, t=0, b=0), showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        annotations=[
            dict(text=f"<b>{centre_text}</b>", x=0.5, y=0.54, showarrow=False, font=dict(size=24, color="#0f1f3d")),
            dict(text=centre_sub, x=0.5, y=0.42, showarrow=False, font=dict(size=12, color="#64748b")),
        ],
    )
    return fig


def legend(present: int, late: int, absent: int, expected: int) -> str:
    def row(label: str, n: int, color: str) -> str:
        pct = f"{n / expected:.1%}" if expected else "0.0%"
        return (
            f'<div class="row"><span class="dot" style="background:{color}"></span><span>{label}</span>'
            f'<span class="n">{pct}</span></div>'
        )

    return '<div class="legend">' + row("Prezente", present, GREEN) + row("Falta", absent, RED) + row("Atrazu", late, AMBER) + "</div>"


# Plain, static look: one typeface everywhere, no animation, no movement on hover, flat white canvas.
STATIC_CSS = """
<style>
.stApp, .stApp *:not([data-testid="stIconMaterial"]):not([class*="material-symbols"]) {
  font-family: "Plus Jakarta Sans", system-ui, "Segoe UI", Arial, sans-serif !important;
}
*, *::before, *::after { animation: none !important; transition: none !important; }
*:hover { transform: none !important; }
[data-testid="stAppViewContainer"] { background: #f5f7fb !important; background-image: none !important; }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stDecoration"] { display: none; }
[data-testid^="stBaseButton-primary"] { background: #1d63ed !important; background-image: none !important; box-shadow: none !important; filter: none !important; }
[class*="st-key-card"], [data-testid="stForm"], [data-testid="stExpander"] details, [data-testid="stMetric"], .pc, .mini, .card { box-shadow: none !important; }
table.dt .mono, code, pre, .class-code b { font-family: inherit !important; }
</style>
"""
