"""Attendance Records: browse, filter, import and correct attendance (including absences)."""
from __future__ import annotations

from datetime import timedelta

import pandas as pd
import streamlit as st

from src.core.config import now_local
from src.services import attendance_service, import_service, stats_service
from src.ui import components as ui
from src.ui import pager, theme

PAGE_SIZE = 10
PAGE_KEY = "records_page"
HEADERS = ["#", "ID", "Naran Estudante", "Klase", "Matéria", "Data", "Oras", "Status", ""]
EXPORT_COLUMNS = [
    "id", "date", "checked_in_at", "subject", "class_name", "nim", "name", "gender", "faculty",
    "department", "cohort", "status", "source", "ip_address",
]


def _combined(start: str, end: str) -> pd.DataFrame:
    """Check-ins plus absences in one table (absent rows have no id, time or IP)."""
    att = attendance_service.attendance_frame(start, end)
    if not att.empty:
        att = att.assign(
            date=att["attendance_date"], subject=att["course_name"],
            source=att["added_by_admin"].map({1: "Admin", 0: "Student"}).fillna("Student"),
        )
    gone = stats_service.absent_records(start, end)
    if not gone.empty:
        gone = gone.assign(id=pd.NA, date=gone["session_date"], checked_in_at=pd.NaT, status="Absent", source="", ip_address="")
    parts = [df for df in (att, gone) if not df.empty]
    if not parts:
        return pd.DataFrame(columns=EXPORT_COLUMNS)
    both = pd.concat([p.reindex(columns=EXPORT_COLUMNS) for p in parts], ignore_index=True)
    both["checked_in_at"] = pd.to_datetime(both["checked_in_at"])
    return both.sort_values(["date", "checked_in_at"], ascending=[False, False], na_position="last", kind="stable").reset_index(drop=True)


@st.dialog("Importa data prezensa", width="large")
def _import_dialog() -> None:
    st.caption(
        "Upload CSV ho kolona **student_id, class, subject, date, time, status** "
        "(oras opsionál; status Present ka Late). Kada liña tama ba enkontru ho klase, matéria no data ne'ebá."
    )
    st.download_button("Download modelu CSV", import_service.TEMPLATE, file_name="attendance_import_template.csv",
                       mime="text/csv", icon=":material/download:")
    upload = st.file_uploader("Fixeiru CSV", type=["csv"], label_visibility="collapsed")
    if upload is None:
        return
    try:
        raw = pd.read_csv(upload, dtype=str, keep_default_na=False)
        import_service.normalize_columns(raw)
    except Exception as exc:  # unreadable file or wrong columns
        st.error(str(exc))
        return
    st.dataframe(raw.head(8), hide_index=True, width="stretch")
    st.caption(f"Hetan liña {len(raw)}.")
    if st.button("Importa", type="primary", icon=":material/upload:"):
        report = import_service.import_frame(raw)
        if report.imported:
            st.success(f"Rejistu {report.imported} importa ona.")
        if report.skipped:
            st.warning(f"Liña {len(report.skipped)} la tama:")
            st.code("\n".join(report.skipped[:50]), language=None)
        elif report.imported:
            st.session_state["_toast"] = f"Rejistu {report.imported} importa ona"


def _filters():
    today = now_local().date()
    f1, f2, f3, f4, f5, f6 = st.columns([2.2, 1.5, 1.5, 1.4, 1.3, 1.1], vertical_alignment="bottom")
    picked = f1.date_input("Períodu data", (today - timedelta(days=6), today), format="DD/MM/YYYY", label_visibility="collapsed")
    return picked, f2, f3, f4, f5, f6


