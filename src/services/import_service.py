"""Import attendance records from a CSV file (Attendance page > Import Data).

Expected columns (header names are case-insensitive, extra columns are ignored):

    student_id | nim   - the student's NIM (must exist in the student list)
    class              - class group of the meeting, as created under Settings > Classes
    subject            - course name of the meeting
    date               - YYYY-MM-DD (DD/MM/YYYY also works)
    time               - HH:MM (optional, defaults to the meeting's start time)
    status             - Present or Late (Absent is calculated by the system and is skipped)

Each row is added to the meeting that matches class + subject + date, exactly like an admin
adding a student by hand, so Kafka/Spark and the dashboard see it too.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from src.data import database as db
from src.services import attendance_service, class_service
from src.services.attendance_service import CheckInResult

TEMPLATE = "student_id,class,subject,date,time,status\n"
ALIASES = {"nim": "student_id", "id": "student_id", "student id": "student_id", "studentid": "student_id"}
STATUS_ALIASES = {"Prezente": "Present", "Atrazu": "Late", "Falta": "Absent"}  # Tetum labels are accepted too
REQUIRED = ["student_id", "class", "subject", "date", "status"]


@dataclass
class ImportReport:
    imported: int = 0
    skipped: list[str] = field(default_factory=list)  # one human-readable line per skipped row


def _parse_date(value: str):
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _parse_time(value: str):
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(value.strip(), fmt).time()
        except ValueError:
            continue
    return None


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=lambda c: ALIASES.get(str(c).strip().lower(), str(c).strip().lower()))
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError("Kolona la iha: " + ", ".join(missing) + ". Presiza: " + ", ".join(REQUIRED) + " (oras opsionál).")
    return df


def import_frame(raw: pd.DataFrame) -> ImportReport:
    df = normalize_columns(raw.astype(str).fillna(""))
    report = ImportReport()
    for line, row in enumerate(df.to_dict("records"), start=2):  # line 1 is the header
        label = f"Liña {line}"
        status = STATUS_ALIASES.get(row["status"].strip().title(), row["status"].strip().title())
        if status == "Absent":
            report.skipped.append(f"{label}: Falta kalkula automátiku, la presiza importa.")
            continue
        if status not in ("Present", "Late"):
            report.skipped.append(f"{label}: status tenke Prezente (Present) ka Atrazu (Late).")
            continue
        day = _parse_date(row["date"])
        if day is None:
            report.skipped.append(f"{label}: data '{row['date']}' la forma YYYY-MM-DD.")
            continue
        found = db.fetch_one(
            "SELECT id FROM class_sessions WHERE class_name = ? AND course_name = ? AND session_date = ? AND is_cancelled = 0",
            (row["class"].strip(), row["subject"].strip(), day.isoformat()),
        )
        session = class_service.get_session(found["id"]) if found else None
        if session is None:
            report.skipped.append(f"{label}: la iha enkontru ba {row['subject']} / {row['class']} iha {day:%d/%m/%Y}.")
            continue
        clock = _parse_time(row.get("time", "")) if row.get("time", "").strip() else session.start_time
        if clock is None:
            report.skipped.append(f"{label}: oras '{row['time']}' la forma HH:MM.")
            continue
        outcome = attendance_service.check_in(
            session, row["student_id"], admin_override=True, status=status, at=datetime.combine(day, clock)
        )
        if outcome.result is CheckInResult.SUCCESS:
            report.imported += 1
        elif outcome.result is CheckInResult.NOT_FOUND:
            report.skipped.append(f"{label}: estudante {row['student_id']} la iha iha lista estudante.")
        else:
            report.skipped.append(f"{label}: {outcome.message}")
    return report
