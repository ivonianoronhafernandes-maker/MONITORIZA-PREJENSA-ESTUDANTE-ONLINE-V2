"""Put rows that existed before the streaming pipeline into the outbox.

Safe to run on every start: event ids are deterministic and the outbox
ignores ids it already has.
"""
from __future__ import annotations

from src.core import events
from src.data import database as db
from src.services import class_service
from src.services.attendance_service import attempt_event, attendance_event
from src.streaming import outbox


def backfill_outbox() -> int:
    before = outbox.stats()["total"]

    titles: dict[int, str] = {}
    for session in class_service.list_sessions():
        titles[session.id] = session.title
        outbox.store(
            events.SESSION_CREATED,
            class_service.session_event(session),
            event_id=f"ses-{session.id}",
            key=str(session.id),
        )
        if session.is_cancelled:  # cancelled meetings are excluded from Spark analytics
            outbox.store(
                events.SESSION_DELETED,
                {"session_id": session.id},
                event_id=f"ses-del-{session.id}",
                key=str(session.id),
            )

    for record in db.fetch_df("SELECT * FROM attendance ORDER BY id").to_dict("records"):
        outbox.store(
            events.ATTENDANCE_RECORDED,
            attendance_event(record, titles.get(record["session_id"], "")),
            event_id=f"att-{record['id']}",
            key=str(record["session_id"]),
        )

    for row in db.fetch_df("SELECT * FROM checkin_attempts ORDER BY id").to_dict("records"):
        outbox.store(events.CHECKIN_ATTEMPTED, attempt_event(row), event_id=f"try-{row['id']}", key=str(row["session_id"]))

    return outbox.stats()["total"] - before
