"""Domain events.

Every event is written to the ``event_outbox`` table (see src/streaming/outbox.py);
a background publisher sends the outbox to Kafka, where Spark Structured
Streaming processes it. Event ids are deterministic (``att-12``, ``ses-3`` ...)
so re-sending an event never double counts it in Spark.

In-process subscribers can still listen with :func:`subscribe`.
"""
from __future__ import annotations

import logging
from typing import Callable

logger = logging.getLogger("attendance.events")

Handler = Callable[[str, dict], None]
_handlers: list[Handler] = []

ATTENDANCE_RECORDED = "attendance.recorded"
ATTENDANCE_DELETED = "attendance.deleted"
CHECKIN_ATTEMPTED = "attendance.checkin_attempted"
SESSION_CREATED = "class_session.created"
SESSION_DELETED = "class_session.deleted"


def subscribe(handler: Handler) -> None:
    if handler not in _handlers:
        _handlers.append(handler)


def publish(event_type: str, payload: dict, *, event_id: str, key: str | None = None) -> None:
    from src.streaming import outbox  # local import: outbox depends on the database layer

    try:
        outbox.store(event_type, payload, event_id=event_id, key=key)
    except Exception:  # never block a check-in because of the event log
        logger.exception("could not store event %s in outbox", event_id)

    for handler in list(_handlers):
        try:
            handler(event_type, payload)
        except Exception:  # a broken subscriber must never block a check-in
            logger.exception("event handler failed for %s", event_type)
