"""Starts the streaming side of the app once per Streamlit server process."""
from __future__ import annotations

import logging

import streamlit as st

from src.core.config import settings
from src.streaming import outbox
from src.streaming.backfill import backfill_outbox
from src.streaming.kafka_publisher import OutboxPublisher

logger = logging.getLogger("attendance.streaming")


@st.cache_resource(show_spinner=False)
def start_pipeline() -> OutboxPublisher | None:
    added = backfill_outbox()
    if added:
        logger.info("backfilled %s event(s) into the outbox", added)
    if not settings.kafka_enabled:
        return None
    publisher = OutboxPublisher()
    publisher.start()
    return publisher


def publisher_status() -> dict:
    publisher = start_pipeline()
    if publisher is None:
        return {"enabled": False, "connected": False, "last_error": None, "last_sent_at": None, **outbox.stats()}
    return publisher.status()
