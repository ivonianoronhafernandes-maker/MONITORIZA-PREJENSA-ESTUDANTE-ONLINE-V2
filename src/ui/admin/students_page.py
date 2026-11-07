"""Students: searchable list with class, e-mail, attendance rate and Good / Medium / Low status.

Student master data lives in data/raw/student.csv. The list is empty until students are added
here ("Add Student") or the CSV is filled in.
"""
from __future__ import annotations

import streamlit as st

from src.data import database as db
from src.data import student_repository as repo
from src.data.student_repository import load_students, normalize_nim
from src.services import stats_service
from src.ui import components as ui
from src.ui import pager, theme

PAGE_SIZE = 10
PAGE_KEY = "students_page"
ALL_STATUS = "Status Hotu"
STATUS_FILTERS = [ALL_STATUS, *theme.LEVEL_TEXT.values()]
GENDERS = ["Male", "Female"]
GENDER_TEXT = {"Male": "Mane", "Female": "Feto"}
HEADERS = ["#", "ID", "Naran", "Klase", "Emél", "Taxa Prezensa", "Status", "Asaun"]


def _history(nim: str):
    frame = db.fetch_df(
        """
        SELECT a.checked_in_at AS checked_in, s.course_name AS subject, s.class_name AS class_name, a.status AS "Status"
        FROM attendance a JOIN class_sessions s ON s.id = a.session_id
        WHERE a.nim = ? ORDER BY a.checked_in_at DESC
        """,
        (normalize_nim(nim),),
    )
    return frame.rename(columns={"checked_in": "Oras Tama", "subject": "Matéria", "class_name": "Klase"})


def _student_form(key: str, student: dict | None) -> tuple[bool, dict]:
    """Shared fields of the Add and Edit dialogs. Returns (submitted, values)."""
    s = student or {}
    with st.form(key, border=False):
        c1, c2 = st.columns(2)
        nim = c1.text_input("ID Estudante (NIM) *", value=s.get("nim", ""), disabled=student is not None)
        name = c2.text_input("Naran kompletu *", value=s.get("name", ""))
        c1, c2 = st.columns(2)
        gender = c1.selectbox("Sexu", GENDERS, format_func=GENDER_TEXT.get, index=GENDERS.index(s["gender"]) if s.get("gender") in GENDERS else 0)
        email = c2.text_input("Emél", value=s.get("email", ""), placeholder="naran@example.com")
        c1, c2, c3 = st.columns(3)
        faculty = c1.text_input("Fakuldade", value=s.get("faculty", ""))
        department = c2.text_input("Departamentu", value=s.get("department", ""), placeholder="ez. CS")
        cohort = c3.text_input("Turno", value=s.get("cohort", ""), placeholder="ez. 2024")
        submitted = st.form_submit_button("Rai mudansa" if student else "Aumenta estudante", type="primary", width="stretch")
    return submitted, {
        "nim": s.get("nim", "") if student else nim, "name": name, "gender": gender, "faculty": faculty,
        "department": department, "cohort": cohort, "email": email,
    }


@st.dialog("Aumenta Estudante")
def _add_dialog() -> None:
    submitted, values = _student_form("add_student_form", None)
    if submitted:
        try:
            repo.add_student(**values)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.session_state["_toast"] = f"{values['name'].strip()} aumenta ona"
            st.rerun()


@st.dialog("Edita Estudante")
def _edit_dialog(student: dict) -> None:
    submitted, values = _student_form(f"edit_student_form_{student['nim']}", student)
    if submitted:
        try:
            repo.update_student(**values)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.session_state["_toast"] = "Estudante atualiza ona"
            st.rerun()


@st.dialog("Detallu Estudante", width="large")
def _view_dialog(student: dict) -> None:
    history = _history(student["nim"])
    ui.student_card(student)
    c1, c2, c3 = st.columns(3)
    c1.metric("Klase ne'ebé tama", len(history))
    c2.metric("Atrazu", int((history["Status"] == "Late").sum()) if not history.empty else 0)
    c3.metric("Taxa prezensa", f"{student['rate']:.1%}" if student["held"] else "-")
    if student.get("email"):
        st.caption(f"Emél: {student['email']}")
    if history.empty:
        st.caption("Seidauk iha prezensa ne'ebé rejista.")
    else:
        st.dataframe(history.assign(Status=history["Status"].map(theme.status_text)), hide_index=True, width="stretch")


