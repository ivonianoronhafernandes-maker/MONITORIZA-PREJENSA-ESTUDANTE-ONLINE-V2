"""Check-in flow: validate the NIM against student.csv and record attendance."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

import pandas as pd

from src.core import events
from src.core.config import now_local
from src.data import database as db
from src.data.student_repository import find_student, normalize_nim
from src.services.class_service import ClassSession


class CheckInResult(str, Enum):
    SUCCESS = "success"
    NOT_FOUND = "not_found"
    DUPLICATE = "duplicate"
    CLOSED = "closed"
    NOT_ALLOWED = "not_allowed"
    DEVICE_USED = "device_used"
    INVALID = "invalid"


@dataclass
class CheckInOutcome:
    result: CheckInResult
    message: str
    student: dict | None = None
    record: dict | None = field(default=None)

    @property
    def ok(self) -> bool:
        return self.result is CheckInResult.SUCCESS


def attempt_event(row: dict) -> dict:
    return {
        "attempt_id": row["id"],
        "session_id": row["session_id"],
        "nim": row["nim_input"],
        "result": row["result"],
        "at": row["created_at"],
        "device_id": row.get("device_id"),
        "ip_address": row.get("ip_address"),
    }


def attendance_event(record: dict, class_title: str) -> dict:
    return {
        "attendance_id": record["id"],
        "session_id": record["session_id"],
        "class_title": class_title,
        "nim": record["nim"],
        "name": record["name"],
        "gender": record["gender"],
        "faculty": record["faculty"],
        "department": record["department"],
        "cohort": record["cohort"],
        "status": record["status"],
        "attendance_date": record["attendance_date"],
        "checked_in_at": record["checked_in_at"],
        "device_id": record.get("device_id"),
        "ip_address": record.get("ip_address"),
        "added_by_admin": int(record.get("added_by_admin") or 0),
    }


def _log_attempt(
    session: ClassSession,
    nim_input: str,
    result: CheckInResult,
    device_id: str | None = None,
    ip_address: str | None = None,
) -> None:
    row = {
        "session_id": session.id,
        "nim_input": nim_input[:64],
        "result": result.value,
        "created_at": now_local().isoformat(sep=" "),
        "device_id": device_id,
        "ip_address": ip_address,
    }
    row["id"] = db.execute(
        "INSERT INTO checkin_attempts (session_id, nim_input, result, created_at, device_id, ip_address) "
        "VALUES (:session_id, :nim_input, :result, :created_at, :device_id, :ip_address)",
        row,
    )
    events.publish(events.CHECKIN_ATTEMPTED, attempt_event(row), event_id=f"try-{row['id']}", key=str(session.id))


def _existing_record(session_id: int, nim: str) -> dict | None:
    return db.fetch_one("SELECT * FROM attendance WHERE session_id = ? AND nim = ?", (session_id, nim))


def _device_record(session_id: int, device_id: str) -> dict | None:
    return db.fetch_one(
        "SELECT * FROM attendance WHERE session_id = ? AND device_id = ? LIMIT 1", (session_id, device_id)
    )


def check_in(
    session: ClassSession,
    nim_input: str,
    *,
    device_id: str | None = None,
    ip_address: str | None = None,
    admin_override: bool = False,
    status: str | None = None,
    at: datetime | None = None,
) -> CheckInOutcome:
    """Record attendance for ``nim_input``.

    ``device_id`` identifies the student's browser: one device can check in
    only one NIM per class, which blocks checking in on behalf of friends.
    ``admin_override`` lets an admin add a student manually outside the
    schedule window or after the link was closed; with it, ``status``
    ("Present"/"Late") sets the status instead of deriving it from the clock; ``at`` (admin
    entries and imports only) sets the recorded check-in time instead of "now".
    """
    nim = normalize_nim(nim_input)
    if not nim:
        return CheckInOutcome(CheckInResult.INVALID, "Favór hatama ita-nia NIM.")

    def log(result: CheckInResult) -> None:
        _log_attempt(session, nim, result, device_id, ip_address)

    state = session.state()
    if state != "open" and not admin_override:
        messages = {
            "closed": "Admin taka ona link klase ne'e.",
            "upcoming": f"Check-in loke iha {session.opens_at:%H:%M} iha {session.session_date:%d/%m/%Y}.",
            "ended": f"Check-in ba klase ne'e remata iha {session.end_time:%H:%M}.",
            "cancelled": "Enkontru ne'e kansela ona.",
        }
        log(CheckInResult.CLOSED)
        return CheckInOutcome(CheckInResult.CLOSED, messages[state])

    student = find_student(nim)
    if student is None:
        log(CheckInResult.NOT_FOUND)
        return CheckInOutcome(CheckInResult.NOT_FOUND, "Konfirma ita-nia NIM")

    if session.departments and student["department"] not in session.departments and not admin_override:
        log(CheckInResult.NOT_ALLOWED)
        return CheckInOutcome(
            CheckInResult.NOT_ALLOWED,
            f"Klase ne'e ba estudante {', '.join(session.departments)} de'it.",
            student=student,
        )

    existing = _existing_record(session.id, nim)
    if existing:
        log(CheckInResult.DUPLICATE)
        return CheckInOutcome(
            CheckInResult.DUPLICATE,
            f"Ita check-in ona iha {existing['checked_in_at'][11:19]}.",
            student=student,
            record=existing,
        )

    if device_id and not admin_override:
        used = _device_record(session.id, device_id)
        if used:
            log(CheckInResult.DEVICE_USED)
            return CheckInOutcome(
                CheckInResult.DEVICE_USED,
                "Aparellu ne'e uza ona atu check-in estudante seluk iha klase ne'e. "
                "Estudante ida-idak tenke check-in ho nia telemovel rasik.",
            )

    now = at if (at and admin_override) else now_local()
    if admin_override and status in ("Present", "Late"):
        pass  # the admin decides, e.g. when adding a student to yesterday's meeting
    else:
        status = "Late" if session.enforce_schedule and now > session.late_at else "Present"
    try:
        db.execute(
            """
            INSERT INTO attendance (session_id, nim, name, gender, faculty, department, cohort,
                                    status, attendance_date, checked_in_at,
                                    device_id, ip_address, added_by_admin)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session.id,
                nim,
                student["name"],
                student["gender"],
                student["faculty"],
                student["department"],
                student["cohort"],
                status,
                now.date().isoformat(),
                now.isoformat(sep=" "),
                None if admin_override else device_id,
                ip_address,
                int(admin_override),
            ),
        )
    except sqlite3.IntegrityError:  # double submit race: the other request won
        existing = _existing_record(session.id, nim)
        log(CheckInResult.DUPLICATE)
        return CheckInOutcome(CheckInResult.DUPLICATE, "Ita check-in ona.", student=student, record=existing)

    record = _existing_record(session.id, nim)
    log(CheckInResult.SUCCESS)
    events.publish(
        events.ATTENDANCE_RECORDED,
        attendance_event(record, session.title),
        event_id=f"att-{record['id']}",
        key=str(session.id),
    )
    return CheckInOutcome(CheckInResult.SUCCESS, "Success", student=student, record=record)


