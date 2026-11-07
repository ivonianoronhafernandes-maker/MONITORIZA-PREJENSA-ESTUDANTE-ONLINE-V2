"""Semester courses on the Classes page: weekly schedule, one permanent QR, attendance grade report."""
from __future__ import annotations

from datetime import time, timedelta

import streamlit as st

from src.core.config import now_local, settings
from src.data.student_repository import list_departments
from src.services import attendance_service, class_service, course_service, settings_service
from src.services.attendance_service import CheckInResult
from src.services.course_service import WEEKDAYS
from src.ui import components as ui
from src.ui import theme


def _create_form() -> None:
    today = now_local().date()
    with st.form("create_course", clear_on_submit=True, border=True):
        ui.card_title("Kursu semestre foun")
        st.caption(
            "Define orariu semana dala ida de'it. Enkontru hotu iha semestre kria automátiku; check-in "
            f"loke minutu {settings.checkin_early_minutes} molok enkontru kada no taka iha oras remata."
        )
        c1, c2 = st.columns(2)
        course = c1.text_input("Naran matéria/kursu *", placeholder="ez. Data Mining")
        class_name = c2.text_input("Klase / grupu *", placeholder="ez. CS-2024-A")
        c1, c2 = st.columns(2)
        lecturer = c1.text_input("Dosente", placeholder="ez. Dr. Maria Soares")
        room = c2.text_input("Sala", placeholder="ez. Lab 2")
        days = st.multiselect(
            "Loron semana *", list(range(7)), default=[0, 2], format_func=lambda d: WEEKDAYS[d]
        )
        c1, c2, c3 = st.columns(3)
        start = c1.time_input("Hahú", value=time(8, 30), step=300)
        end = c2.time_input("Remata", value=time(10, 30), step=300)
        late = c3.number_input("Atrazu depois (minutu)", min_value=0, max_value=240, value=15, step=5)
        c1, c2 = st.columns(2)
        first_day = c1.date_input("Semestre hahú", value=today, format="DD/MM/YYYY")
        last_day = c2.date_input("Semestre remata", value=today + timedelta(weeks=17), format="DD/MM/YYYY")
        departments = st.multiselect("Limita ba departamentu", list_departments(), placeholder="Departamentu hotu")

        if st.form_submit_button("Kria orariu semestre", type="primary"):
            try:
                with st.spinner("Kria enkontru hotu..."):
                    created = course_service.create_course(
                        course_name=course,
                        class_name=class_name,
                        lecturer=lecturer,
                        room=room,
                        weekdays=days,
                        start_time=start,
                        end_time=end,
                        start_date=first_day,
                        end_date=last_day,
                        late_after_minutes=int(late),
                        departments=departments,
                    )
            except ValueError as exc:
                st.error(str(exc))
            else:
                n = len(course_service.meetings(created.id))
                st.session_state["open_course_id"] = created.id
                st.success(f"{created.title}: enkontru {n} kria ona ({created.schedule_text}). QR ida ba semestre tomak.")


def _overview(course: course_service.Course) -> None:
    meetings = course_service.meetings(course.id)
    held = course_service.held_meetings(course)
    nxt = course_service.current_meeting(course)
    link_col, qr_col = st.columns([3, 1])
    with link_col:
        ui.card_title("Kódigu klase & link permanente (semestre tomak)")
        st.markdown(
            f'<div class="class-code"><span>Kódigu klase</span><b>{course.token}</b>'
            f"<small>Estudante uza link ka scan QR atu halo check-in.</small></div>",
            unsafe_allow_html=True,
        )
        st.code(course.link, language=None)
        st.markdown(
            ui.meta_grid(
                {
                    "Orariu": course.schedule_text,
                    "Semestre": f"{course.start_date:%d %b %Y} - {course.end_date:%d %b %Y}",
                    "Enkontru": f"{len(held)} hala'o / {len(meetings)} total",
                    "Agora / tuir mai": f"{nxt.session_date:%a %d %b} {nxt.start_time:%H:%M}" if nxt else "-",
                    "Atrazu depois": f"{course.late_after_minutes} min",
                    "Departamentu": ", ".join(course.departments) or "Hotu",
                    "Dosente": course.lecturer or "-",
                    "Sala": course.room or "-",
                }
            ),
            unsafe_allow_html=True,
        )
        st.write("")
        b1, b2, b3, b4 = st.columns(4)
        if course.is_active:
            if b1.button("Hapara kursu", key=f"cpause_{course.id}", width="stretch", help="Hapara check-in ba enkontru hotu"):
                course_service.set_active(course.id, False)
                st.rerun()
        elif b1.button("Kontinua kursu", key=f"cresume_{course.id}", width="stretch"):
            course_service.set_active(course.id, True)
            st.rerun()
        if b2.button("Link foun", key=f"cregen_{course.id}", width="stretch", help="Link/QR tuan la servisu tan"):
            course_service.regenerate_token(course.id)
            st.rerun()
        b3.link_button("Loke pájina", course.link, width="stretch")
        with b4.popover("Hamoos", width="stretch"):
            st.warning("Hamoos kursu, enkontru hotu no rejistu prezensa hotu.")
            if st.button("Konfirma hamoos", key=f"cdel_{course.id}", type="primary"):
                course_service.delete_course(course.id)
                st.rerun()
    with qr_col:
        png = ui.qr_png(course.link)
        st.image(png, caption="QR hanesan ba enkontru hotu", width="stretch")
        st.download_button(
            "Download QR", png, file_name=f"qr_{course.course_name}_{course.class_name}.png", mime="image/png",
            key=f"cqr_{course.id}", width="stretch",
        )


