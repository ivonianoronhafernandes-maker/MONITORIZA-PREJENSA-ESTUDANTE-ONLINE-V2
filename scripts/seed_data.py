"""Generate SIMULATED attendance data so the system reaches 10,000+ records (capstone volume test).

    python scripts/seed_data.py                 # add courses, class sessions and attendance (default >= 12,000 records)
    python scripts/seed_data.py --target 20000  # more records (always at least 7 days)
    python scripts/seed_data.py --reset         # first wipe courses / sessions / attendance (database is backed up)

The records are SIMULATED (random but realistic: ~88% attend, ~10% of those are late). Students come from
data/raw/student.csv. When real attendance exists, run with --reset-only to clear the simulation.
"""
from __future__ import annotations

import argparse
import random
import secrets
import shutil
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from flask_app import data  # noqa: E402
from src.core.config import now_local, settings  # noqa: E402
from src.data.database import init_db  # noqa: E402

COURSES = [  # (matéria, departamentu, lektor, sala, oras)
    ("Inteligência Artificial", "CIÊNCIAS DOS COMPUTADORES", "Carlos Soares", "Sala A1", "08:15"),
    ("Base de Dadus", "CIÊNCIAS DOS COMPUTADORES", "Maria Gusmão", "Sala A2", "10:15"),
    ("Big Data", "CIÊNCIAS DOS COMPUTADORES", "Ana Belo", "Lab 1", "13:30"),
    ("Kontabilidade Finanseira", "CONTABILIDADE", "Joaquim Pereira", "Sala B1", "08:15"),
    ("Auditoria", "CONTABILIDADE", "Lucia Fernandes", "Sala B2", "10:15"),
    ("Jestaun Finansas", "GESTÃO DE FINANÇAS", "Pedro Martins", "Sala C1", "08:15"),
    ("Merkadu Kapitál", "GESTÃO DE FINANÇAS", "Rosa Lima", "Sala C2", "10:15"),
    ("Mekánika Solu", "ENGENHARIA CIVIL", "Domingos Ramos", "Sala D1", "13:30"),
    ("Estrutura Konkretu", "ENGENHARIA CIVIL", "Beatriz Costa", "Sala D2", "08:15"),
    ("Termodinámika", "ENGENHARIA MECÂNICA", "Tomás Alves", "Sala E1", "10:15"),
    ("Turizmu Sustentável", "GESTÃO TOUR & TRAVEL", "Elsa Ximenes", "Sala F1", "13:30"),
    ("Jeolojia Petróleu", "ENGENHARIA PETROLÍFERA", "Nelson Araújo", "Sala G1", "08:15"),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=12000)
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--reset-only", action="store_true")
    ap.add_argument("--seed", type=int, default=2026)
    a = ap.parse_args()
    random.seed(a.seed)

    db = Path(settings.database_path)
    init_db(db)
    if (a.reset or a.reset_only) and db.stat().st_size:
        shutil.copy(db, db.with_name(f"attendance_backup_{datetime.now():%Y%m%d_%H%M%S}.db"))
    con = sqlite3.connect(db)
    con.execute("PRAGMA foreign_keys = ON")
    if a.reset or a.reset_only:
        for t in ("attendance", "checkin_attempts", "class_sessions", "courses", "event_outbox"):
            con.execute(f"DELETE FROM {t}")
        con.commit()
        print("Simulation wiped.")
        if a.reset_only:
            return

    st = data.students()
    if st.empty:
        sys.exit("data/raw/student.csv has no students.")
    depts = set(st["department"])
    today = now_local().date()
    created = now_local().strftime("%Y-%m-%d %H:%M:%S")
    last_day = today if today.weekday() != 6 else today - timedelta(days=1)  # no class on Sunday
    days = []
    d = last_day
    while len(days) < 30:  # newest day first; we stop as soon as the target is reached
        if d.weekday() != 6:
            days.append(d)
        d -= timedelta(days=1)

    # one permanent course row per matéria
    course_ids = {}
    for name, dept, lect, room, start in COURSES:
        if dept not in depts:
            continue
        h, m = map(int, start.split(":"))
        end = f"{h + 2:02d}:{m:02d}"
        cur = con.execute(
            "INSERT INTO courses (token, course_name, class_name, lecturer, room, weekdays, start_time, end_time,"
            " late_after_minutes, departments, start_date, end_date, is_active, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1,?)",
            (secrets.token_urlsafe(8), name, dept.title(), lect, room, "0,1,2,3,4,5", start, end, 15, dept,
             (last_day - timedelta(days=30)).isoformat(), (last_day + timedelta(days=90)).isoformat(), created))
        course_ids[name] = (cur.lastrowid, dept, lect, room, start, end)
    con.commit()

    total, used_days = 0, 0
    by_dept = {k: v for k, v in st.groupby("department")}
    order = list(course_ids.items())
    for day in days:  # newest -> oldest; at least 7 days (the dashboard trend), then until the target is reached
        if total >= a.target and used_days >= 7:
            break
        used_days += 1
        for k in range(2):  # two classes per day, rotating through the matéria
            name, (cid, dept, lect, room, start, end) = order[(day.toordinal() * 2 + k) % len(order)]
            sid = con.execute(
                "INSERT INTO class_sessions (token, course_name, class_name, lecturer, room, session_date, start_time, end_time,"
                " late_after_minutes, departments, enforce_schedule, is_active, created_at, course_id, is_cancelled)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,1,?,?,?,0)",
                (secrets.token_urlsafe(8), name, dept.title(), lect, room, day.isoformat(), start, end, 15, dept,
                 1 if day == last_day else 0, created, cid)).lastrowid
            chosen = by_dept[dept].sample(frac=random.uniform(0.80, 0.93), random_state=random.randint(0, 10**6))
            sh, sm = map(int, start.split(":"))
            t0 = datetime(day.year, day.month, day.day, sh, sm)
            batch = []
            for r in chosen.itertuples():
                late = random.random() < 0.10
                when = t0 + timedelta(minutes=random.randint(16, 40) if late else random.randint(-12, 14), seconds=random.randint(0, 59))
                batch.append((sid, r.nim, r.name, "Male" if r.gender == "Mane" else "Female", r.faculty, r.department, r.cohort,
                              "Late" if late else "Present", day.isoformat(), when.strftime("%Y-%m-%d %H:%M:%S"),
                              f"sim-{secrets.token_hex(6)}", f"10.0.{random.randint(0, 20)}.{random.randint(2, 250)}"))
            con.executemany(
                "INSERT INTO attendance (session_id, nim, name, gender, faculty, department, cohort, status, attendance_date,"
                " checked_in_at, device_id, ip_address, added_by_admin) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0)", batch)
            total += len(batch)
    con.commit()
    n = con.execute("SELECT COUNT(*) FROM attendance").fetchone()[0]
    print(f"Added {total:,} simulated attendance records ({n:,} in the database).")
    if n < a.target:
        print(f"Below target {a.target:,}: run again with --reset --target {a.target} after raising the number of days.")
    con.close()


if __name__ == "__main__":
    main()