def attendance_frame(start_date: str | None = None, end_date: str | None = None) -> pd.DataFrame:
    """Attendance joined with its class, optionally limited to a date range (inclusive)."""
    sql = """
        SELECT a.*, s.course_name, s.class_name, s.lecturer, s.room, s.token,
               s.course_name || ' - ' || s.class_name AS class_title
        FROM attendance a JOIN class_sessions s ON s.id = a.session_id
    """
    params: list = []
    if start_date and end_date:
        sql += " WHERE a.attendance_date BETWEEN ? AND ?"
        params = [start_date, end_date]
    sql += " ORDER BY a.checked_in_at DESC"
    df = db.fetch_df(sql, tuple(params))
    if not df.empty:
        df["checked_in_at"] = pd.to_datetime(df["checked_in_at"])
    return df


def attempts_frame(start_date: str, end_date: str) -> pd.DataFrame:
    df = db.fetch_df(
        "SELECT * FROM checkin_attempts WHERE substr(created_at, 1, 10) BETWEEN ? AND ? ORDER BY created_at DESC",
        (start_date, end_date),
    )
    if not df.empty:
        df["created_at"] = pd.to_datetime(df["created_at"])
    return df


def session_attendance(session_id: int) -> pd.DataFrame:
    return db.fetch_df(
        "SELECT * FROM attendance WHERE session_id = ? ORDER BY checked_in_at DESC", (session_id,)
    )


def delete_record(record_id: int) -> None:
    record = db.fetch_one("SELECT session_id FROM attendance WHERE id = ?", (record_id,))
    db.execute("DELETE FROM attendance WHERE id = ?", (record_id,))
    if record:
        events.publish(
            events.ATTENDANCE_DELETED,
            {"attendance_id": record_id, "session_id": record["session_id"]},
            event_id=f"att-del-{record_id}",
            key=str(record["session_id"]),
        )
