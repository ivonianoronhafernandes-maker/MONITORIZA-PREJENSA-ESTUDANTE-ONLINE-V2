"""Analytics: attendance rate, trend, per-class comparison and students with low attendance.

Numbers come from the Spark snapshot (and the database for the per-student table). The proxy
attendance detection from Spark stays at the bottom of the page. Everything is zero / empty
until the first class and check-in exist.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.core.config import now_local, settings
from src.data.student_repository import load_students
from src.services import dashboard_views as views, spark_analytics
from src.ui import components as ui
from src.ui import theme
from src.ui.admin import dashboard_page as dash

CHART_CONFIG = {"displayModeBar": False}

RULE_LABELS = {
    "device_reuse": "Telemovel ida, estudante barak",
    "shared_ip": "Estudante barak husi IP ida",
    "rapid_burst": "Check-in lais tuir malu",
    "nim_guessing": "Tebak NIM",
    "overlapping_classes": "Iha klase rua hamutuk",
}
SEVERITY_LABELS = {"high": "Aas", "medium": "Média", "low": "Ki'ik"}



def _rate_gauge(counts: dict) -> None:
    ui.card_title("Taxa Prezensa")
    attended, expected = counts["attended"], counts["expected"]
    values = [attended, max(expected - attended, 0)] if expected else [0, 1]
    fig = go.Figure(
        go.Pie(
            values=values, hole=0.76, sort=False, direction="clockwise", textinfo="none", hoverinfo="skip",
            marker=dict(colors=[theme.GREEN, "#d8f1e2" if expected else "#e5ebf5"], line=dict(color="#fff", width=2)),
        )
    )
    fig.update_layout(
        height=230, margin=dict(l=0, r=0, t=0, b=0), showlegend=False, paper_bgcolor="rgba(0,0,0,0)",
        annotations=[dict(text=f"<b>{counts['rate']:.1%}</b>", x=0.5, y=0.5, showarrow=False, font=dict(size=24, color="#0f1f3d"))],
    )
    st.plotly_chart(fig, width="stretch", config=CHART_CONFIG)


def _tiles(total_students: int, counts: dict) -> None:
    st.markdown(
        theme.mini_cards(
            [
                {"tone": "blue", "icon": "people", "label": "Total Estudante", "value": total_students},
                {"tone": "green", "icon": "check", "label": "Prezente", "value": counts["present"]},
                {"tone": "red", "icon": "cancel", "label": "Falta", "value": counts["absent"]},
                {"tone": "amber", "icon": "clock", "label": "Atrazu", "value": counts["late"]},
            ]
        ),
        unsafe_allow_html=True,
    )


def _trend_lines(view: dict) -> None:
    ui.card_title("Tendénsia Prezensa")
    day = views.daily_counts(view)
    fig = go.Figure()
    for col, label in (("present", "Present"), ("absent", "Absent"), ("late", "Late")):
        fig.add_scatter(
            x=day["date"], y=day[col], name=theme.status_text(label), mode="lines+markers",
            line=dict(color=ui.STATUS_COLORS[label], width=2.2), marker=dict(size=6),
            hovertemplate=f"%{{x|%a %d %b}}<br>{theme.status_text(label)}: %{{y}}<extra></extra>",
        )
    fig.update_xaxes(tickformat="%d %b", type="date")
    fig.update_layout(legend=dict(orientation="h", y=1.14, x=1, xanchor="right"))
    ui.integer_axis(fig, "y", float(max(day[["present", "absent", "late"]].max().max(), 1)))
    st.plotly_chart(ui.style_fig(fig, 260), width="stretch", config=CHART_CONFIG)


def _by_class(view: dict) -> None:
    ui.card_title("Prezensa Tuir Klase")
    df = views.by_class(view)
    if df.empty:
        st.markdown('<div class="empty-row">Seidauk iha enkontru klase iha períodu ne\'e.</div>', unsafe_allow_html=True)
        return
    fig = go.Figure()
    for col, label in (("present", "Present"), ("absent", "Absent"), ("late", "Late")):
        fig.add_bar(x=df["class"], y=df[col], name=theme.status_text(label), marker_color=ui.STATUS_COLORS[label],
                    hovertemplate=f"%{{x}}<br>{theme.status_text(label)}: %{{y}}<extra></extra>")
    fig.update_layout(barmode="group", bargap=0.3, legend=dict(orientation="h", y=1.14, x=1, xanchor="right"))
    ui.integer_axis(fig, "y", float(df[["present", "absent", "late"]].max().max()))
    st.plotly_chart(ui.style_fig(fig, 260), width="stretch", config=CHART_CONFIG)


def _alerts(alerts: list[dict]) -> None:
    ui.card_title("Detesaun prezensa tau-malu (titip absen)")
    st.caption(
        "Padraun ne'ebé Spark hetan iha stream check-in. Ne'e sinál atu revee, la’os prova: "
        "konfirma ho estudante sira molok foti asaun."
    )
    if not alerts:
        st.success("La hetan padraun suspeitu iha seleisaun ne'e.")
        return
    df = pd.DataFrame(alerts)
    df["severity"] = df["severity"].map(SEVERITY_LABELS).fillna(df["severity"])
    df["rule"] = df["rule"].map(RULE_LABELS).fillna(df["rule"])
    df["nims"] = df["nims"].map(lambda n: ", ".join(n or []))
    st.dataframe(
        df[["severity", "rule", "class_title", "detail", "nims", "subject", "last_seen"]],
        hide_index=True, width="stretch",
        column_config={
            "severity": st.column_config.TextColumn("Nível", width=100),
            "rule": "Padraun", "class_title": "Klase",
            "detail": st.column_config.TextColumn("Saida Spark hetan", width="large"),
            "nims": "NIM involvidu", "subject": "Aparellu / IP", "last_seen": "Haree ikus",
        },
    )



def _render_body(period_label: str) -> None:
    snapshot = spark_analytics.load_snapshot()
    today = now_local().date().isoformat()
    view, _, alerts, rng = views.select_or_empty(snapshot, period_label, None, today)
    counts = views.status_counts(view["kpis"])

    left, right = st.columns([1, 2.3], vertical_alignment="center")
    with left.container(key="card-an-rate"):
        _rate_gauge(counts)
    with right:
        _tiles(len(load_students()), counts)

    left, right = st.columns(2)
    with left.container(key="card-an-trend"):
        _trend_lines(view)
    with right.container(key="card-an-class"):
        _by_class(view)

    left, right = st.columns(2)
    with left.container(key="card-an-status"):
        dash.status_card(counts)
    with right.container(key="card-an-low"):
        ui.card_title("Estudante ho Prezensa Kiik")
        dash.lowest_students_table(rng[0], rng[1])

    with st.container(key="card-an-alerts"):
        _alerts(alerts)
    if snapshot:
        st.caption(f"Spark kalkula iha {snapshot.get('generated_at', '-')} · pájina atualiza {now_local():%H:%M:%S}")


def render() -> None:
    ui.inject_css()
    title, f_period = st.columns([4, 1.6], vertical_alignment="bottom")
    with title:
        ui.page_header("Analiza", "Analiza padraun no informasaun prezensa")
    period = f_period.selectbox("Period", list(views.PERIODS), index=1, key="an_period", label_visibility="collapsed")
    st.fragment(run_every=settings.dashboard_refresh_seconds)(_render_body)(period)
