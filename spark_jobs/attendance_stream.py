"""Spark Structured Streaming job: Kafka -> analytics snapshot for the dashboard.

Flow per micro-batch (foreachBatch):
  1. new Kafka events are appended to a Parquet event log (bronze)
  2. the whole log is recomputed with Spark (gold.py): analytics + proxy detection
  3. the result is written atomically to OUTPUT_DIR/analytics.json

A heartbeat (OUTPUT_DIR/spark_status.json) is written every few seconds so the
dashboard knows whether Spark is alive, and the snapshot is refreshed every
minute even without new events (e.g. when the date changes).
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.utils import AnalysisException

import gold

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:29092")
TOPIC = os.getenv("KAFKA_TOPIC", "attendance-events")
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "/opt/app/output"))
STATE_DIR = os.getenv("STATE_DIR", "/opt/app/state")
TRIGGER_SECONDS = int(os.getenv("TRIGGER_SECONDS", "5"))
UTC_OFFSET_HOURS = int(os.getenv("UTC_OFFSET_HOURS", "9"))
REFRESH_SECONDS = int(os.getenv("REFRESH_SECONDS", "60"))

BRONZE = f"{STATE_DIR}/bronze_events"
CHECKPOINT = f"{STATE_DIR}/checkpoint"
TZ = timezone(timedelta(hours=UTC_OFFSET_HOURS))
CONFIG = gold.DetectionConfig(
    shared_ip_min_students=int(os.getenv("SHARED_IP_MIN_STUDENTS", "3")),
    burst_seconds=int(os.getenv("BURST_SECONDS", "20")),
    nim_guess_min_attempts=int(os.getenv("NIM_GUESS_MIN_ATTEMPTS", "3")),
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("attendance-stream")


def now_local() -> datetime:
    return datetime.now(TZ).replace(tzinfo=None, microsecond=0)


def write_json(name: str, data: dict) -> None:
    """Write atomically so the dashboard never reads a half-written file."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    target = OUTPUT_DIR / name
    tmp = OUTPUT_DIR / f".{name}.tmp"
    tmp.write_text(json.dumps(data, default=str, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, target)


spark = (
    SparkSession.builder.appName("attendance-stream")
    .config("spark.sql.session.timeZone", "UTC")  # event timestamps are already local time strings
    # Class-sized data: one shuffle partition avoids scheduling many near-empty tasks per query,
    # and adaptive execution only adds re-planning overhead here (measured: ~11s -> ~6s per refresh).
    .config("spark.sql.shuffle.partitions", "1")
    .config("spark.sql.adaptive.enabled", "false")
    .config("spark.ui.showConsoleProgress", "false")
    .getOrCreate()
)
spark.sparkContext.setLogLevel("WARN")

lock = threading.Lock()
state = {"last_refresh": 0.0, "last_batch_id": None, "events_in_log": 0, "last_batch_rows": 0}


def load_event_log():
    try:
        return spark.read.parquet(BRONZE).select("event_id", "event_type", "json")
    except AnalysisException:  # nothing received yet
        return spark.createDataFrame([], gold.RAW_SCHEMA)


def refresh(reason: str) -> None:
    started = time.time()
    events = load_event_log().cache()
    try:
        total = events.count()
        snapshot = gold.build_snapshot(spark, events, now_local().date(), CONFIG)
    finally:
        events.unpersist()
    snapshot["generated_at"] = now_local().isoformat(sep=" ")
    snapshot["compute_seconds"] = round(time.time() - started, 2)
    snapshot["events_in_log"] = total
    snapshot["trigger"] = reason
    write_json("analytics.json", snapshot)
    state.update(last_refresh=time.time(), events_in_log=total)
    log.info("snapshot written (%s): %s events, %.1fs", reason, total, time.time() - started)


def process_batch(batch_df, batch_id: int) -> None:
    rows = batch_df.count()
    if rows:
        batch_df.write.mode("append").parquet(BRONZE)
    with lock:
        state.update(last_batch_id=batch_id, last_batch_rows=rows)
        if rows or state["last_refresh"] == 0:
            refresh(f"batch {batch_id}: {rows} new event(s)")


raw = (
    spark.readStream.format("kafka")
    .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP)
    .option("subscribe", TOPIC)
    .option("startingOffsets", "earliest")
    .option("failOnDataLoss", "false")
    .load()
)
events_stream = raw.select(
    F.get_json_object(F.col("value").cast("string"), "$.event_id").alias("event_id"),
    F.get_json_object(F.col("value").cast("string"), "$.event_type").alias("event_type"),
    F.col("value").cast("string").alias("json"),
    F.col("timestamp").alias("kafka_timestamp"),
    "partition",
    "offset",
).filter(F.col("event_id").isNotNull())

query = (
    events_stream.writeStream.queryName("attendance_events")
    .foreachBatch(process_batch)
    .option("checkpointLocation", CHECKPOINT)
    .trigger(processingTime=f"{TRIGGER_SECONDS} seconds")
    .start()
)
log.info("streaming from %s topic %s every %ss", KAFKA_BOOTSTRAP, TOPIC, TRIGGER_SECONDS)

def heartbeat() -> None:
    """Write spark_status.json every few seconds from its own thread, so a long
    recomputation never makes the dashboard think Spark is down."""
    while query.isActive:
        try:
            progress = query.lastProgress or {}
            write_json(
                "spark_status.json",
                {
                    "alive_at": now_local().isoformat(sep=" "),
                    "query": query.name,
                    "status": query.status.get("message"),
                    "computing": lock.locked(),
                    "last_batch_id": state["last_batch_id"],
                    "last_batch_rows": state["last_batch_rows"],
                    "events_in_log": state["events_in_log"],
                    "input_rows_per_second": progress.get("inputRowsPerSecond"),
                    "batch_duration_ms": (progress.get("durationMs") or {}).get("triggerExecution"),
                    "trigger_seconds": TRIGGER_SECONDS,
                    "kafka_topic": TOPIC,
                },
            )
        except Exception:
            log.exception("heartbeat failed")
        time.sleep(TRIGGER_SECONDS)


threading.Thread(target=heartbeat, name="heartbeat", daemon=True).start()

# Periodic refresh (e.g. after midnight) in the main thread.
while query.isActive:
    if time.time() - state["last_refresh"] > REFRESH_SECONDS and lock.acquire(blocking=False):
        try:
            refresh("scheduled refresh")
        except Exception:
            log.exception("scheduled refresh failed")
        finally:
            lock.release()
    query.awaitTermination(TRIGGER_SECONDS)

log.error("query stopped: %s", query.exception())