"""Attendance statistics computed from the SQLite tables.

Used by the pages that list people and records (Students, Attendance, Reports and the
"Top 5 students" table). The headline dashboard numbers still come from Spark.

"Absent" is not stored anywhere: a student is absent from a meeting that already started when
the meeting applies to their department and they have no check-in for it.
"""
from __future__ import annotations

import pandas as pd

from src.core.config import now_local
from src.data import database as db
from src.data.student_repository import load_students


def _dept_list(value: str | None) -> list[str]:
    return [d.strip() for d in (value or "").split(",") if d.strip()]


def sessions_held(
    start: str, end: str, class_title: str | None = None, session_id: int | None = None,
    class_name: str | None = None, subject: str | None = None,
) -> pd.DataFrame:
    """Meetings in [start, end] that already started and were not cancelled.

    ``class_name`` / ``subject`` filter on the class group and the course (subject) of the meeting.
    """
    now = now_local()
    df = db.fetch_df(
        """
        SELECT id, course_name || ' - ' || class_name AS class_title, class_name, course_name AS subject,
               session_date, start_time, end_time, departments
        FROM class_sessions
        WHERE is_cancelled = 0 AND session_date BETWEEN ? AND ?
        ORDER BY session_date, start_time
        """,
        (start, end),
    )
    if df.empty:
        return df
    today, hhmm = now.date().isoformat(), f"{now:%H:%M}"
    started = (df["session_date"] < today) | ((df["session_date"] == today) & (df["start_time"] <= hhmm))
    df = df[started]
    if class_title:
        df = df[df["class_title"] == class_title]
    if session_id:
        df = df[df["id"] == session_id]
    if class_name:
        df = df[df["class_name"] == class_name]
    if subject:
        df = df[df["subject"] == subject]
    return df.reset_index(drop=True)


def _expected(sessions: pd.DataFrame, students: pd.DataFrame) -> pd.Series:
    by_dept = students.groupby("department").size().to_dict()
    total = len(students)

    def count(depts: str) -> int:
        wanted = _dept_list(depts)
        return sum(by_dept.get(d, 0) for d in wanted) if wanted else total

    return sessions["departments"].map(count) if not sessions.empty else pd.Series(dtype=int)


def _checkins(session_ids: list[int]) -> pd.DataFrame:
    if not session_ids:
        return pd.DataFrame(columns=["session_id", "nim", "status"])
    marks = ",".join("?" * len(session_ids))
    return db.fetch_df(f"SELECT session_id, nim, status FROM attendance WHERE session_id IN ({marks})", tuple(session_ids))


def class_summary(
    start: str, end: str, class_title: str | None = None, class_name: str | None = None, subject: str | None = None
) -> pd.DataFrame:
    """One row per meeting: expected, attended, on time, late, absent and rate."""
    sessions = sessions_held(start, end, class_title, class_name=class_name, subject=subject)
    cols = ["class_title", "class_name", "subject", "session_date", "time", "expected", "attended", "on_time", "late",
            "absent", "rate"]
    if sessions.empty:
        return pd.DataFrame(columns=cols)
    students = load_students()
    sessions = sessions.assign(expected=_expected(sessions, students).values)
    check = _checkins(sessions["id"].tolist())
    attended = check.groupby("session_id").size()
    late = check[check["status"] == "Late"].groupby("session_id").size()
    out = sessions.assign(
        attended=sessions["id"].map(attended).fillna(0).astype(int),
        late=sessions["id"].map(late).fillna(0).astype(int),
    )
    out["on_time"] = out["attended"] - out["late"]
    out["absent"] = (out["expected"] - out["attended"]).clip(lower=0)
    out["rate"] = (out["attended"] / out["expected"].where(out["expected"] > 0)).fillna(0.0)
    out["time"] = out["start_time"] + "-" + out["end_time"]
    return out[cols]


