"""Create class sessions and share a unique check-in link + QR code for each."""
from __future__ import annotations

import html
from datetime import datetime, time, timedelta

import streamlit as st

from src.core.config import now_local, settings
from src.data.student_repository import list_departments
from src.services import analytics_service, attendance_service, class_service, settings_service
from src.services.attendance_service import CheckInResult
from src.ui import components as ui
from src.ui import theme
from src.ui.admin.courses_section import render_courses


def _round_down(dt: datetime, minutes: int = 5) -> time:
    """Default start = now (rounded down), so a class created now is open for check-in right away."""
    return dt.replace(minute=dt.minute - dt.minute % minutes, second=0, microsecond=0).time()


def _create_form() -> None:
    now = now_local()
    start_default = _round_down(now)
    end_dt = datetime.combine(now.date(), start_default) + timedelta(minutes=100)
    # Sessions end on the same day, so late-evening defaults stop at 23:55.
    end_default = end_dt.time() if end_dt.date() == now.date() else time(23, 55)
    if start_default >= end_default:
        start_default = time(0, 0)

    with st.form("create_class", clear_on_submit=True, border=True):
        ui.card_title("Sesaun úniku foun")
        c1, c2 = st.columns(2)
        course = c1.text_input("Naran matéria/kursu *", placeholder="ez. Big Data")
        class_name = c2.text_input("Klase / grupu *", placeholder="e.g. CS-2024-A")
        c1, c2 = st.columns(2)
        lecturer = c1.text_input("Dosente", placeholder="ez. Dr. Maria Soares")
        room = c2.text_input("Sala", placeholder="ez. Lab 2")
        c1, c2, c3, c4 = st.columns(4)
        session_date = c1.date_input("Data", value=now.date(), format="DD/MM/YYYY")
        start = c2.time_input("Hahú", value=start_default, step=300)
        end = c3.time_input("Remata", value=end_default, step=300)
        late = c4.number_input("Atrazu depois (minutu)", min_value=0, max_value=240, value=15, step=5)
        c1, c2 = st.columns([3, 1])
        departments = c1.multiselect(
            "Limita ba departamentu", list_departments(), placeholder="Departamentu hotu"
        )
        enforce = c2.checkbox(
            "Simu de'it durante oras klase",
            value=True,
            help=f"Check-in loke minutu {settings.checkin_early_minutes} molok hahú no taka iha oras remata.",
        )

        if st.form_submit_button("Kria klase & halo link", type="primary"):
            try:
                session = class_service.create_session(
                    course_name=course,
                    class_name=class_name,
                    lecturer=lecturer,
                    room=room,
                    session_date=session_date,
                    start_time=start,
                    end_time=end,
                    late_after_minutes=int(late),
                    departments=departments,
                    enforce_schedule=enforce,
                )
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.session_state["open_session_id"] = session.id
                st.success(f"Klase kria ona. Fahe link ne'e: {session.link}")


def _manual_checkin(session: class_service.ClassSession) -> None:
    with st.form(f"manual_{session.id}", clear_on_submit=True):
        c1, c2, c3 = st.columns([3, 2, 1], vertical_alignment="bottom")
        nim = c1.text_input("Aumenta estudante ho liman (NIM)", key=f"manual_nim_{session.id}")
        status = c2.radio("Status", ["Present", "Late"], format_func=theme.status_text, horizontal=True, index=settings_service.STATUSES.index(settings_service.get("default_status")), key=f"manual_status_{session.id}")
        if c3.form_submit_button("Aumenta", width="stretch"):
            outcome = attendance_service.check_in(session, nim, admin_override=True, status=status)
            if outcome.result is CheckInResult.SUCCESS:
                st.toast(f"{outcome.student['name']} aumenta ona ({theme.status_text(outcome.record['status'])})", icon="✅")
            elif outcome.result is CheckInResult.NOT_FOUND:
                st.error("Konfirma NIM - la hetan iha lista estudante.")
            else:
                st.warning(outcome.message)


