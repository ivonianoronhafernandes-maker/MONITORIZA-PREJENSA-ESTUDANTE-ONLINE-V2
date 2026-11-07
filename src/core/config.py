"""Central application settings.

Every value can be overridden with an environment variable so the same code
runs locally, in Docker, or next to Kafka/Spark later without edits.
"""
from __future__ import annotations

import os
import socket
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value not in (None, "") else default


@dataclass(frozen=True)
class Settings:
    app_name: str = _env("APP_NAME", "Monitorizasaun Prezensa Estudante")
    institution: str = _env("APP_INSTITUTION", "Student Attendance System")

    student_csv: Path = Path(_env("STUDENT_CSV", str(BASE_DIR / "data" / "raw" / "student.csv")))
    database_path: Path = Path(_env("DATABASE_PATH", str(BASE_DIR / "database" / "attendance.db")))

    # Base URL used when building the per-class check-in links.
    # Empty = auto: this computer's Wi-Fi/LAN address, so students' phones can open the links.
    public_base_url_override: str = _env("PUBLIC_BASE_URL", "")

    # First admin account, created only when the database has no admin yet.
    # After that, passwords are managed on the Admin > Settings page.
    admin_username: str = _env("ADMIN_USERNAME", "admin")
    admin_password: str = _env("ADMIN_PASSWORD", "")
    admin_session_days: int = int(_env("ADMIN_SESSION_DAYS", "7"))

    # Students may check in this many minutes before the class starts (they arrive early).
    checkin_early_minutes: int = int(_env("CHECKIN_EARLY_MINUTES", "15"))

    # One device may check in only one NIM per class (anti proxy attendance).
    device_check: bool = _env("DEVICE_CHECK", "1") == "1"

    # Local time zone (Timor-Leste, UTC+9 - matches the dataset timestamps).
    utc_offset_hours: int = int(_env("UTC_OFFSET_HOURS", "9"))

    # Flask dashboard (flask_app/app.py) shown inside the Streamlit Dashboard page.
    flask_url: str = _env("FLASK_URL", "http://127.0.0.1:5000").rstrip("/")
    flask_url_fixed: bool = bool(os.getenv("FLASK_URL"))  # when set, always use it instead of the browser's host

    # Dashboard auto refresh interval (seconds).
    dashboard_refresh_seconds: int = int(_env("DASHBOARD_REFRESH_SECONDS", "5"))

    # Streaming pipeline: app -> Kafka -> Spark Structured Streaming -> dashboard.
    # Start Docker + Kafka + Spark automatically together with `streamlit run App.py`.
    auto_start_pipeline: bool = _env("AUTO_START_PIPELINE", "1") == "1"
    kafka_enabled: bool = _env("KAFKA_ENABLED", "1") == "1"
    kafka_bootstrap: str = _env("KAFKA_BOOTSTRAP", "localhost:9092")
    kafka_topic: str = _env("KAFKA_TOPIC", "attendance-events")
    # Folder where the Spark job writes its results (mounted into the Spark container).
    spark_output_dir: Path = Path(_env("SPARK_OUTPUT_DIR", str(BASE_DIR / "data" / "spark")))
    # Spark results older than this are shown as "Spark offline" on the dashboard.
    spark_stale_seconds: int = int(_env("SPARK_STALE_SECONDS", "30"))

    @property
    def tz(self) -> timezone:
        return timezone(timedelta(hours=self.utc_offset_hours))

    @property
    def public_base_url(self) -> str:
        if self.public_base_url_override:
            return self.public_base_url_override.rstrip("/")
        return f"http://{lan_ip()}:{server_port()}"


@lru_cache(maxsize=1)
def lan_ip() -> str:
    """This computer's address on the local network (falls back to localhost)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))  # no packet is sent; only picks the outgoing interface
            return s.getsockname()[0]
    except OSError:
        return "localhost"


def server_port() -> int:
    try:
        import streamlit as st

        return int(st.get_option("server.port") or 8501)
    except Exception:
        return 8501


settings = Settings()


def now_local() -> datetime:
    """Current time in the configured local time zone (naive, second precision)."""
    return datetime.now(settings.tz).replace(tzinfo=None, microsecond=0)
