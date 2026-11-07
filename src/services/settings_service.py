"""System settings edited on Admin > Settings > General (stored in the app_settings table)."""
from __future__ import annotations

from datetime import datetime

from src.core.config import now_local
from src.core.i18n_dict import DICT
from src.data import database as db

LANGUAGES = ["Tetum", "English", "Indonesia"]
STATUSES = ["Present", "Late"]
DEFAULT_SYSTEM_NAME = "Monitorizasaun Prezensa Estudante"


def _default_names() -> set[str]:
    """The built-in system name in every language (Tetum key, English, Indonesia)."""
    names: set[str] = set()
    for tetum, (en, idn) in DICT.items():
        if en == "Student Attendance Monitoring":
            names |= {tetum, en, idn}
    return names


def defaults() -> dict[str, str]:
    return {
        "system_name": DEFAULT_SYSTEM_NAME,
        "academic_year": str(now_local().year),
        "default_status": "Present",
        "language": "Tetum",
    }


def get_all() -> dict[str, str]:
    values = defaults()
    rows = db.fetch_df("SELECT key, value FROM app_settings")
    for r in rows.itertuples():
        if r.key in values:
            values[r.key] = r.value
    if values["system_name"] in _default_names():  # never renamed: follow the interface language
        values["system_name"] = DEFAULT_SYSTEM_NAME
    return values


def get(key: str) -> str:
    return get_all()[key]


def save(system_name: str, academic_year: str, default_status: str, language: str) -> None:
    """Validate and store the General settings."""
    system_name = " ".join((system_name or "").split())
    academic_year = (academic_year or "").strip()
    if not system_name:
        raise ValueError("Naran sistema labele mamuk.")
    if not academic_year:
        raise ValueError("Tinan akadémiku labele mamuk.")
    if default_status not in STATUSES:
        raise ValueError("Status prezensa default tenke Prezente ka Atrazu.")
    if language not in LANGUAGES:
        raise ValueError("Lian la apoiu.")
    values = {
        "system_name": system_name, "academic_year": academic_year,
        "default_status": default_status, "language": language,
        "updated_at": f"{now_local():%Y-%m-%d %H:%M:%S}",
    }
    with db.get_connection() as conn:
        conn.executemany(
            "INSERT INTO app_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            list(values.items()),
        )


def last_update() -> str:
    row = db.fetch_one("SELECT value FROM app_settings WHERE key = 'updated_at'")
    if not row:
        return "-"
    try:
        return f"{datetime.fromisoformat(row['value']):%d/%m/%Y %H:%M}"
    except ValueError:
        return row["value"]
