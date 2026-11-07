"""Student-facing check-in page, reached through a class link ``/?class=<token>``.

Designed mobile-first: most students open it by scanning the QR code on their phone.
"""
from __future__ import annotations

import html

import streamlit as st

from src.core import browser
from src.core.config import now_local, settings
from src.services import class_service, course_service
from src.services.attendance_service import CheckInResult, check_in
from src.services import settings_service
from src.ui import components as ui
from src.ui.theme import status_text as theme_status

_RESULT_KEY = "last_checkin_outcome"


def _brand() -> None:
    st.markdown(
        f'<div class="brand-mini"><img src="/app/static/dit_logo.png" alt="DIT logo">'
        f"<div>{html.escape(settings_service.get('system_name'))}<small>Check-in estudante</small></div></div>",
        unsafe_allow_html=True,
    )


def _hero(session: class_service.ClassSession, course=None) -> None:
    chips = [
        f"📅 {session.session_date:%a, %d %b}",
        f"🕒 {session.start_time:%H:%M} – {session.end_time:%H:%M}",
    ]
    if course is not None:
        all_meetings = course_service.meetings(course.id)
        number = next((i for i, m in enumerate(all_meetings, start=1) if m.id == session.id), None)
        if number:
            chips.insert(0, f"📘 Enkontru {number} husi {len(all_meetings)}")
    if session.room:
        chips.append(f"📍 {session.room}")
    if session.departments:
        chips.append("👥 " + ", ".join(session.departments))
    chips_html = "".join(f'<span class="chip">{html.escape(c)}</span>' for c in chips)
    lecturer = f'<div class="who">👩‍🏫 {html.escape(session.lecturer)}</div>' if session.lecturer else ""
    st.markdown(
        f"""<div class="hero">
              <div class="status">{ui.state_badge(session.state())}</div>
              <div class="eyebrow">Check-in prezensa</div>
              <h2>{html.escape(session.title)}</h2>
              {lecturer}
              <div class="chips">{chips_html}</div>
            </div>""",
        unsafe_allow_html=True,
    )


def _countdown(session: class_service.ClassSession) -> None:
    if not session.enforce_schedule or session.state() != "open":
        return
    now = now_local()
    to_late = int((session.late_at - now).total_seconds())
    to_close = int((session.ends_at - now).total_seconds())
    ui.live_clock(to_late, to_close)


def _render_outcome(outcome) -> None:
    if outcome.result is CheckInResult.SUCCESS:
        status = outcome.record["status"]
        ui.result_card(
            "ok",
            "Susesu",
            f"Ita-nia prezensa rejista nu'udar {ui.badge(theme_status(status), 'badge-good' if status == 'Present' else 'badge-warn')}",
        )
        ui.student_card(outcome.student, outcome.record)
    elif outcome.result is CheckInResult.NOT_FOUND:
        ui.result_card(
            "bad",
            "Konfirma ita-nia NIM",
            "NIM ne'e la hetan iha lista estudante. Verifika no koko fali, ka kontaktu ita-nia dosente.",
        )
    elif outcome.result is CheckInResult.DUPLICATE:
        ui.result_card("warn", "Check-in ona", html.escape(outcome.message))
        ui.student_card(outcome.student, outcome.record)
    else:
        ui.result_card("bad", "La rejista", html.escape(outcome.message))
        if outcome.student:
            ui.student_card(outcome.student)


def _class_code_prompt() -> None:
    _brand()
    st.markdown(
        """<div class="empty"><h2>Bem-vindu!</h2>
           <p>Scan kódigu QR ne'ebé dosente hatudu.</p></div>""",
        unsafe_allow_html=True,
    )
    with st.form("class_code_form"):
        code = st.text_input("Kódigu klase", placeholder="ez. aB3xYz9Q")
        if st.form_submit_button("Kontinua →", type="primary", width="stretch"):
            if class_service.get_session_by_token(code) or course_service.get_course_by_token(code):
                st.query_params["class"] = code.strip()
                st.rerun()
            else:
                st.error("Kódigu klase la hetan. Verifika ho dosente.")


def render() -> None:
    ui.inject_student_css()
    token = st.query_params.get("class")
    if not token:
        _class_code_prompt()
        ui.app_footer()
        return

    session = class_service.get_session_by_token(token)
    course = None
    if session is None:  # a semester course link: pick today's (or the next) meeting
        course = course_service.get_course_by_token(token)
        session = course_service.current_meeting(course) if course else None
    if session is None:
        _brand()
        ui.result_card(
            "bad",
            "Link la válidu",
            "Link prezensa ne'e la válidu ka troka ona. Husu link foun ba ita-nia dosente.",
        )
        return

    _brand()
    _hero(session, course)

    device_id = None
    if settings.device_check:
        device_id = browser.ensure_device_id()
        if device_id is None:
            st.info(
                "Prepara check-in ba aparellu ne'e... Se mensajen ne'e kontinua, permite cookies ba sítiu ne'e "
                "iha browser no karrega fali pájina."
            )
            return

    state = session.state()
    if state != "open":
        messages = {
            "upcoming": f"Check-in loke iha {session.opens_at:%H:%M} iha {session.session_date:%d/%m/%Y}.",
            "ended": f"Check-in remata iha {session.end_time:%H:%M}.",
            "closed": "Admin taka ona link klase ne'e.",
            "cancelled": "Enkontru ne'e kansela ona.",
        }
        title = "Check-in seidauk loke"
        if course is not None and state == "upcoming":
            title = "Enkontru tuir mai"
        elif course is not None and state == "ended" and session.session_date < now_local().date():
            title, messages["ended"] = "Semestre remata ona", "Enkontru hotu iha kursu ne'e remata ona."
        ui.result_card("warn", title, html.escape(messages[state]))
    else:
        _countdown(session)

    with st.form("checkin_form", clear_on_submit=True):
        nim = st.text_input("ID Estudante (NIM)", placeholder="Hakerek ita-nia NIM iha ne'e", max_chars=40)
        submitted = st.form_submit_button("Check-in  ✓", type="primary", width="stretch", disabled=state != "open")

    if submitted:
        with st.spinner("Verifika ita-nia NIM..."):
            outcome = check_in(session, nim, device_id=device_id, ip_address=browser.client_ip())
            st.session_state[_RESULT_KEY] = (session.id, outcome)
        if outcome.ok:
            ui.celebrate()  # only on the run that recorded it, not on later reruns

    last = st.session_state.get(_RESULT_KEY)
    if last and last[0] == session.id:
        _render_outcome(last[1])

    ui.app_footer()
