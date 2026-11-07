"""The system starts empty (no students, classes or attendance) and every page-level service works that way.

Runs in a subprocess because settings are read from environment variables when the app is first imported.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCRIPT = r'''
import sys
sys.path.insert(0, ROOT)
from datetime import time, timedelta
import pandas as pd
from src.core.config import now_local
from src.data import database as db
from src.data import student_repository as repo
from src.services import (attendance_service, class_service, dashboard_views as views, import_service,
                          report_service, settings_service, stats_service)

db.init_db()

# 1. empty system
assert repo.load_students().empty
assert stats_service.lifetime_rates().empty
table = report_service.student_report("2026-01-01", "2026-12-31")
info = report_service.summary(table, 0)
assert info == {"students": 0, "present": 0, "absent": 0, "late": 0, "rate": 0.0}
assert report_service.to_pdf(table, info, "t").startswith(b"%PDF") and report_service.to_excel(table, info, "t")[:2] == b"PK"
today = now_local().date()
view, _, alerts, rng = views.select_or_empty(None, "Last 7 days", None, today.isoformat())
assert len(views.daily_counts(view)) == 7 and views.by_class(view).empty and alerts == []
assert views.status_counts(view["kpis"])["rate"] == 0.0

# 2. settings
assert settings_service.get("default_status") == "Present"
settings_service.save("My System", "2026/2027", "Late", "Tetum")
assert settings_service.get("system_name") == "My System" and settings_service.get("default_status") == "Late"

# 3. add / edit students
repo.add_student("2401", "Ana Silva", "Female", "Eng", "cs", "2024", "ana@x.com")
repo.add_student("2402", "Joao Costa", "Male", "Eng", "CS", "2024")
try:
    repo.add_student("2401", "Dup", "Male", "", "", "")
    raise SystemExit("duplicate NIM was accepted")
except ValueError:
    pass
repo.update_student("2402", "Joao C. Costa", "Male", "Eng", "CS", "2024", "joao@x.com")
students = repo.load_students()
assert list(students["class_name"]) == ["CS-2024", "CS-2024"] and "joao@x.com" in set(students["email"])

# 4. attendance, report and import
day = today - timedelta(days=1)
sess = class_service.create_session(course_name="Big Data", class_name="CS-A", lecturer="", room="", session_date=day,
    start_time=time(8, 0), end_time=time(10, 0), late_after_minutes=15, departments=[], enforce_schedule=False)
csv = pd.DataFrame({"NIM": ["2401", "2402", "9999", "2401"], "class": ["CS-A"] * 4, "subject": ["Big Data"] * 4,
                    "date": [day.isoformat()] * 4, "time": ["08:05", "", "08:10", "08:10"],
                    "status": ["Late", "Present", "Present", "Absent"]})
rep = import_service.import_frame(csv)
assert rep.imported == 2 and len(rep.skipped) == 2, rep
s, e = (today - timedelta(days=6)).isoformat(), today.isoformat()
report = report_service.student_report(s, e)
summary = report_service.summary(report, 2)
assert summary["present"] == 1 and summary["late"] == 1 and summary["absent"] == 0 and summary["rate"] == 1.0, summary
assert set(stats_service.absent_records(s, e).columns) >= {"class_name", "subject"}
print("OK")
'''


def test_empty_system_and_student_editing():
    tmp = Path(tempfile.mkdtemp())
    (tmp / "student.csv").write_text('"Cap waktu","Naran Kompletu","Nim","Sexu","Fakuldade","Departamentu","Turno","Email"\n', encoding="utf-8")
    env = {
        **os.environ, "DATABASE_PATH": str(tmp / "t.db"), "STUDENT_CSV": str(tmp / "student.csv"),
        "SPARK_OUTPUT_DIR": str(tmp / "spark"), "KAFKA_ENABLED": "0", "AUTO_START_PIPELINE": "0",
    }
    result = subprocess.run([sys.executable, "-c", SCRIPT.replace("ROOT", repr(str(ROOT)), 1)], env=env, capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0 and "OK" in result.stdout, result.stdout + result.stderr


if __name__ == "__main__":
    test_empty_system_and_student_editing()
    print("ok test_empty_system_and_student_editing")
