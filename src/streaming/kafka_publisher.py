"""Background thread that publishes the event outbox to Kafka."""
from __future__ import annotations

import logging
import threading
import time

from src.core.config import now_local, settings
from src.streaming import outbox

logger = logging.getLogger("attendance.kafka")


class OutboxPublisher(threading.Thread):
    """Polls the outbox and sends pending events to Kafka.

    Events are only marked as published after Kafka acknowledged them, so a
    Kafka outage just delays delivery. Reconnects automatically.
    """

    def __init__(self, poll_seconds: float = 1.0, retry_seconds: float = 5.0):
        super().__init__(name="kafka-outbox-publisher", daemon=True)
        self.poll_seconds = poll_seconds
        self.retry_seconds = retry_seconds
        self._producer = None
        self._stop = threading.Event()
        self.connected = False
        self.last_error: str | None = None
        self.last_sent_at: str | None = None
        self.sent_total = 0

    # -- kafka ---------------------------------------------------------------------------------
    def _connect(self):
        from kafka import KafkaProducer  # imported lazily so the app runs without Kafka installed

        return KafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap,
            acks="all",
            linger_ms=20,
            retries=3,
            request_timeout_ms=10_000,
            max_block_ms=5_000,
            key_serializer=lambda k: k.encode() if k else None,
            value_serializer=lambda v: v.encode("utf-8"),
        )

    def publish_pending(self) -> int:
        """Send one batch of pending events. Returns how many were acknowledged."""
        rows = outbox.pending(500)
        if not rows:
            return 0
        if self._producer is None:
            self._producer = self._connect()
        futures = [(r["id"], self._producer.send(settings.kafka_topic, key=r["event_key"], value=r["payload"])) for r in rows]
        self._producer.flush(timeout=15)
        acked = [row_id for row_id, fut in futures if fut.succeeded()]
        outbox.mark_published(acked)
        if len(acked) < len(rows):
            failed = next(fut for _, fut in futures if not fut.succeeded())
            raise RuntimeError(f"Kafka did not acknowledge {len(rows) - len(acked)} event(s): {failed.exception}")
        self.sent_total += len(acked)
        self.last_sent_at = now_local().isoformat(sep=" ")
        return len(acked)

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                if self._producer is None:  # connect up front so the status is right even when idle
                    self._producer = self._connect()
                sent = self.publish_pending()
                if self._producer is not None:
                    self.connected, self.last_error = True, None
                if sent == 500:
                    continue  # backlog: keep going without sleeping
                self._stop.wait(self.poll_seconds)
            except Exception as exc:  # broker down, network error...
                error = str(exc)[:300]
                if error != self.last_error:  # log each distinct problem once, not every retry
                    logger.warning("Kafka publish failed (retrying every %ss): %s", self.retry_seconds, error)
                self.connected, self.last_error = False, error
                self._close()
                self._stop.wait(self.retry_seconds)

    def _close(self) -> None:
        if self._producer is not None:
            try:
                self._producer.close(timeout=2)
            except Exception:
                pass
            self._producer = None

    def stop(self) -> None:
        self._stop.set()
        self._close()

    def status(self) -> dict:
        return {
            "enabled": settings.kafka_enabled,
            "connected": self.connected,
            "last_error": self.last_error,
            "last_sent_at": self.last_sent_at,
            "sent_since_start": self.sent_total,
            **outbox.stats(),
        }
