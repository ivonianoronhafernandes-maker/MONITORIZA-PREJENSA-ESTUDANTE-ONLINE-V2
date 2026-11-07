"""Attendance Reports: summary + per-student preview, exported as PDF or Excel."""
from __future__ import annotations

from datetime import timedelta

import pandas as pd
import streamlit as st

from src.core.config import now_local
from src.data import database as db
from src.data.student_repository import load_students
from src.services import report_service
from src.ui import components as ui
from src.ui import theme

PREVIEW_ROWS = 10
STATE = "_report"


def _options() -> tuple[list[str], list[str]]:
    df = db.fetch_df("SELECT DISTINCT class_name, course_name FROM class_sessions WHERE is_cancelled = 0")
    if df.empty:
        return [], []
    return sorted(df["class_name"].unique()), sorted(df["course_name"].unique())


def _build(start: str, end: str, cls: str, subject: str) -> dict:
    table = report_service.student_report(
        start, end, None if cls == "Klase Hotu" else cls, None if subject == "Matéria Hotu" else subject
    )
    info = report_service.summary(table, len(load_students()))
    parts = [f"{start} to'o {end}"] + [x for x in (cls, subject) if x not in ("Klase Hotu", "Matéria Hotu")]
    return {"key": (start, end, cls, subject), "table": table, "info": info, "title": "Relatóriu Prezensa - " + " - ".join(parts)}


def render() -> None:
    ui.inject_css()
    ui.page_header("Relatóriu Prezensa", "Kria no esporta relatóriu prezensa")
    classes, subjects = _options()
    today = now_local().date()

    with st.container(key="card-rep-filters"):
        f1, f2, f3, f4 = st.columns([2.4, 1.6, 1.6, 1.5], vertical_alignment="bottom")
        picked = f1.date_input("Períodu data", (today - timedelta(days=6), today), format="DD/MM/YYYY", label_visibility="collapsed")
        cls = f2.selectbox("Class", ["Klase Hotu", *classes], label_visibility="collapsed")
        subject = f3.selectbox("Subject", ["Matéria Hotu", *subjects], label_visibility="collapsed")
        generate = f4.button("Kria Relatóriu", icon=":material/description:", type="primary", width="stretch")
        if not (isinstance(picked, tuple) and len(picked) == 2):
            st.info("Hili data hahú no data remata.")
            return
        key = (picked[0].isoformat(), picked[1].isoformat(), cls, subject)
        if generate or STATE not in st.session_state:  # first visit: show the default selection straight away
            st.session_state[STATE] = _build(*key)
        report = st.session_state[STATE]
        if report["key"] != key:
            st.caption("Filtru muda ona - klik **Kria Relatóriu** atu atualiza relatóriu.")

    table, info = report["table"], report["info"]
    left, right = st.columns([1, 2.2])
    with left.container(key="card-rep-summary"):
        ui.card_title("Rezumu Relatóriu")
        st.markdown(
            theme.summary_rows(
                [
                    ("blue", "people", "Total Estudante", info["students"]),
                    ("green", "check", "Prezente", info["present"]),
                    ("red", "cancel", "Falta", info["absent"]),
                    ("amber", "clock", "Atrazu", info["late"]),
                    ("teal", "trend", "Taxa Prezensa", f"{info['rate']:.1%}"),
                ]
            ),
            unsafe_allow_html=True,
        )
    with right.container(key="card-rep-preview"):
        ui.card_title("Vista Relatóriu")
        if table.empty:
            st.markdown(theme.empty_table(["#", *report_service.PREVIEW_COLUMNS], "Seidauk iha data relatóriu."), unsafe_allow_html=True)
        else:
            rows = [
                [str(i), theme.esc(r["Naran Estudante"]), theme.esc(r["Klase"]), str(r["Prezente"]), str(r["Falta"]),
                 str(r["Atrazu"]), theme.rate_text(r["Taxa"])]
                for i, (_, r) in enumerate(table.head(PREVIEW_ROWS).iterrows(), start=1)
            ]
            st.markdown(theme.table(["#", *report_service.PREVIEW_COLUMNS], rows), unsafe_allow_html=True)
            if len(table) > PREVIEW_ROWS:
                st.caption(f"Hatudu {PREVIEW_ROWS} husi estudante {len(table)}. Esporta inklui ema hotu.")
        _, pdf_col, xls_col = st.columns([2, 1, 1])
        stem = f"attendance_report_{key[0]}_{key[1]}"
        pdf_col.download_button(
            "Esporta PDF", report_service.to_pdf(table, info, report["title"]), file_name=f"{stem}.pdf",
            mime="application/pdf", icon=":material/picture_as_pdf:", type="primary", width="stretch",
        )
        xls_col.download_button(
            "Esporta Excel", report_service.to_excel(table, info, report["title"]), file_name=f"{stem}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", icon=":material/table_view:",
            width="stretch",
        )
