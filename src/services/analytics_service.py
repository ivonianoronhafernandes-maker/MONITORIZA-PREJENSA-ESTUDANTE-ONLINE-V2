"""Class roster helpers used by the Classes page.

Dashboard analytics are computed by Spark (see spark_jobs/ and
src/services/spark_analytics.py), not here.
"""
from __future__ import annotations

import pandas as pd

from src.data.student_repository import load_students
from src.services import attendance_service
from src.services.class_service import ClassSession


def expected_students(session: ClassSession) -> pd.DataFrame:
    students = load_students()
    if session.departments:
        students = students[students["department"].isin(session.departments)]
    return students


def absent_students(session: ClassSession) -> pd.DataFrame:
    """Students expected in the class who have not checked in yet (live from the database)."""
    expected = expected_students(session)
    present = set(attendance_service.session_attendance(session.id)["nim"])
    return expected[~expected["nim"].isin(present)][["nim", "name", "department", "cohort", "gender"]]
