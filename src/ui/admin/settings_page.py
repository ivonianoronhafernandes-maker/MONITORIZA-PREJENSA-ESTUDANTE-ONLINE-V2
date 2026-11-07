"""Admin account settings: change password, add and remove admins."""
from __future__ import annotations

import html
import sqlite3
import tempfile
from pathlib import Path

import streamlit as st

from src.core.config import now_local, settings
from src.data import database as db
from src.services import settings_service, spark_analytics
from src.streaming import infrastructure, outbox
from src.streaming.runtime import publisher_status
from src.ui import components as ui
from src.ui import theme
from src.ui.admin import classes_page, pipeline_status


def _streaming() -> None:
    ui.card_title("Pipeline streaming (Kafka + Spark)")
    kafka = publisher_status()
    spark = spark_analytics.spark_status()
    st.markdown(
        ui.meta_grid(
            {
                "Kafka broker": settings.kafka_bootstrap if settings.kafka_enabled else "Dezativa",
                "Topiku Kafka": settings.kafka_topic,
                "Koneksaun Kafka": "Konekta" if kafka["connected"] else "La ativu",
                "Evento iha outbox": f"{kafka['total']} ({kafka['pending']} hein)",
                "Spark stream": "Streaming" if spark["online"] else "La ativu",
                "Rezultadu Spark": str(settings.spark_output_dir.name),
            }
        ),
        unsafe_allow_html=True,
    )
    infra = infrastructure.status()
    st.caption(f"Docker: {infra['message']}")
    st.caption("Kafka UI: http://localhost:8085 · Spark UI: http://localhost:4040")

    c1, c2, c3 = st.columns(3)
    busy = infra["state"] in ("starting_docker", "starting_containers", "waiting_kafka")
    if c1.button("Hahú Kafka & Spark", width="stretch", disabled=busy):
        infrastructure.start(force=True)
        st.toast("Hahú Kafka no Spark iha background...", icon="⏳")
        st.rerun()
    with c2.popover("Para Kafka & Spark", width="stretch", disabled=busy):
        st.write("Dashboard para atualiza to'o ita hahú fali. Check-in kontinua servisu "
                 "no prosesa bainhira pipeline fila fali. La iha data ne'ebé hamoos.")
        if st.button("Para agora", type="primary"):
            with st.spinner("Hapara container sira..."):
                infrastructure.stop()
            st.rerun()
    with c3.popover("Haruka fali evento hotu ba Kafka", width="stretch"):
        st.write(
            "Use this after wiping Kafka/Spark (`docker compose down -v`). Every event is sent again; "
            "Spark ignores events it has already processed, so nothing is counted twice."
        )
        if st.button("Haruka fali hotu", type="primary"):
            n = outbox.reset_published()
            st.success(f"Evento {n} hein hodi haruka ba Kafka.")


VERSION = "1.0.0"
DEVELOPER = "Grupo 1 · DIT 2026"


def _general() -> None:
    values = settings_service.get_all()
    left, right = st.columns([1.5, 1])
    with left.container(key="card-set-general"):
        ui.card_title("Konfigurasaun Jerál")
        with st.form("general_settings", border=False):
            name = st.text_input("Naran Sistema", value=values["system_name"])
            year = st.text_input("Tinan Akadémiku", value=values["academic_year"])
            status = st.selectbox(
                "Status Prezensa Default", settings_service.STATUSES, format_func=theme.status_text,
                index=settings_service.STATUSES.index(values["default_status"]),
                help="Status ne'ebé hili uluk bainhira aumenta estudante ba enkontru ho liman.",
            )
            language = st.selectbox("Lian", settings_service.LANGUAGES, index=settings_service.LANGUAGES.index(values["language"]))
            if st.form_submit_button("Rai Konfigurasaun", icon=":material/save:", type="primary"):
                try:
                    settings_service.save(name, year, status, language)
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    st.toast("Konfigurasaun rai ona", icon="✅")
                    st.rerun()
    with right:
        with st.container(key="card-set-db"):
            ui.card_title("Informasaun Database")
            try:
                db.fetch_one("SELECT 1")
                connected = True
            except Exception:
                connected = False
            size = f"{settings.database_path.stat().st_size / 1024:,.0f} KB" if settings.database_path.exists() else "-"
            st.markdown(
                _kv({"Tipu": "SQLite", "Fixeiru": settings.database_path.name, "Boot": size, "Fatin": "lokál"})
                + f'<div style="margin-top:.7rem"><span class="dot-ok{"" if connected else " off"}">{"Konekta" if connected else "La konekta"}</span></div>',
                unsafe_allow_html=True,
            )
        with st.container(key="card-set-sys"):
            ui.card_title("Informasaun Sistema")
            st.markdown(
                _kv({"Versaun": VERSION, "Atualiza Ikus": settings_service.last_update(), "Zona oras": f"UTC+{settings.utc_offset_hours}",
                     "Dezenvolvedór": DEVELOPER}),
                unsafe_allow_html=True,
            )