def daily_summary(start: str, end: str, class_title: str | None = None) -> pd.DataFrame:
    meetings = class_summary(start, end, class_title)
    cols = ["date", "meetings", "expected", "attended", "on_time", "late", "absent", "rate"]
    if meetings.empty:
        return pd.DataFrame(columns=cols)
    grouped = meetings.groupby("session_date").agg(
        meetings=("class_title", "size"), expected=("expected", "sum"), attended=("attended", "sum"),
        on_time=("on_time", "sum"), late=("late", "sum"), absent=("absent", "sum"),
    ).reset_index().rename(columns={"session_date": "date"})
    grouped["rate"] = (grouped["attended"] / grouped["expected"].where(grouped["expected"] > 0)).fillna(0.0)
    return grouped[cols]


def totals(start: str, end: str, class_title: str | None = None) -> dict:
    meetings = class_summary(start, end, class_title)
    expected = int(meetings["expected"].sum()) if not meetings.empty else 0
    attended = int(meetings["attended"].sum()) if not meetings.empty else 0
    late = int(meetings["late"].sum()) if not meetings.empty else 0
    return {
        "meetings": len(meetings), "expected": expected, "attended": attended, "late": late,
        "on_time": attended - late, "absent": max(expected - attended, 0),
        "rate": attended / expected if expected else 0.0,
    }


def student_rates(
    start: str, end: str, class_title: str | None = None, session_id: int | None = None,
    class_name: str | None = None, subject: str | None = None,
) -> pd.DataFrame:
    """Per student: meetings that applied to them, attended, on time, late, absent and rate."""
    students = load_students()
    sessions = sessions_held(start, end, class_title, session_id, class_name, subject)
    base = students[["nim", "name", "gender", "faculty", "department", "cohort", "email", "class_name"]].copy()
    base = base.rename(columns={"class_name": "student_class"})
    if sessions.empty:
        return base.assign(held=0, attended=0, on_time=0, late=0, absent=0, rate=0.0)

    dept_sets = [set(_dept_list(d)) for d in sessions["departments"]]
    held_by_dept = {
        dept: sum(1 for ds in dept_sets if not ds or dept in ds) for dept in students["department"].unique()
    }
    check = _checkins(sessions["id"].tolist())
    attended = check.groupby("nim").size()
    late = check[check["status"] == "Late"].groupby("nim").size()

    base["held"] = base["department"].map(held_by_dept).fillna(0).astype(int)
    base["attended"] = base["nim"].map(attended).fillna(0).astype(int)
    base["late"] = base["nim"].map(late).fillna(0).astype(int)
    base["on_time"] = base["attended"] - base["late"]
    base["absent"] = (base["held"] - base["attended"]).clip(lower=0)
    base["rate"] = (base["attended"] / base["held"].where(base["held"] > 0)).clip(upper=1.0).fillna(0.0)
    return base


def top_students(start: str, end: str, limit: int = 5, session_id: int | None = None) -> pd.DataFrame:
    rates = student_rates(start, end, session_id=session_id)
    rates = rates[rates["attended"] > 0]
    return rates.sort_values(["rate", "attended", "name"], ascending=[False, False, True]).head(limit)


def lifetime_rates() -> pd.DataFrame:
    """Rate per student over every meeting held so far (used on the Students page)."""
    return student_rates("2000-01-01", now_local().date().isoformat())


ABSENT_COLUMNS = ["session_id", "class_title", "class_name", "subject", "session_date", "nim", "name", "gender", "faculty", "department", "cohort"]


def absent_records(start: str, end: str) -> pd.DataFrame:
    """One row per (meeting, expected student) with no check-in, for meetings that already started."""
    sessions = sessions_held(start, end)
    if sessions.empty:
        return pd.DataFrame(columns=ABSENT_COLUMNS)
    students = load_students()
    check = _checkins(sessions["id"].tolist())
    present = set(zip(check["session_id"], check["nim"]))
    rows = []
    for s in sessions.itertuples():
        wanted = _dept_list(s.departments)
        pool = students[students["department"].isin(wanted)] if wanted else students
        for r in pool.itertuples():
            if (s.id, r.nim) not in present:
                rows.append((s.id, s.class_title, s.class_name, s.subject, s.session_date, r.nim, r.name, r.gender, r.faculty, r.department, r.cohort))
    return pd.DataFrame(rows, columns=ABSENT_COLUMNS)