def _session_detail(session: class_service.ClassSession) -> None:
    link_col, qr_col = st.columns([3, 1])
    with link_col:
        ui.card_title("Kódigu klase & link check-in")
        st.markdown(
            f'<div class="class-code"><span>Kódigu klase</span><b>{session.token}</b>'
            f"<small>Link ka QR de'it mak estudante uza atu halo check-in.</small></div>",
            unsafe_allow_html=True,
        )
        st.code(session.link, language=None)
        st.markdown(
            ui.meta_grid(
                {
                    "Dosente": session.lecturer or "-",
                    "Sala": session.room or "-",
                    "Oras": f"{session.start_time:%H:%M} - {session.end_time:%H:%M}",
                    "Atrazu depois": f"{session.late_at:%H:%M}" if session.enforce_schedule else "La iha limite oras",
                    "Departamentu": ", ".join(session.departments) or "Hotu",
                }
            ),
            unsafe_allow_html=True,
        )
        st.write("")
        b1, b2, b3, b4 = st.columns(4)
        if session.is_active:
            if b1.button("Taka link", key=f"close_{session.id}", width="stretch"):
                class_service.set_active(session.id, False)
                st.rerun()
        elif b1.button("Loke fali link", key=f"open_{session.id}", width="stretch"):
            class_service.set_active(session.id, True)
            st.rerun()
        if b2.button("Link foun", key=f"regen_{session.id}", width="stretch", help="Link tuan la servisu tan"):
            class_service.regenerate_token(session.id)
            st.rerun()
        b3.link_button("Loke pájina", session.link, width="stretch")
        with b4.popover("Hamoos", width="stretch"):
            st.warning("Hamoos klase ne'e no rejistu prezensa hotu.")
            if st.button("Konfirma hamoos", key=f"del_{session.id}", type="primary"):
                class_service.delete_session(session.id)
                st.rerun()
    with qr_col:
        png = ui.qr_png(session.link)
        st.image(png, caption="Scan atu check-in", width="stretch")
        st.download_button(
            "Download QR", png, file_name=f"qr_{session.token}.png", mime="image/png",
            key=f"qr_{session.id}", width="stretch",
        )

    _manual_checkin(session)

    present = attendance_service.session_attendance(session.id)
    absent = analytics_service.absent_students(session)
    tab_present, tab_absent = st.tabs([f"Prezente ({len(present)})", f"Seidauk check-in ({len(absent)})"])
    with tab_present:
        if present.empty:
            st.caption("Seidauk iha check-in.")
        else:
            view = present[["checked_in_at", "nim", "name", "department", "cohort", "gender", "status"]]
            st.dataframe(view, hide_index=True, width="stretch")
            st.download_button(
                "Download CSV", view.to_csv(index=False).encode("utf-8"),
                file_name=f"attendance_{session.session_date}_{session.class_name}.csv",
                mime="text/csv", key=f"csv_{session.id}",
            )
    with tab_absent:
        st.dataframe(absent, hide_index=True, width="stretch")


def _session_list() -> None:
    sessions = class_service.list_single_sessions()
    if not sessions:
        st.info("Seidauk iha sesaun úniku. Kria ida iha leten.")
        return

    f1, f2 = st.columns([2, 1])
    query = f1.text_input("Buka klase", placeholder="Kursu, klase, dosente...").strip().lower()
    state_filter = f2.multiselect("Status", ["open", "upcoming", "ended", "closed"], format_func=lambda x: ui.STATE_BADGES[x][0])

    counts = class_service.sessions_frame().set_index("id")["attendees"].to_dict()
    open_id = st.session_state.get("open_session_id")
    shown = 0
    for s in sessions:
        haystack = f"{s.course_name} {s.class_name} {s.lecturer} {s.room}".lower()
        if query and query not in haystack:
            continue
        state = s.state()
        if state_filter and state not in state_filter:
            continue
        shown += 1
        label = (
            f"{s.session_date:%d %b %Y} · {s.start_time:%H:%M} — {s.title} · "
            f"{counts.get(s.id, 0)} prezente · kódigu {s.token} · {ui.STATE_BADGES.get(state, (state,))[0].upper()}"
        )
        with st.expander(label, expanded=s.id == open_id):
            st.markdown(ui.state_badge(state), unsafe_allow_html=True)
            _session_detail(s)
    if not shown:
        st.caption("La iha klase ne'ebé kompatível ho filtru.")


def render() -> None:
    ui.inject_css()
    ui.page_header("Klase & Link", "Orariu semestre no sesaun úniku, ida-idak ho QR rasik", "🔗")
    render_body()


def render_body() -> None:
    """Everything except the page header, so it can also live in Settings > Classes."""
    st.caption(
        f"Links point to `{html.escape(settings.public_base_url)}`. Telemovel estudante tenke iha Wi-Fi hanesan ho komputadór ne'e "
        "(define PUBLIC_BASE_URL atu uza domíniu públiku)."
    )
    semester, single = st.tabs(["📅 Kursu semestre", "🔗 Sesaun úniku"])
    with semester:
        render_courses()
    with single:
        st.caption("Ba enkontru ida de'it, ez. klase kompensasaun ka seminár.")
        _create_form()
        _session_list()
