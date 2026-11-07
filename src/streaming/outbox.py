"""Transactional outbox for domain events waiting to be published to Kafka."""
from __future__ import annotations

import json

from src.core.config import now_local
from src.data import database as db


def envelope(event_type: str, payload: dict, event_id: str) -> dict:
    return {"event_id": event_id, "event_type": event_type, "occurred_at": now_local().isoformat(sep=" "), **payload}


def store(event_type: str, payload: dict, *, event_id: str, key: str | None = None) -> None:
    """Save an event once (idempotent on ``event_id``)."""
    body = json.dumps(envelope(event_type, payload, event_id), default=str, ensure_ascii=False)
    db.execute(
        "INSERT OR IGNORE INTO event_outbox (event_id, event_type, event_key, payload, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (event_id, event_type, key, body, now_local().isoformat(sep=" ")),
    )


def pending(limit: int = 500) -> list[dict]:
    return db.fetch_df(
        "SELECT id, event_id, event_key, payload FROM event_outbox WHERE published_at IS NULL ORDER BY id LIMIT ?",
        (limit,),
    ).to_dict("records")


def mark_published(ids: list[int]) -> None:
    if not ids:
        return
    marks = ",".join("?" * len(ids))
    db.execute(
        f"UPDATE event_outbox SET published_at = ? WHERE id IN ({marks})",
        (now_local().isoformat(sep=" "), *ids),
    )


def stats() -> dict:
    row = db.fetch_one(
        "SELECT COUNT(*) AS total, SUM(CASE WHEN published_at IS NULL THEN 1 ELSE 0 END) AS pending, "
        "MAX(published_at) AS last_published_at FROM event_outbox"
    )
    return {"total": row["total"] or 0, "pending": row["pending"] or 0, "last_published_at": row["last_published_at"]}


def reset_published() -> int:
    """Mark every event as unpublished so the whole history is sent to Kafka again."""
    with db.get_connection() as conn:
        return conn.execute("UPDATE event_outbox SET published_at = NULL").rowcount
