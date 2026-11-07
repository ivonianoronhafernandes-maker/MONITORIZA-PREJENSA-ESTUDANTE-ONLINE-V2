"""Shapes the Spark snapshot into the small tables the Dashboard and Analytics pages draw.

Pure functions (no Streamlit): the numbers themselves are computed by Spark; this only
selects a period/class and derives Present / Late / Absent and per-class / per-day rows.
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

PERIODS = {"Today": "today", "Last 7 days": "last_7_days", "Last 30 days": "last_30_days"}


def select(snapshot: dict, period_label: str, class_key: str | None) -> tuple[dict, set[int], list[dict], tuple[str, str]]:
    """Return (view, session ids, proxy alerts, (start, end)) for the chosen period or single class."""
    if class_key and class_key in snapshot["classes"]:
        view = snapshot["classes"][class_key]
        alerts = [a for a in snapshot["alerts"] if str(a["session_id"]) == class_key]
        return view, {int(class_key)}, alerts, (view["session_date"], view["session_date"])
    view = snapshot["periods"][PERIODS[period_label]]
    sids = {c["session_id"] for c in view["classes"]}
    alerts = [a for a in snapshot["alerts"] if a["session_id"] in sids]
    return view, sids, alerts, (view["start"], view["end"])


def status_counts(kpis: dict) -> dict:
    """Present (on time) + Late + Absent always add up to the expected attendance."""
    attended, late, expected = kpis["checkins"], kpis["late"], kpis["expected"]
    return {
        "expected": expected,
        "attended": attended,
        "present": attended - late,
        "late": late,
        "absent": max(expected - attended, 0),
        "rate": attended / expected if expected else 0.0,
    }


def _classes_frame(view: dict) -> pd.DataFrame:
    cols = ["class", "date", "attended", "on_time", "late", "expected"]
    df = pd.DataFrame(view["classes"], columns=cols + ["session_id", "time", "rate"])
    return df[cols]


def by_class(view: dict) -> pd.DataFrame:
    """One row per course title: on time, late, absent, expected and rate."""
    df = _classes_frame(view)
    if df.empty:
        return pd.DataFrame(columns=["class", "present", "late", "absent", "expected", "attended", "rate"])
    g = df.groupby("class", as_index=False)[["attended", "on_time", "late", "expected"]].sum()
    g["absent"] = (g["expected"] - g["attended"]).clip(lower=0)
    g["rate"] = (g["attended"] / g["expected"].where(g["expected"] > 0)).fillna(0.0)
    return g.rename(columns={"on_time": "present"})[["class", "present", "late", "absent", "expected", "attended", "rate"]]


def by_day(view: dict) -> pd.DataFrame:
    """One row per meeting day with present / late / absent rates (share of expected)."""
    df = _classes_frame(view)
    if df.empty:
        return pd.DataFrame(columns=["date", "present", "late", "absent", "rate"])
    g = df.groupby("date", as_index=False)[["attended", "on_time", "late", "expected"]].sum().sort_values("date")
    exp = g["expected"].where(g["expected"] > 0)
    g["rate"] = (g["attended"] / exp).fillna(0.0)
    g["present"] = (g["on_time"] / exp).fillna(0.0)
    g["late"] = (g["late"] / exp).fillna(0.0)
    g["absent"] = (1 - g["rate"]).where(g["expected"] > 0, 0.0)
    return g[["date", "present", "late", "absent", "rate"]]


# ---- empty system / fixed 7-day window ------------------------------------------------------------

def empty_view(start: str, end: str) -> dict:
    """What every page shows before Spark has produced any result: all zeros, no classes."""
    return {
        "start": start, "end": end, "classes": [], "gender": [], "attempts": [], "departments": [], "timeline": [],
        "kpis": {"checkins": 0, "students": 0, "late": 0, "late_rate": 0.0, "expected": 0, "rate": 0.0, "classes": 0,
                 "failed_attempts": 0, "proxy_blocked": 0, "alerts": 0},
    }


def select_or_empty(snapshot: dict | None, period_label: str, class_key: str | None, today: str) -> tuple[dict, set[int], list[dict], tuple[str, str]]:
    """Like :func:`select`, but returns an all-zero selection when there is no Spark snapshot yet."""
    if not snapshot:
        start = (date.fromisoformat(today) - timedelta(days=6)).isoformat()
        return empty_view(start, today), set(), [], (start, today)
    return select(snapshot, period_label, class_key)


def daily_counts(view: dict) -> pd.DataFrame:
    """Present / late / absent head-counts for EVERY day between view start and end (zeros when no class)."""
    days = pd.date_range(view["start"], view["end"], freq="D")
    out = pd.DataFrame({"date": days})
    df = _classes_frame(view)
    if df.empty:
        g = pd.DataFrame(columns=["date", "attended", "on_time", "late", "expected"])
    else:
        g = df.groupby("date", as_index=False)[["attended", "on_time", "late", "expected"]].sum()
        g["date"] = pd.to_datetime(g["date"])
    out = out.merge(g, on="date", how="left").fillna(0)
    out = out.rename(columns={"on_time": "present"})
    out["absent"] = (out["expected"] - out["attended"]).clip(lower=0)
    for col in ("present", "late", "absent", "attended", "expected"):
        out[col] = out[col].astype(int)
    return out[["date", "present", "late", "absent", "attended", "expected"]]