def _reset_page() -> None:
    st.session_state[PAGE_KEY] = 1


def _filters(students):
    f1, f2, f3, f4 = st.columns([3, 1.6, 1.6, 1.3], vertical_alignment="bottom")
    query = f1.text_input("Search", key="students_q", placeholder="Buka tuir naran ka ID...", label_visibility="collapsed")
    classes = f2.selectbox("Class", ["Klase Hotu", *sorted(students["class_name"].unique())], label_visibility="collapsed", on_change=_reset_page)
    status = f3.selectbox("Status", STATUS_FILTERS, label_visibility="collapsed", on_change=_reset_page)
    if f4.button("Aumenta Estudante", icon=":material/add:", type="primary", width="stretch"):
        _add_dialog()
    view = students
    q = query.strip().lower()
    if q:
        view = view[view["name"].str.lower().str.contains(q, regex=False) | view["nim"].str.lower().str.contains(q, regex=False)]
    if classes != "Klase Hotu":
        view = view[view["class_name"] == classes]
    if status != ALL_STATUS:
        level = next(k for k, v in theme.LEVEL_TEXT.items() if v == status)
        view = view[(view["held"] > 0) & (view["rate"].map(theme.level) == level)]
    return view, (query, classes, status)


def _table(view, first_index: int) -> None:
    if view.empty:
        st.markdown(
            theme.empty_table(HEADERS, "Seidauk iha estudante. Uza <b>Aumenta Estudante</b> atu rejista dahuluk."),
            unsafe_allow_html=True,
        )
        return
    rows = []
    for i, r in enumerate(view.itertuples(), start=first_index):
        has_data = r.held > 0
        rows.append(
            [
                str(i), theme.esc(r.nim), theme.esc(r.name), theme.esc(r.class_name), theme.esc(r.email or "-"),
                theme.rate_text(r.rate) if has_data else "-",
                theme.level_pill(r.rate) if has_data else '<span class="st-pill muted">La iha data</span>',
                '<span class="act">👁 ✎</span>',
            ]
        )
    st.markdown(
        theme.table(HEADERS, rows, ["", "mono", "", "", "", "", "", ""]),
        unsafe_allow_html=True,
    )


def _actions(view) -> None:
    """Row actions: the HTML table cannot hold buttons, so pick a student here to view or edit."""
    if view.empty:
        return
    options = {r.nim: f"{r.name} ({r.nim})" for r in view.itertuples()}
    c1, c2, c3 = st.columns([4, 1, 1], vertical_alignment="bottom")
    nim = c1.selectbox("Estudante", list(options), format_func=options.get, index=None, placeholder="Hili estudante atu haree ka edita", key="students_pick")
    student = view[view["nim"] == nim].iloc[0].to_dict() if nim else None
    if c2.button("Haree", icon=":material/visibility:", width="stretch", disabled=student is None):
        _view_dialog(student)
    if c3.button("Edita", icon=":material/edit:", width="stretch", disabled=student is None):
        _edit_dialog(student)


def render() -> None:
    ui.inject_css()
    ui.page_header("Estudante", "Jere data estudante")
    if msg := st.session_state.pop("_toast", None):
        st.toast(msg, icon="✅")

    students = load_students()
    rates = stats_service.lifetime_rates()[["nim", "held", "attended", "rate"]]
    students = students.merge(rates, on="nim", how="left").fillna({"held": 0, "attended": 0, "rate": 0.0})
    students[["held", "attended"]] = students[["held", "attended"]].astype(int)

    with st.container(key="card-students"):
        view, signature = _filters(students)
        if st.session_state.get("_students_sig") != signature:
            st.session_state["_students_sig"] = signature
            st.session_state[PAGE_KEY] = 1  # a new filter starts on page 1
        pages = pager.total_pages(len(view), PAGE_SIZE)
        page = pager.current_page(PAGE_KEY, pages)
        chunk = view.iloc[(page - 1) * PAGE_SIZE: page * PAGE_SIZE]
        _table(chunk, (page - 1) * PAGE_SIZE + 1)
        pager.render(PAGE_KEY, len(view), PAGE_SIZE, "estudante")
    with st.container(key="card-student-actions"):
        _actions(chunk)