def _table(chunk: pd.DataFrame, first_index: int) -> None:
    if chunk.empty:
        st.markdown(theme.empty_table(HEADERS, "La iha rejistu prezensa ba seleisaun ne'e."), unsafe_allow_html=True)
        return
    rows = []
    for i, r in enumerate(chunk.itertuples(), start=first_index):
        rows.append(
            [
                str(i), theme.esc(r.nim), theme.esc(r.name), theme.esc(r.class_name), theme.esc(r.subject),
                f"{pd.to_datetime(r.date):%d/%m/%Y}", f"{r.checked_in_at:%H:%M}" if pd.notna(r.checked_in_at) else "-",
                theme.pill(r.status), '<span class="act">👁</span>',
            ]
        )
    st.markdown(theme.table(HEADERS, rows, ["", "mono", "", "", "", "", "", "", ""]), unsafe_allow_html=True)


def _details(view: pd.DataFrame) -> None:
    real = view[view["id"].notna()]
    with st.expander("Detallu rejistu & korreisaun"):
        options = {
            int(r.id): f"#{int(r.id)} · {r.name} · {r.subject} · {r.checked_in_at:%d %b %H:%M}" for r in real.head(200).itertuples()
        }
        record_id = st.selectbox("Rejistu", list(options), format_func=options.get, index=None, placeholder="Hili rejistu ida")
        if record_id:
            r = real[real["id"] == record_id].iloc[0]
            st.markdown(
                ui.meta_grid(
                    {"Estudante": f"{r['name']} ({r['nim']})", "Matéria": r["subject"], "Klase": r["class_name"],
                     "Oras tama": f"{r['checked_in_at']:%d/%m/%Y %H:%M:%S}", "Aumenta husi": r["source"], "Enderesu IP": r["ip_address"] or "-"}
                ),
                unsafe_allow_html=True,
            )
            if st.button("Hamoos rejistu", type="primary", icon=":material/delete:"):
                attendance_service.delete_record(int(record_id))
                st.toast("Rejistu hamoos ona", icon="🗑️")
                st.rerun()


def render() -> None:
    ui.inject_css()
    ui.page_header("Rejistu Prezensa", "Haree no jere data prezensa")
    if msg := st.session_state.pop("_toast", None):
        st.toast(msg, icon="✅")

    with st.container(key="card-records"):
        picked, f2, f3, f4, f5, f6 = _filters()
        if not (isinstance(picked, tuple) and len(picked) == 2):
            st.info("Hili data hahú no data remata.")
            return
        s, e = picked[0].isoformat(), picked[1].isoformat()
        data = _combined(s, e)
        class_options = sorted(data["class_name"].dropna().unique()) if not data.empty else []
        subject_options = sorted(data["subject"].dropna().unique()) if not data.empty else []
        cls = f2.selectbox("Class", ["Klase Hotu", *class_options], label_visibility="collapsed")
        subject = f3.selectbox("Subject", ["Matéria Hotu", *subject_options], label_visibility="collapsed")
        status = f4.selectbox("Status", ["Status Hotu", "Present", "Late", "Absent"], format_func=lambda x: x if x == "Status Hotu" else theme.status_text(x), label_visibility="collapsed")
        if f5.button("Importa Data", icon=":material/upload:", type="primary", width="stretch"):
            _import_dialog()

        view = data
        if cls != "Klase Hotu":
            view = view[view["class_name"] == cls]
        if subject != "Matéria Hotu":
            view = view[view["subject"] == subject]
        if status != "Status Hotu":
            view = view[view["status"] == status]
        f6.download_button(
            "Esporta", view[EXPORT_COLUMNS].to_csv(index=False).encode("utf-8"), file_name=f"attendance_{s}_{e}.csv",
            mime="text/csv", icon=":material/download:", width="stretch", disabled=view.empty,
        )

        signature = (s, e, cls, subject, status)
        if st.session_state.get("_records_sig") != signature:
            st.session_state["_records_sig"] = signature
            st.session_state[PAGE_KEY] = 1  # a new filter starts on page 1
        pages = pager.total_pages(len(view), PAGE_SIZE)
        page = pager.current_page(PAGE_KEY, pages)
        _table(view.iloc[(page - 1) * PAGE_SIZE: page * PAGE_SIZE], (page - 1) * PAGE_SIZE + 1)
        pager.render(PAGE_KEY, len(view), PAGE_SIZE, "rejistu")

    if not view.empty:
        _details(view)
