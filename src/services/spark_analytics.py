"""Reads the analytics produced by the Spark Structured Streaming job.

The dashboard shows only these Spark results; it does not aggregate the
attendance tables itself.
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

from src.core.config import now_local, settings

SNAPSHOT_FILE = "analytics.json"
STATUS_FILE = "spark_status.json"

_cache: dict[str, tuple[float, dict]] = {}


def _read_json(name: str) -> dict | None:
    path = Path(settings.spark_output_dir) / name
    try:
        mtime = path.stat().st_mtime
    except FileNotFoundError:
        return None
    cached = _cache.get(name)
    if cached and cached[0] == mtime:
        return cached[1]
    for _ in range(3):  # Spark replaces the file atomically; retry if we catch it mid-swap
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            _cache[name] = (mtime, data)
            return data
        except (json.JSONDecodeError, OSError):
            time.sleep(0.1)
    return cached[1] if cached else None


def _age_seconds(stamp: str | None) -> float | None:
    if not stamp:
        return None
    try:
        return (now_local() - datetime.fromisoformat(stamp)).total_seconds()
    except ValueError:
        return None


def load_snapshot() -> dict | None:
    return _read_json(SNAPSHOT_FILE)


def spark_status() -> dict:
    status = _read_json(STATUS_FILE) or {}
    age = _age_seconds(status.get("alive_at"))
    return {
        **status,
        "online": age is not None and age <= settings.spark_stale_seconds,
        "heartbeat_age": age,
    }


def snapshot_age(snapshot: dict | None) -> float | None:
    return _age_seconds((snapshot or {}).get("generated_at"))
