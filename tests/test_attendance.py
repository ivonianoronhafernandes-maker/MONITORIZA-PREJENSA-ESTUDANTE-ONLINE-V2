"""Smoke tests. Run with:  python -m pytest tests  (or  python tests/test_attendance.py)"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import time, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["DATABASE_PATH"] = str(Path(tempfile.mkdtemp()) / "test.db")
os.environ["STUDENT_CSV"] = str(ROOT / "tests" / "fixtures" / "student_sample.csv")  # the real student.csv starts empty
os.environ["ADMIN_PASSWORD"] = "secret"
os.environ["DEVICE_CHECK"] = "0"  # AppTest has no browser cookies; the device rule is tested at service level
os.environ["KAFKA_ENABLED"] = "0"  # events stay in the outbox; no broker needed
os.environ["AUTO_START_PIPELINE"] = "0"  # tests must not start Docker containers
os.environ["SPARK_OUTPUT_DIR"] = str(Path(tempfile.mkdtemp()) / "spark")

import json  # noqa: E402

from streamlit.testing.v1 import AppTest  # noqa: E402

from src.core.config import now_local  # noqa: E402
from src.data import database as db  # noqa: E402
from src.data.student_repository import find_student, load_students  # noqa: E402
from src.services import analytics_service, attendance_service, auth_service, class_service, spark_analytics  # noqa: E402
from src.services.attendance_service import CheckInResult, check_in  # noqa: E402
from src.streaming import outbox  # noqa: E402
from src.streaming.backfill import backfill_outbox  # noqa: E402


def _open_session(**kw):
    """A class that is open right now, whatever the time of day (sessions cannot cross midnight)."""
    now = now_local()
    start = now - timedelta(minutes=30)
    end = now + timedelta(minutes=60)
    return class_service.create_session(
        course_name="Big Data", class_name="CS-A", lecturer="Lect", room="Lab 1",
        session_date=now.date(),
        start_time=start.time() if start.date() == now.date() else time(0, 0),
        end_time=end.time() if end.date() == now.date() else time(23, 59),
        late_after_minutes=0,  # any check-in after the start counts as Late
        **kw,
    )


def test_students_clean():
    df = load_students()
    assert df["nim"].is_unique
    assert set(df["gender"]) <= {"Male", "Female"}
    assert "Business and Management" in set(df["faculty"])
    assert find_student(" 2401020110102 ")["name"] == "Dulce De Jesus Sarmento"


def test_checkin_flow():
    s = _open_session()
    ok = check_in(s, "2401020110102")
    assert ok.result is CheckInResult.SUCCESS and ok.record["status"] == "Late"  # late_after_minutes=0
    assert check_in(s, "2401020110102").result is CheckInResult.DUPLICATE
    assert check_in(s, "999").result is CheckInResult.NOT_FOUND
    assert check_in(s, "999").message == "Confirm your NIM"

    restricted = _open_session(departments=["ACC"])
    assert check_in(restricted, "2401020110102").result is CheckInResult.NOT_ALLOWED
    class_service.set_active(restricted.id, False)
    assert check_in(class_service.get_session(restricted.id), "2403070110002").result is CheckInResult.CLOSED
    forced = check_in(class_service.get_session(restricted.id), "2403070110002", admin_override=True)
    assert forced.ok and forced.record["added_by_admin"] == 1

    assert len(analytics_service.absent_students(s)) == len(load_students()) - 1


def test_checkin_opens_before_start():
    from src.core.config import settings

    now = now_local().replace(second=0, microsecond=0)
    early = settings.checkin_early_minutes
    if now.hour >= 22:  # sessions cannot cross midnight; skip the late-night edge
        return
    soon = class_service.create_session(
        course_name="Soon", class_name="S", lecturer="", room="", session_date=now.date(),
        start_time=(now + timedelta(minutes=early - 5)).time(), end_time=(now + timedelta(minutes=90)).time(),
    )
    later = class_service.create_session(
        course_name="Later", class_name="L", lecturer="", room="", session_date=now.date(),
        start_time=(now + timedelta(minutes=early + 10)).time(), end_time=(now + timedelta(minutes=90)).time(),
    )
    assert soon.state() == "open"  # starts in (early - 5) minutes: students may already check in
    ok = check_in(soon, "2401020110072")
    assert ok.ok and ok.record["status"] == "Present"
    assert later.state() == "upcoming"
    assert check_in(later, "2401020110072").result is CheckInResult.CLOSED


def test_semester_course():
    from datetime import date, datetime

    from src.services import course_service

    # Monday + Wednesday from Mon 6 Oct 2025 to Wed 29 Oct 2025 -> 8 meetings
    dates = course_service.meeting_dates(date(2025, 10, 6), date(2025, 10, 29), [0, 2])
    assert len(dates) == 8 and all(d.weekday() in (0, 2) for d in dates)

    today = now_local().date()
    course = course_service.create_course(
        course_name="Data Mining", class_name="CS-SEM", lecturer="L", room="R",
        weekdays=[today.weekday(), (today.weekday() + 2) % 7],
        start_time=time(8, 30), end_time=time(10, 30),
        start_date=today - timedelta(days=14), end_date=today + timedelta(days=14),
        late_after_minutes=15, departments=["ACC"],
    )
    meetings = course_service.meetings(course.id)
    assert len(meetings) == len(course_service.meeting_dates(course.start_date, course.end_date, course.weekdays))
    assert all(m.course_id == course.id and m.enforce_schedule for m in meetings)
    assert course.link.endswith("?class=" + course.token)

    # One permanent link: during the meeting it resolves to today's meeting, before it too,
    # and on a day without class to the next meeting.
    during = datetime.combine(today, time(9, 0))
    current = course_service.current_meeting(course, during)
    assert current.session_date == today and current.state(during) == "open"
    evening = datetime.combine(today, time(20, 0))
    assert course_service.current_meeting(course, evening).session_date == today  # still today's (ended)
    past = [m for m in meetings if m.session_date < today]
    day_after_past = datetime.combine(past[0].session_date + timedelta(days=1), time(12, 0))
    nxt = course_service.current_meeting(course, day_after_past)
    assert nxt.session_date > past[0].session_date

    # Check-ins at exact times -> grade report
    first, second = past[0], past[1]
    acc = load_students()[load_students()["department"] == "ACC"]["nim"].tolist()
    for m, nim in ((first, acc[0]), (second, acc[0])):  # added afterwards by the admin as Present
        assert check_in(m, nim, admin_override=True, status="Present").record["status"] == "Present"
    assert check_in(first, acc[1], admin_override=True).record["status"] == "Late"  # default: by the clock
    cancelled = len(past) > 2
    if cancelled:  # a holiday is not counted in the grade
        class_service.cancel_session(past[2].id)
    report, held = course_service.attendance_report(course, during)
    expected_held = len([m for m in meetings if m.starts_at <= during]) - int(cancelled)
    assert held == expected_held
    row = report.set_index("nim").loc[acc[0]]
    assert row["attended"] == 2 and row["on_time"] == 2 and row["absent"] == held - 2
    assert abs(row["attendance_pct"] - 2 / held) < 1e-9
    assert set(report["nim"]) == set(acc)  # only enrolled (ACC) students
    log = course_service.course_attendance(course)
    assert len(log) == 3 and log["checked_in_at"].str.len().min() == 19  # full date + time recorded

    # Pause stops check-in; the student page resolves the course token
    course_service.set_active(course.id, False)
    assert course_service.current_meeting(course, during).state(during) == "closed"
    page = AppTest.from_file(str(ROOT / "App.py"), default_timeout=30)
    page.query_params["class"] = course.token
    page.run()
    assert not page.exception, page.exception
    assert any(("Enkontru" in m.value or "Meeting" in m.value) for m in page.markdown)

    course_service.delete_course(course.id)
    assert course_service.meetings(course.id) == [] and course_service.get_course(course.id) is None


def test_events_go_to_outbox():
    s = _open_session(departments=["ACC"])
    ok = check_in(s, "2403070110062", device_id="p9", ip_address="10.1.1.1")
    check_in(s, "404", device_id="p9", ip_address="10.1.1.1")
    attendance_service.delete_record(ok.record["id"])

    rows = db.fetch_df("SELECT event_id, event_type, payload FROM event_outbox").set_index("event_id")
    session_evt = json.loads(rows.loc[f"ses-{s.id}", "payload"])
    assert session_evt["expected_by_department"] == {"ACC": session_evt["expected_total"]} and session_evt["expected_total"] > 0
    recorded = json.loads(rows.loc[f"att-{ok.record['id']}", "payload"])
    assert recorded["event_type"] == "attendance.recorded" and recorded["device_id"] == "p9"
    assert recorded["ip_address"] == "10.1.1.1" and recorded["class_title"] == s.title
    assert f"att-del-{ok.record['id']}" in rows.index
    attempts = [json.loads(p) for p in rows[rows["event_type"] == "attendance.checkin_attempted"]["payload"]]
    assert {"success", "not_found"} <= {a["result"] for a in attempts if a["session_id"] == s.id}

    # Re-storing (backfill / replay) never duplicates an event
    before = outbox.stats()["total"]
    backfill_outbox()
    backfill_outbox()
    assert outbox.stats()["total"] == before
    assert outbox.reset_published() == before and outbox.stats()["pending"] == before


def test_spark_snapshot_reader():
    from src.core.config import settings

    out = Path(settings.spark_output_dir)
    assert spark_analytics.load_snapshot() is None or out.exists()
    status = spark_analytics.spark_status()
    assert "online" in status


def test_one_device_one_student():
    s = _open_session()
    first = check_in(s, "2401020110059", device_id="phone-1", ip_address="192.168.1.50")
    assert first.ok and first.record["device_id"] == "phone-1"
    # Same phone, different NIM -> blocked (proxy attendance)
    assert check_in(s, "2401020110093", device_id="phone-1").result is CheckInResult.DEVICE_USED
    # Same phone, same NIM -> "already checked in", not a proxy warning
    assert check_in(s, "2401020110059", device_id="phone-1").result is CheckInResult.DUPLICATE
    # Another phone works, and the same phone is fine in a different class
    assert check_in(s, "2401020110093", device_id="phone-2").ok
    assert check_in(_open_session(), "2401020110093", device_id="phone-1").ok
    # Admin can still add the blocked student manually
    assert check_in(s, "2401020110016", device_id="phone-1", admin_override=True).ok


def test_admin_accounts():
    auth_service.ensure_default_admin()
    row = db.fetch_one("SELECT password_hash FROM admins WHERE username = 'admin'")
    assert row["password_hash"].startswith("pbkdf2_sha256$") and "secret" not in row["password_hash"]
    assert auth_service.verify_password("secret", row["password_hash"])
    assert not auth_service.verify_password("wrong", row["password_hash"])

    auth_service.create_admin("dosen1", "password123")
    try:
        auth_service.create_admin("dosen2", "short")
        raise AssertionError("short password accepted")
    except ValueError:
        pass
    auth_service.change_password("dosen1", "password123", "newpassword1")
    stored = db.fetch_one("SELECT password_hash FROM admins WHERE username = 'dosen1'")["password_hash"]
    assert auth_service.verify_password("newpassword1", stored)
    auth_service.delete_admin("dosen1", current_user="admin")
    assert all(a["username"] != "dosen1" for a in auth_service.list_admins())


def test_pages_render():
    s = _open_session()
    student = AppTest.from_file(str(ROOT / "App.py"), default_timeout=30)
    student.query_params["class"] = s.token
    student.run()
    assert not student.exception
    student.text_input[0].input("2403070110184")
    student.button[0].click().run()
    assert not student.exception
    assert any(("Susesu" in m.value or "Success" in m.value) for m in student.markdown)

    student.text_input[0].input("0000")
    student.button[0].click().run()
    assert any(("Konfirma ita-nia NIM" in m.value or "Confirm your NIM" in m.value) for m in student.markdown)

    admin = AppTest.from_file(str(ROOT / "App.py"), default_timeout=30)
    admin.session_state["admin_authenticated"] = True
    admin.session_state["admin_username"] = "admin"
    admin.run()
    assert not admin.exception, admin.exception


def test_admin_pages():
    s = _open_session()
    check_in(s, "2401020110041")
    auth_service.ensure_default_admin()
    pages = (
        "classes_page", "records_page", "students_page", "dashboard_page", "analytics_page", "reports_page",
        "settings_page",
    )
    for page in pages:
        script = f"import sys\nsys.path.insert(0, {str(ROOT)!r})\nfrom src.ui.admin import {page}\n{page}.render()\n"
        at = AppTest.from_string(script, default_timeout=30)
        at.session_state["admin_authenticated"] = True
        at.session_state["admin_username"] = "admin"
        at.run()
        assert not at.exception, (page, at.exception)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