def _kv(items: dict[str, str]) -> str:
    cells = "".join(f'<div class="k">{html.escape(k)}</div><div class="v">{html.escape(str(v))}</div>' for k, v in items.items())
    return f'<div class="kv">{cells}</div>'


def _subjects() -> None:
    with st.container(key="card-set-subjects"):
        ui.card_title("Matéria")
        st.caption("Matéria kria hamutuk ho kursu iha tab **Klase**. Lista ne'e hatudu saida mak iha to'o agora.")
        df = db.fetch_df(
            """
            SELECT course_name AS subject, COUNT(DISTINCT class_name) AS classes, COUNT(*) AS meetings,
                   MIN(session_date) AS first_meeting, MAX(session_date) AS last_meeting
            FROM class_sessions GROUP BY course_name ORDER BY course_name
            """
        )
        df = df.rename(columns={"subject": "Matéria", "classes": "Klase", "meetings": "Enkontru", "first_meeting": "Enkontru dahuluk", "last_meeting": "Enkontru ikus"})
        if df.empty:
            st.markdown(theme.empty_table(["Matéria", "Klase", "Enkontru", "Enkontru dahuluk", "Enkontru ikus"], "Seidauk iha matéria."), unsafe_allow_html=True)
        else:
            st.dataframe(df, hide_index=True, width="stretch")


def _database_copy() -> bytes:
    """Consistent snapshot of the SQLite database (safe while students are checking in)."""
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "attendance_backup.db"
        source = sqlite3.connect(settings.database_path)
        dest = sqlite3.connect(target)
        try:
            source.backup(dest)
        finally:
            dest.close()
            source.close()
        return target.read_bytes()


def _backup() -> None:
    ui.card_title("Backup")
    st.caption("Download kópia data. Rai backup iha fatin seguru: ne'e iha naran no NIM estudante.")
    c1, c2 = st.columns(2)
    stamp = f"{now_local():%Y%m%d_%H%M}"
    if settings.database_path.exists():
        c1.download_button(
            "Download database prezensa", _database_copy(), file_name=f"attendance_{stamp}.db",
            mime="application/octet-stream", icon=":material/database:", width="stretch",
        )
    if settings.student_csv.exists():
        c2.download_button(
            "Download lista estudante (CSV)", settings.student_csv.read_bytes(), file_name=settings.student_csv.name,
            mime="text/csv", icon=":material/groups:", width="stretch",
        )


def render() -> None:
    ui.inject_css()
    ui.page_header("Konfigurasaun", "Konfigurasaun sistema")
    general, classes, subjects, database = st.tabs(["Jerál", "Klase", "Matéria", "Database"])
    with general:
        _general()
    with classes:
        classes_page.render_body()
    with subjects:
        _subjects()
    with database:
        with st.container(key="card-set-pipeline"):
            _streaming()
        pipeline_status.cards(spark_analytics.load_snapshot())
        with st.container(key="card-set-backup"):
            _backup()
