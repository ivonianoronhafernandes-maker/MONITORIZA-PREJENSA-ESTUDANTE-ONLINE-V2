"""Dashboard: overview of the last 7 days of attendance.

Headline numbers, trend, status split and per-class bars come from the Spark snapshot
(spark_jobs/). The "lowest attendance" table is read from the database, because Spark does not
keep a per-student history. Before any class or check-in exists every number is zero and every
panel shows an empty state.
"""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from src.core.config import now_local, settings
from src.data.student_repository import load_students
from src.services import dashboard_views as views, spark_analytics, stats_service
from src.ui import components as ui
from src.ui import shell, theme
from src.ui.admin import pipeline_status

CHART_CONFIG = {"displayModeBar": False}
PERIOD = "Last 7 days"


def _pct(part: int, whole: int) -> str:
    return f"{part / whole:.1%}" if whole else "0.0%"


def kpi_cards(total_students: int, c: dict) -> None:
    st.markdown(
        theme.pastel_cards(
            [
                {"tone": "blue", "icon": "people", "label": "Total Estudante", "value": total_students},
                {"tone": "green", "icon": "check", "label": "Prezente", "value": c["present"], "sub": _pct(c["present"], c["expected"])},
                {"tone": "red", "icon": "cancel", "label": "Falta", "value": c["absent"], "sub": _pct(c["absent"], c["expected"])},
                {"tone": "amber", "icon": "clock", "label": "Atrazu", "value": c["late"], "sub": _pct(c["late"], c["expected"])},
            ]
        ),
        unsafe_allow_html=True,
    )


def _trend(view: dict) -> None:
    ui.card_title("Tendénsia Prezensa (Loron 7 Ikus)")
    day = views.daily_counts(view)
    fig = go.Figure(
        go.Scatter(
            x=day["date"], y=day["attended"], mode="lines+markers", name="Tama",
            line=dict(color=theme.BLUE, width=2.5), marker=dict(size=7, color=theme.BLUE),
            fill="tozeroy", fillcolor="rgba(29, 99, 237, 0.10)",
            hovertemplate="%{x|%a %d %b}: %{y} estudante<extra></extra>",
        )
    )
    fig.update_layout(showlegend=False)
    fig.update_xaxes(tickformat="%d %b", type="date")
    ui.integer_axis(fig, "y", float(max(day["attended"].max(), day["expected"].max(), 1)))
    st.plotly_chart(ui.style_fig(fig, 270), width="stretch", config=CHART_CONFIG)


def status_card(c: dict, title: str = "Status Prezensa") -> None:
    ui.card_title(title)
    left, right = st.columns([1, 1], vertical_alignment="center")
    left.plotly_chart(
        theme.donut(c["present"], c["late"], c["absent"], str(c["expected"]), centre_sub="Total"),
        width="stretch", config=CHART_CONFIG,
    )
    right.markdown(theme.legend(c["present"], c["late"], c["absent"], c["expected"]), unsafe_allow_html=True)


def _class_bars(view: dict) -> None:
    ui.card_title("Prezensa Tuir Klase")
    df = views.by_class(view)
    if df.empty:
        st.markdown('<div class="empty-row">Seidauk iha enkontru klase iha loron 7 ikus ne\'e.</div>', unsafe_allow_html=True)
        return
    df = df.sort_values("rate", ascending=False).head(6)
    st.markdown(theme.class_bars(list(zip(df["class"], df["rate"]))), unsafe_allow_html=True)


def lowest_students_table(start: str, end: str, limit: int = 5) -> None:
    people = stats_service.student_rates(start, end)
    people = people[people["held"] > 0].sort_values(["rate", "name"]).head(limit)
    if people.empty:
        st.markdown(theme.empty_table(["#", "Naran", "Klase", "Taxa Prezensa"], "Seidauk iha data prezensa."), unsafe_allow_html=True)
        return
    rows = [
        [str(i), theme.esc(r.name), theme.esc(r.student_class), theme.rate_text(r.rate)]
        for i, r in enumerate(people.itertuples(), start=1)
    ]
    st.markdown(theme.table(["#", "Naran", "Klase", "Taxa Prezensa"], rows), unsafe_allow_html=True)


def _render_body() -> None:
    snapshot = spark_analytics.load_snapshot()
    pipeline_status.notice()
    today = now_local().date().isoformat()
    view, _, alerts, rng = views.select_or_empty(snapshot, PERIOD, None, today)
    counts = views.status_counts(view["kpis"])
    kpi_cards(len(load_students()), counts)

    if alerts:
        analytics = shell.page("analytics")
        msg, link = st.columns([5, 1], vertical_alignment="center")
        msg.warning(f"{len(alerts)} alerta posível prezensa tau-malu (titip absen) iha loron 7 ikus.", icon=":material/warning:")
        if analytics is not None:
            link.page_link(analytics, label="Haree alerta sira", icon=":material/arrow_forward:")

    left, right = st.columns([3, 2])
    with left.container(key="card-trend"):
        _trend(view)
    with right.container(key="card-status"):
        status_card(counts)

    left, right = st.columns([2, 3])
    with left.container(key="card-byclass"):
        _class_bars(view)
    with right.container(key="card-low"):
        ui.card_title("Estudante 5 ho Prezensa Kiik Liu")
        lowest_students_table(rng[0], rng[1])

    if snapshot:
        st.caption(f"Spark kalkula iha {snapshot.get('generated_at', '-')} · pájina atualiza {now_local():%H:%M:%S}")


def _flask_dashboard_url() -> str:
    """Flask dashboard address on the same host the browser used (works from phones / other PCs on the LAN too)."""
    try:
        host = (st.context.headers.get("Host") or "").split(":")[0]
    except Exception:
        host = ""
    if host and not settings.flask_url_fixed:
        return f"http://{host}:5000/dashboard"
    return f"{settings.flask_url}/dashboard"


def render() -> None:
    """The dashboard lives in Flask: go there straight away (link shown in case the browser blocks the redirect)."""
    import streamlit.components.v1 as components

    url = _flask_dashboard_url()
    components.html(f'<script>window.parent.location.href = "{url}";</script>', height=0)
    st.markdown(f"### Hakat ba dashboard...\n[**Klik iha ne'e se la loke aut\u00f3matikamente**]({url})")


def render_streamlit() -> None:
    ui.inject_css()
    title, date_col = st.columns([4, 1.3], vertical_alignment="center")
    with title:
        ui.page_header("Dashboard", "Vizaun jerál prezensa estudante")
    date_col.markdown(theme.date_pill(f"{now_local():%d/%m/%Y}"), unsafe_allow_html=True)

    st.fragment(run_every=settings.dashboard_refresh_seconds)(_render_body)()
