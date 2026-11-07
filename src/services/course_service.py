"""Semester courses: a weekly schedule that generates every meeting of the semester.

Example: Data Mining, Monday + Wednesday, 08:30-10:30, 1 Oct - 31 Jan.
Every meeting is an ordinary class session (so check-in rules, Kafka events and
Spark analytics work unchanged); check-in opens and closes by itself on each
meeting's date and time. The course token is one permanent link/QR that always
points to the current (or next) meeting.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

import pandas as pd

from src.core.config import now_local
from src.data import database as db
from src.data.student_repository import load_students
from src.services import class_service
from src.services.class_service import ClassSession

WEEKDAYS = ["Segunda", "Tersa", "Kuarta", "Kinta", "Sexta", "Sábadu", "Domingu"]
MAX_MEETINGS = 400


@dataclass
class Course:
    id: int
    token: str
    course_name: str
    class_name: str
    lecturer: str
    room: str
    weekdays: list[int]
    start_time: time
    end_time: time
    late_after_minutes: int
    departments: list[str]
    start_date: date
    end_date: date
    is_active: bool
    created_at: str

    @classmethod
    def from_row(cls, row: dict) -> "Course":
        return cls(
            id=int(row["id"]),
            token=row["token"],
            course_name=row["course_name"],
            class_name=row["class_name"],
            lecturer=row["lecturer"],
            room=row["room"],
            weekdays=[int(d) for d in str(row["weekdays"]).split(",") if d != ""],
            start_time=time.fromisoformat(row["start_time"]),
            end_time=time.fromisoformat(row["end_time"]),
            late_after_minutes=int(row["late_after_minutes"]),
            departments=[d for d in row["departments"].split(",") if d],
            start_date=date.fromisoformat(row["start_date"]),
            end_date=date.fromisoformat(row["end_date"]),
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
        )

    @property
    def title(self) -> str:
        return f"{self.course_name} - {self.class_name}"

    @property
    def link(self) -> str:
        return class_service.build_link(self.token)

    @property
    def schedule_text(self) -> str:
        days = " & ".join(WEEKDAYS[d] for d in sorted(self.weekdays))
        return f"{days} · {self.start_time:%H:%M}-{self.end_time:%H:%M}"


def meeting_dates(start: date, end: date, weekdays: list[int]) -> list[date]:
    """Every date between start and end (inclusive) that falls on one of the weekdays (Mon=0)."""
    days = set(weekdays)
    out, d = [], start
    while d <= end:
        if d.weekday() in days:
            out.append(d)
        d += timedelta(days=1)
    return out


def create_course(
    *,
    course_name: str,
    class_name: str,
    lecturer: str,
    room: str,
    weekdays: list[int],
    start_time: time,
    end_time: time,
    start_date: date,
    end_date: date,
    late_after_minutes: int = 15,
    departments: list[str] | None = None,
) -> Course:
    if not course_name.strip() or not class_name.strip():
        raise ValueError("Naran kursu no naran klase obrigatóriu.")
    if not weekdays:
        raise ValueError("Hili loron semana ida ka liu.")
    if end_time <= start_time:
        raise ValueError("Oras remata tenke depois oras hahú.")
    if end_date < start_date:
        raise ValueError("Data remata semestre tenke depois data hahú.")
    dates = meeting_dates(start_date, end_date, weekdays)
    if not dates:
        raise ValueError("La iha enkontru iha loron ne'ebé hili entre data sira ne'e.")
    if len(dates) > MAX_MEETINGS:
        raise ValueError(f"Ne'e sei kria enkontru {len(dates)}; favór hili períodu badak liu.")

    token = class_service.new_token()
    course_id = db.execute(
        """
        INSERT INTO courses (token, course_name, class_name, lecturer, room, weekdays, start_time, end_time,
                             late_after_minutes, departments, start_date, end_date, is_active, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
        """,
        (
            token,
            course_name.strip(),
            class_name.strip(),
            lecturer.strip(),
            room.strip(),
            ",".join(str(d) for d in sorted(set(weekdays))),
            start_time.strftime("%H:%M"),
            end_time.strftime("%H:%M"),
            int(late_after_minutes),
            ",".join(departments or []),
            start_date.isoformat(),
            end_date.isoformat(),
            now_local().isoformat(sep=" "),
        ),
    )
    for d in dates:
        class_service.create_session(
            course_name=course_name,
            class_name=class_name,
            lecturer=lecturer,
            room=room,
            session_date=d,
            start_time=start_time,
            end_time=end_time,
            late_after_minutes=late_after_minutes,
            departments=departments,
            enforce_schedule=True,  # opens and closes automatically at the meeting time
            course_id=course_id,
        )
    return get_course(course_id)


def get_course(course_id: int) -> Course | None:
    row = db.fetch_one("SELECT * FROM courses WHERE id = ?", (course_id,))
    return Course.from_row(row) if row else None


def get_course_by_token(token: str | None) -> Course | None:
    if not token:
        return None
    row = db.fetch_one("SELECT * FROM courses WHERE token = ?", (token.strip(),))
    return Course.from_row(row) if row else None


def list_courses() -> list[Course]:
    rows = db.fetch_df("SELECT * FROM courses ORDER BY start_date DESC, id DESC")
    return [Course.from_row(r) for r in rows.to_dict("records")]


def meetings(course_id: int) -> list[ClassSession]:
    rows = db.fetch_df(
        "SELECT * FROM class_sessions WHERE course_id = ? ORDER BY session_date, start_time", (course_id,)
    )
    return [ClassSession.from_row(r) for r in rows.to_dict("records")]


def current_meeting(course: Course, at: datetime | None = None) -> ClassSession | None:
    """The meeting a student scanning the course QR should see.

    Priority: a meeting open right now, then today's meeting, then the next one,
    then the last one (after the semester ended). Cancelled meetings are skipped.
    """
    at = at or now_local()
    active = [m for m in meetings(course.id) if not m.is_cancelled]
    if not active:
        return None
    for m in active:
        if m.state(at) == "open":
            return m
    today = [m for m in active if m.session_date == at.date()]
    if today:
        return today[0]
    upcoming = [m for m in active if m.starts_at > at]
    return upcoming[0] if upcoming else active[-1]


def set_active(course_id: int, active: bool) -> None:
    """Pause or resume the whole course (all its meetings)."""
    db.execute("UPDATE courses SET is_active = ? WHERE id = ?", (int(active), course_id))
    db.execute(
        "UPDATE class_sessions SET is_active = ? WHERE course_id = ? AND is_cancelled = 0",
        (int(active), course_id),
    )


def regenerate_token(course_id: int) -> str:
    token = class_service.new_token()
    db.execute("UPDATE courses SET token = ? WHERE id = ?", (token, course_id))
    return token


def delete_course(course_id: int) -> None:
    for m in meetings(course_id):
        class_service.delete_session(m.id)  # publishes a delete event per meeting for Spark
    db.execute("DELETE FROM courses WHERE id = ?", (course_id,))


# ---- attendance grade report ------------------------------------------------------------------

def held_meetings(course: Course, at: datetime | None = None) -> list[ClassSession]:
    """Meetings that already took place (started) and were not cancelled."""
    at = at or now_local()
    return [m for m in meetings(course.id) if not m.is_cancelled and m.starts_at <= at]


def enrolled_students(course: Course) -> pd.DataFrame:
    students = load_students()
    if course.departments:
        students = students[students["department"].isin(course.departments)]
    return students[["nim", "name", "department", "cohort"]]


def course_attendance(course: Course) -> pd.DataFrame:
    """Every check-in of the course with the meeting date and exact check-in time."""
    return db.fetch_df(
        """
        SELECT a.nim, a.name, a.department, s.session_date AS meeting_date, s.start_time,
               a.checked_in_at, a.status, a.added_by_admin
        FROM attendance a JOIN class_sessions s ON s.id = a.session_id
        WHERE s.course_id = ? AND s.is_cancelled = 0
        ORDER BY s.session_date, a.checked_in_at
        """,
        (course.id,),
    )


def attendance_report(course: Course, at: datetime | None = None) -> tuple[pd.DataFrame, int]:
    """Per-student attendance score over the meetings held so far.

    Returns (report, meetings_held). Late counts as attended (and is shown separately).
    """
    held = held_meetings(course, at)
    held_ids = {m.id for m in held}
    students = enrolled_students(course).copy()
    att = db.fetch_df(
        f"""
        SELECT nim, session_id, status FROM attendance
        WHERE session_id IN ({",".join("?" * len(held_ids)) or "NULL"})
        """,
        tuple(held_ids),
    )
    present = att[att["status"] == "Present"].groupby("nim").size() if not att.empty else pd.Series(dtype=int)
    late = att[att["status"] == "Late"].groupby("nim").size() if not att.empty else pd.Series(dtype=int)

    students["on_time"] = students["nim"].map(present).fillna(0).astype(int)
    students["late"] = students["nim"].map(late).fillna(0).astype(int)
    students["attended"] = students["on_time"] + students["late"]
    students["absent"] = (len(held) - students["attended"]).clip(lower=0)
    students["attendance_pct"] = students["attended"] / len(held) if held else 0.0
    report = students.sort_values(["attendance_pct", "name"], ascending=[False, True]).reset_index(drop=True)
    return report, len(held)


def meetings_frame(course: Course, at: datetime | None = None) -> pd.DataFrame:
    """One row per meeting: date, day, status and how many attended."""
    at = at or now_local()
    counts = db.fetch_df(
        """
        SELECT session_id, COUNT(*) AS attended, SUM(CASE WHEN status = 'Late' THEN 1 ELSE 0 END) AS late
        FROM attendance WHERE session_id IN (SELECT id FROM class_sessions WHERE course_id = ?)
        GROUP BY session_id
        """,
        (course.id,),
    ).set_index("session_id")
    rows = []
    for n, m in enumerate(meetings(course.id), start=1):
        rows.append(
            {
                "session_id": m.id,
                "no": n,
                "date": m.session_date,
                "day": WEEKDAYS[m.session_date.weekday()],
                "time": f"{m.start_time:%H:%M}-{m.end_time:%H:%M}",
                "status": m.state(at).title(),
                "attended": int(counts["attended"].get(m.id, 0)) if not counts.empty else 0,
                "late": int(counts["late"].get(m.id, 0) or 0) if not counts.empty else 0,
            }
        )
    return pd.DataFrame(rows)
