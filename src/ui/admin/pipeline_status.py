"""Kafka + Spark pipeline status: three status cards and the start-up / offline notices."""
from __future__ import annotations

import html

import streamlit as st

from src.core.config import settings
from src.services import spark_analytics
from src.streaming import infrastructure
from src.streaming.runtime import publisher_status
from src.ui import components as ui


def _fmt_age(seconds: float | None) -> str:
    if seconds is None:
        return "nunka"
    if seconds < 90:
        return f"{int(seconds)} segundu liu ona"
    if seconds < 5400:
        return f"{int(seconds // 60)} minutu liu ona"
    return f"{seconds / 3600:.1f} oras liu ona"


# ---- pipeline status ---------------------------------------------------------------------------

_STATUS_CSS = """
<style>
.pipe { display: flex; align-items: center; gap: .75rem; }
.pipe .ico { width: 40px; height: 40px; flex: 0 0 40px; border-radius: 12px; display: grid; place-items: center;
             font-size: 1.2rem; background: var(--info-bg); }
.pipe .name { font-weight: 800; font-size: .92rem; color: var(--ink); display: flex; gap: .45rem; align-items: center; flex-wrap: wrap; }
.pipe small { color: var(--muted); font-size: .78rem; }
[class*="st-key-card-kafka"], [class*="st-key-card-spark"], [class*="st-key-card-results"] { min-height: 96px; justify-content: center; }
.pipe code { font-size: .74rem; background: #f1f5f9; padding: .05rem .35rem; border-radius: 6px; }
</style>
"""


def _status_card(col, key: str, icon: str, name: str, badge_html: str, detail_html: str) -> None:
    with col.container(key=f"card-{key}"):
        st.markdown(
            f'<div class="pipe"><div class="ico">{icon}</div><div><div class="name">{name} {badge_html}</div>'
            f"<small>{detail_html}</small></div></div>",
            unsafe_allow_html=True,
        )


def cards(snapshot: dict | None) -> None:
    kafka = publisher_status()
    spark = spark_analytics.spark_status()
    st.markdown(_STATUS_CSS, unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)

    if not kafka["enabled"]:
        kafka_line = ui.badge("Dezativa", "badge-muted")
    elif kafka["connected"] and not kafka["pending"]:
        kafka_line = ui.badge("Konekta", "badge-good badge-live")
    elif kafka["connected"]:
        kafka_line = ui.badge(f"Haruka {kafka['pending']}", "badge-info")
    else:
        kafka_line = ui.badge(f"La ativu · {kafka['pending']} hein", "badge-bad")
    _status_card(
        c1, "kafka", "📨", "Kafka", kafka_line,
        f"{kafka['total']} evento · topiku <code>{html.escape(settings.kafka_topic)}</code>",
    )

    spark_line = ui.badge("Streaming", "badge-good badge-live") if spark["online"] else ui.badge("La ativu", "badge-bad")
    batch = spark.get("last_batch_id")
    _status_card(
        c2, "spark", "⚡", "Spark Streaming", spark_line,
        f"micro-batch {'#' + str(batch) if batch is not None else '-'} · heartbeat {_fmt_age(spark.get('heartbeat_age'))}",
    )

    if snapshot:
        _status_card(
            c3, "results", "📈", "Rezultadu Spark",
            ui.badge(_fmt_age(spark_analytics.snapshot_age(snapshot)), "badge-info"),
            f"{snapshot.get('events_in_log', 0)} evento · kalkula iha {snapshot.get('compute_seconds', '?')} s",
        )
    else:
        _status_card(c3, "results", "📈", "Rezultadu Spark", ui.badge("Seidauk iha", "badge-muted"), "hein evento dahuluk")


def notice() -> None:
    """Short banner while the pipeline is starting or stopped (nothing when everything is live)."""
    kafka = publisher_status()
    spark = spark_analytics.spark_status()
    infra = infrastructure.status()
    pipeline_up = spark["online"] and (kafka["connected"] or not kafka["enabled"])
    if pipeline_up:
        pass  # everything is live: nothing to announce
    elif infra["state"] in ("waiting", "starting_docker", "starting_containers", "waiting_kafka"):
        st.info(f"⏳ {infra['message']} Check-in rai durante ne'e no prosesa bainhira Spark ativu.")
    elif infra["state"] in ("error", "stopped", "disabled"):
        st.warning(f"{infra['message']} Jere pipeline iha **Konfigurasaun**.")
    elif not spark["online"]:
        st.info(
            "⏳ Kafka ativu; Spark seidauk hahú ho kompletu (hahú dahuluk download konektór Kafka "
            "no presiza minutu 1-2)."
        )
    elif kafka["enabled"] and not kafka["connected"] and kafka.get("last_error"):
        st.caption(f"Kafka: {kafka['last_error']}")


