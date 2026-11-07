"""Loads and cleans the student master data from ``student.csv``.

The raw file comes from a Google Form (Tetum headers), so it contains
duplicate submissions, typos and inconsistent casing. Everything is
normalised here once, and the rest of the app only sees clean columns:

    nim, name, gender, faculty, department, cohort, email, class_name, registered_at

The file may be empty (header only): the system then simply shows no students until
they are added on the Students page ("Add Student") or pasted into the CSV.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import streamlit as st

from src.core.config import now_local, settings

RAW_TO_CLEAN = {
    "Cap waktu": "registered_at",
    "Naran Kompletu": "name",
    "Nim": "nim",
    "Sexu": "gender",
    "Fakuldade": "faculty",
    "Departamentu": "department",
    "Turno": "cohort",
}

RAW_COLUMNS = list(RAW_TO_CLEAN) + ["Email"]
GENDER_MAP = {"mane": "Male", "feto": "Female", "fero": "Female", "male": "Male", "female": "Female"}
GENDER_TO_RAW = {"Male": "Mane", "Female": "Feto"}
FACULTY_FIXES = {"bunesse and management": "Business and Management"}

CLEAN_COLUMNS = ["nim", "name", "gender", "faculty", "department", "cohort", "email", "class_name", "registered_at"]


def normalize_nim(value: object) -> str:
    """Canonical NIM form used for lookups: trimmed, upper-case, no inner spaces."""
    return re.sub(r"\s+", "", str(value or "")).upper()


def _clean_name(value: str) -> str:
    name = re.sub(r"\s+", " ", str(value)).strip()
    return name.title()


def _parse_timestamp(series: pd.Series) -> pd.Series:
    cleaned = series.astype(str).str.replace(r"\s*GMT[+-]\d+$", "", regex=True)
    return pd.to_datetime(cleaned, format="%Y/%m/%d %I:%M:%S %p", errors="coerce")


def clean_students(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.rename(columns={**RAW_TO_CLEAN, "Email": "email"})
    missing = [c for c in RAW_TO_CLEAN.values() if c not in df.columns]
    if missing:
        raise ValueError(f"student.csv is missing columns: {missing}")
    if "email" not in df.columns:  # older files have no Email column
        df["email"] = ""

    df = df[[*RAW_TO_CLEAN.values(), "email"]].copy()
    df["email"] = df["email"].astype(str).str.strip()
    df["nim"] = df["nim"].map(normalize_nim)
    df = df[df["nim"] != ""]
    df["name"] = df["name"].map(_clean_name)
    df["gender"] = df["gender"].astype(str).str.strip().str.lower().map(GENDER_MAP).fillna("Unknown")
    faculty = df["faculty"].astype(str).str.strip()
    df["faculty"] = faculty.str.lower().map(FACULTY_FIXES).fillna(faculty)
    df["department"] = df["department"].astype(str).str.strip().str.upper()
    df["cohort"] = df["cohort"].astype(str).str.strip()
    df["registered_at"] = _parse_timestamp(df["registered_at"])
    # "Class" shown in the admin UI = department + cohort, e.g. CS-2024.
    df["class_name"] = (df["department"] + "-" + df["cohort"]).str.strip("-")

    # Students submitted the form more than once: keep the latest submission.
    df = (
        df.sort_values("registered_at")
        .drop_duplicates(subset="nim", keep="last")
        .sort_values("name")
        .reset_index(drop=True)
    )
    return df[CLEAN_COLUMNS]


@st.cache_data(show_spinner=False)
def _load(path: str, mtime: float) -> tuple[pd.DataFrame, int]:
    raw = pd.read_csv(path, dtype=str, keep_default_na=False)
    return clean_students(raw), len(raw)


def load_students(path: Path | None = None) -> pd.DataFrame:
    """Clean student table, cached until the CSV file changes on disk."""
    csv_path = Path(path or settings.student_csv)
    df, _ = _load(str(csv_path), csv_path.stat().st_mtime)
    return df


def raw_row_count(path: Path | None = None) -> int:
    csv_path = Path(path or settings.student_csv)
    _, count = _load(str(csv_path), csv_path.stat().st_mtime)
    return count


def find_student(nim: str) -> dict | None:
    key = normalize_nim(nim)
    if not key:
        return None
    match = load_students().loc[lambda d: d["nim"] == key]
    if match.empty:
        return None
    return match.iloc[0].to_dict()


def list_departments() -> list[str]:
    return sorted(load_students()["department"].unique().tolist())


# ---- editing (Students page: Add / Edit) --------------------------------------------------------

def _read_raw(path: Path) -> pd.DataFrame:
    if path.exists():
        raw = pd.read_csv(path, dtype=str, keep_default_na=False)
    else:
        raw = pd.DataFrame(columns=RAW_COLUMNS)
    if "Email" not in raw.columns:
        raw["Email"] = ""
    return raw


def _write_raw(path: Path, raw: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw.to_csv(path, index=False, quoting=1)  # quote everything, like the original form export
    _load.clear()


def _validate(nim: str, name: str) -> tuple[str, str]:
    nim, name = normalize_nim(nim), re.sub(r"\s+", " ", str(name or "")).strip()
    if not nim:
        raise ValueError("Student ID (NIM) is required.")
    if not name:
        raise ValueError("Name is required.")
    return nim, name


def add_student(nim: str, name: str, gender: str, faculty: str, department: str, cohort: str, email: str = "") -> None:
    """Append one student to the CSV. Raises ValueError for a missing field or an existing NIM."""
    nim, name = _validate(nim, name)
    path = Path(settings.student_csv)
    raw = _read_raw(path)
    if (raw["Nim"].map(normalize_nim) == nim).any():
        raise ValueError(f"Student ID {nim} already exists.")
    row = {
        "Cap waktu": f"{now_local():%Y/%m/%d %I:%M:%S %p} GMT+{settings.utc_offset_hours}",
        "Naran Kompletu": name, "Nim": nim, "Sexu": GENDER_TO_RAW.get(gender, ""), "Fakuldade": faculty.strip(),
        "Departamentu": department.strip().upper(), "Turno": cohort.strip(), "Email": email.strip(),
    }
    _write_raw(path, pd.concat([raw, pd.DataFrame([row])], ignore_index=True)[RAW_COLUMNS])


def update_student(nim: str, name: str, gender: str, faculty: str, department: str, cohort: str, email: str = "") -> None:
    """Change the details of an existing student (the NIM itself is the key and is not changed)."""
    nim, name = _validate(nim, name)
    path = Path(settings.student_csv)
    raw = _read_raw(path)
    mask = raw["Nim"].map(normalize_nim) == nim
    if not mask.any():
        raise ValueError(f"Student ID {nim} not found.")
    raw.loc[mask, ["Naran Kompletu", "Sexu", "Fakuldade", "Departamentu", "Turno", "Email"]] = [
        name, GENDER_TO_RAW.get(gender, ""), faculty.strip(), department.strip().upper(), cohort.strip(), email.strip(),
    ]
    _write_raw(path, raw[RAW_COLUMNS])