def _grade_tab(course: course_service.Course) -> None:
    report, held = course_service.attendance_report(course)
    st.caption(
        f"Bazeia ba enkontru **{held}** ne'ebé hala'o ona (enkontru kansela la konta). "
        "Atrazu konta nu'udar tama no hatudu separadu."
    )
    if held == 0:
        st.info("Seidauk iha enkontru ne'ebé hala'o.")
        return
    st.dataframe(
        report,
        hide_index=True,
        width="stretch",
        column_config={
            "nim": "NIM",
            "name": "Naran",
            "department": "Dep.",
            "cohort": "Turno",
            "on_time": "Tuir oras",
            "late": "Atrazu",
            "attended": "Tama",
            "absent": "Falta",
            "attendance_pct": st.column_config.ProgressColumn(
                "Prezensa", format="percent", min_value=0, max_value=1
            ),
        },
    )
    export = report.assign(attendance_pct=(report["attendance_pct"] * 100).round(1), meetings_held=held)
    st.download_button(
        "Download relatóriu nota (CSV)",
        export.to_csv(index=False).encode("utf-8"),
        file_name=f"attendance_grade_{course.course_name}_{course.class_name}.csv",
        mime="text/csv",
        key=f"cgrade_{course.id}",
    )


def _meetings_tab(course: course_service.Course) -> None:
    frame = course_service.meetings_frame(course)
    st.dataframe(
        frame.drop(columns=["session_id"]),
        hide_index=True,
        width="stretch",
        column_config={
            "no": st.column_config.NumberColumn("#", width="small"),
            "date": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
            "day": "Loron",
            "time": "Oras",
            "status": "Status",
            "attended": "Tama",
            "late": "Atrazu",
        },
    )
    meetings = [m for m in course_service.meetings(course.id) if not m.is_cancelled]
    labels = {m.id: f"#{i} · {m.session_date:%a %d %b %Y}" for i, m in enumerate(course_service.meetings(course.id), 1)}

    c1, c2 = st.columns(2)
    with c1.form(f"cmanual_{course.id}", clear_on_submit=True):
        ui.card_title("Aumenta estudante ho liman")
        meeting_id = st.selectbox("Enkontru", [m.id for m in meetings], format_func=labels.get, key=f"cm_meet_{course.id}")
        nim = st.text_input("NIM", key=f"cm_nim_{course.id}")
        status = st.radio("Status", ["Present", "Late"], format_func=theme.status_text, horizontal=True, index=settings_service.STATUSES.index(settings_service.get("default_status")), key=f"cm_status_{course.id}")
        if st.form_submit_button("Aumenta ba enkontru"):
            meeting = next(m for m in meetings if m.id == meeting_id)
            outcome = attendance_service.check_in(meeting, nim, admin_override=True, status=status)
            if outcome.result is CheckInResult.SUCCESS:
                st.toast(f"{outcome.student['name']} aumenta ona ({theme.status_text(outcome.record['status'])})", icon="✅")
            elif outcome.result is CheckInResult.NOT_FOUND:
                st.error("NIM la hetan iha lista estudante.")
            else:
                st.warning(outcome.message)
    with c2.form(f"ccancel_{course.id}"):
        ui.card_title("Kansela enkontru (ez. feriadu)")
        future = [m for m in meetings if m.state() in ("upcoming", "open")]
        cancel_id = st.selectbox(
            "Enkontru", [m.id for m in future], format_func=labels.get, key=f"cc_meet_{course.id}",
            placeholder="La iha enkontru tuir mai",
        )
        st.caption("Enkontru kansela la konta iha nota prezensa. La bele fila fali.")
        if st.form_submit_button("Kansela enkontru") and cancel_id:
            class_service.cancel_session(cancel_id)
            st.toast("Enkontru kansela ona", icon="🗓️")
            st.rerun()


def _log_tab(course: course_service.Course) -> None:
    log = course_service.course_attendance(course)
    if log.empty:
        st.caption("Seidauk iha check-in.")
        return
    log = log.assign(source=log["added_by_admin"].map({1: "Admin"}).fillna("Estudante")).drop(columns=["added_by_admin"])
    st.dataframe(
        log,
        hide_index=True,
        width="stretch",
        column_config={
            "nim": "NIM",
            "name": "Naran",
            "department": "Dep.",
            "meeting_date": st.column_config.DateColumn("Data enkontru", format="ddd DD/MM/YYYY"),
            "start_time": "Klase hahú",
            "checked_in_at": st.column_config.DatetimeColumn("Check-in iha", format="DD/MM/YYYY HH:mm:ss"),
            "status": "Status",
            "source": "Aumenta husi",
        },
    )
    st.download_button(
        "Download log check-in (CSV)",
        log.to_csv(index=False).encode("utf-8"),
        file_name=f"checkins_{course.course_name}_{course.class_name}.csv",
        mime="text/csv",
        key=f"clog_{course.id}",
    )


def render_courses() -> None:
    _create_form()
    courses = course_service.list_courses()
    if not courses:
        st.info("Seidauk iha kursu semestre. Kria dahuluk iha leten.")
        return
    ui.section_title("Kursu semestre", f"{len(courses)} course(s)")
    open_id = st.session_state.get("open_course_id")
    for course in courses:
        meetings = course_service.meetings(course.id)
        held = len(course_service.held_meetings(course))
        status = "ATIVU" if course.is_active else "HAPARA"
        label = (
            f"📘 {course.title} · {course.schedule_text} · enkontru {held}/{len(meetings)} · "
            f"kódigu {course.token} · {status}"
        )
        with st.expander(label, expanded=course.id == open_id):
            _overview(course)
            grade, meet, log = st.tabs(["📊 Nota prezensa", "🗓️ Enkontru", "🕒 Log check-in (data & oras)"])
            with grade:
                _grade_tab(course)
            with meet:
                _meetings_tab(course)
            with log:
                _log_tab(course)
