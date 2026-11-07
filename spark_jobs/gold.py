"""Spark computations over the attendance event log.

Input : a DataFrame of raw Kafka events  (event_id, event_type, json)
Output: one JSON-serialisable snapshot with
          - dashboard analytics per period (today / last 7 / last 30 days) and per class
          - proxy-attendance alerts ("titip absen") found by five detection rules

All aggregation, distinct counting, windowing and rule evaluation happen in
Spark. The driver only arranges the small aggregated rows into the snapshot.
"""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from functools import reduce

from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F
from pyspark.sql import types as T

RAW_SCHEMA = "event_id string, event_type string, json string"

RECORDED = T.StructType(
    [
        T.StructField("attendance_id", T.LongType()),
        T.StructField("session_id", T.LongType()),
        T.StructField("class_title", T.StringType()),
        T.StructField("nim", T.StringType()),
        T.StructField("name", T.StringType()),
        T.StructField("gender", T.StringType()),
        T.StructField("faculty", T.StringType()),
        T.StructField("department", T.StringType()),
        T.StructField("cohort", T.StringType()),
        T.StructField("status", T.StringType()),
        T.StructField("attendance_date", T.StringType()),
        T.StructField("checked_in_at", T.StringType()),
        T.StructField("device_id", T.StringType()),
        T.StructField("ip_address", T.StringType()),
        T.StructField("added_by_admin", T.IntegerType()),
    ]
)
ATTEMPT = T.StructType(
    [
        T.StructField("attempt_id", T.LongType()),
        T.StructField("session_id", T.LongType()),
        T.StructField("nim", T.StringType()),
        T.StructField("result", T.StringType()),
        T.StructField("at", T.StringType()),
        T.StructField("device_id", T.StringType()),
        T.StructField("ip_address", T.StringType()),
    ]
)
SESSION = T.StructType(
    [
        T.StructField("session_id", T.LongType()),
        T.StructField("class_title", T.StringType()),
        T.StructField("lecturer", T.StringType()),
        T.StructField("room", T.StringType()),
        T.StructField("session_date", T.StringType()),
        T.StructField("start_time", T.StringType()),
        T.StructField("end_time", T.StringType()),
        T.StructField("departments", T.ArrayType(T.StringType())),
        T.StructField("expected_by_department", T.MapType(T.StringType(), T.IntegerType())),
        T.StructField("expected_total", T.IntegerType()),
    ]
)
SESSION_ID_ONLY = T.StructType([T.StructField("session_id", T.LongType())])
ATTENDANCE_ID_ONLY = T.StructType([T.StructField("attendance_id", T.LongType())])

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


@dataclass(frozen=True)
class DetectionConfig:
    shared_ip_min_students: int = 3   # R2: this many different students from one IP
    burst_seconds: int = 20           # R3: different students from one IP within N seconds
    nim_guess_min_attempts: int = 3   # R4: unknown NIMs tried from one device


# ---- silver: clean, de-duplicated tables ----------------------------------------------------------

def _parse(events: DataFrame, event_type: str, schema: T.StructType) -> DataFrame:
    return (
        events.filter(F.col("event_type") == event_type)
        .select(F.from_json("json", schema).alias("e"))
        .select("e.*")
    )


def build_silver(events: DataFrame) -> tuple[DataFrame, DataFrame, DataFrame]:
    events = events.dropDuplicates(["event_id"])
    deleted_sessions = _parse(events, "class_session.deleted", SESSION_ID_ONLY).select("session_id").distinct()
    deleted_records = _parse(events, "attendance.deleted", ATTENDANCE_ID_ONLY).select("attendance_id").distinct()

    sessions = (
        _parse(events, "class_session.created", SESSION)
        .dropDuplicates(["session_id"])
        .join(deleted_sessions, "session_id", "left_anti")
    )
    session_dates = sessions.select("session_id", "session_date")

    checkins = (
        _parse(events, "attendance.recorded", RECORDED)
        .dropDuplicates(["attendance_id"])
        .join(deleted_records, "attendance_id", "left_anti")
        .join(session_dates, "session_id")  # only classes that still exist
        .withColumn("ts", F.to_timestamp("checked_in_at"))
        .withColumn("added_by_admin", F.coalesce("added_by_admin", F.lit(0)))
    )
    attempts = (
        _parse(events, "attendance.checkin_attempted", ATTEMPT)
        .dropDuplicates(["attempt_id"])
        .join(session_dates, "session_id")
        .withColumn("ts", F.to_timestamp("at"))
    )
    return sessions.cache(), checkins.cache(), attempts.cache()


# ---- proxy attendance detection ---------------------------------------------------------------

_ALERT_COLUMNS = ["rule", "severity", "session_id", "subject", "nims", "occurrences", "first_seen", "last_seen", "detail"]


def _fmt(col: str | F.Column) -> F.Column:
    return F.date_format(col, "yyyy-MM-dd HH:mm:ss")


def detect_proxy_attendance(
    sessions: DataFrame, checkins: DataFrame, attempts: DataFrame, cfg: DetectionConfig
) -> DataFrame:
    student_checkins = checkins.filter((F.col("added_by_admin") == 0))

    # R1 - a phone that already checked in one student tried to check in others
    owners = (
        student_checkins.filter(F.col("device_id").isNotNull())
        .groupBy("session_id", "device_id")
        .agg(F.first("nim").alias("owner"))
    )
    r1 = (
        attempts.filter((F.col("result") == "device_used") & F.col("device_id").isNotNull())
        .groupBy("session_id", "device_id")
        .agg(
            F.collect_set("nim").alias("tried"),
            F.count("*").alias("occurrences"),
            F.min("ts").alias("first"),
            F.max("ts").alias("last"),
        )
        .join(owners, ["session_id", "device_id"], "left")
        .select(
            F.lit("device_reuse").alias("rule"),
            F.lit("high").alias("severity"),
            "session_id",
            F.concat(F.lit("device "), F.substring("device_id", 1, 8)).alias("subject"),
            F.when(F.col("owner").isNull(), F.col("tried"))
            .otherwise(F.array_distinct(F.concat(F.array("owner"), F.col("tried"))))
            .alias("nims"),
            "occurrences",
            _fmt("first").alias("first_seen"),
            _fmt("last").alias("last_seen"),
            F.format_string(
                "Phone used by %s tried to check in %d other NIM(s): %s",
                F.coalesce("owner", F.lit("an unknown student")),
                F.size("tried"),
                F.concat_ws(", ", "tried"),
            ).alias("detail"),
        )
    )

    by_ip = student_checkins.filter(F.col("ip_address").isNotNull())

    # R2 - many different students checked in from one IP address
    r2 = (
        by_ip.groupBy("session_id", "ip_address")
        .agg(
            F.countDistinct("nim").alias("students"),
            F.collect_set("nim").alias("nims"),
            F.min("ts").alias("first"),
            F.max("ts").alias("last"),
        )
        .filter(F.col("students") >= cfg.shared_ip_min_students)
        .select(
            F.lit("shared_ip").alias("rule"),
            F.lit("medium").alias("severity"),
            "session_id",
            F.concat(F.lit("IP "), "ip_address").alias("subject"),
            "nims",
            F.col("students").cast("long").alias("occurrences"),
            _fmt("first").alias("first_seen"),
            _fmt("last").alias("last_seen"),
            F.format_string("%d different students checked in from the same IP address %s", "students", "ip_address")
            .alias("detail"),
        )
    )

    # R3 - different students checked in back-to-back from one IP (window function)
    w = Window.partitionBy("session_id", "ip_address").orderBy("ts")
    pairs = (
        by_ip.withColumn("prev_nim", F.lag("nim").over(w))
        .withColumn("prev_ts", F.lag("ts").over(w))
        .filter(
            F.col("prev_nim").isNotNull()
            & (F.col("nim") != F.col("prev_nim"))
            & ((F.unix_timestamp("ts") - F.unix_timestamp("prev_ts")) <= cfg.burst_seconds)
        )
    )
    r3 = (
        pairs.groupBy("session_id", "ip_address")
        .agg(
            F.count("*").alias("occurrences"),
            F.array_distinct(F.flatten(F.collect_list(F.array("prev_nim", "nim")))).alias("nims"),
            F.min("prev_ts").alias("first"),
            F.max("ts").alias("last"),
        )
        .select(
            F.lit("rapid_burst").alias("rule"),
            F.lit("high").alias("severity"),
            "session_id",
            F.concat(F.lit("IP "), "ip_address").alias("subject"),
            "nims",
            "occurrences",
            _fmt("first").alias("first_seen"),
            _fmt("last").alias("last_seen"),
            F.format_string(
                "%d back-to-back check-ins of different students within %d s from IP %s",
                "occurrences",
                F.lit(cfg.burst_seconds),
                "ip_address",
            ).alias("detail"),
        )
    )

    # R4 - one device kept trying NIMs that do not exist
    r4 = (
        attempts.filter((F.col("result") == "not_found") & F.col("device_id").isNotNull())
        .groupBy("session_id", "device_id")
        .agg(
            F.count("*").alias("occurrences"),
            F.collect_set("nim").alias("nims"),
            F.min("ts").alias("first"),
            F.max("ts").alias("last"),
        )
        .filter(F.col("occurrences") >= cfg.nim_guess_min_attempts)
        .select(
            F.lit("nim_guessing").alias("rule"),
            F.lit("low").alias("severity"),
            "session_id",
            F.concat(F.lit("device "), F.substring("device_id", 1, 8)).alias("subject"),
            "nims",
            "occurrences",
            _fmt("first").alias("first_seen"),
            _fmt("last").alias("last_seen"),
            F.format_string("%d unknown NIMs tried from one device", "occurrences").alias("detail"),
        )
    )

    # R5 - the same student is present in two classes whose times overlap
    timed = checkins.join(
        sessions.select("session_id", "start_time", "end_time", F.col("class_title").alias("title")), "session_id"
    )
    a, b = timed.alias("a"), timed.alias("b")
    r5 = a.join(
        b,
        (F.col("a.nim") == F.col("b.nim"))
        & (F.col("a.session_date") == F.col("b.session_date"))
        & (F.col("a.session_id") < F.col("b.session_id"))
        & (F.col("a.start_time") < F.col("b.end_time"))
        & (F.col("b.start_time") < F.col("a.end_time")),
    ).select(
        F.lit("overlapping_classes").alias("rule"),
        F.lit("medium").alias("severity"),
        F.col("b.session_id").alias("session_id"),
        F.concat(F.lit("NIM "), F.col("a.nim")).alias("subject"),
        F.array(F.col("a.nim")).alias("nims"),
        F.lit(1).cast("long").alias("occurrences"),
        _fmt(F.least("a.ts", "b.ts")).alias("first_seen"),
        _fmt(F.greatest("a.ts", "b.ts")).alias("last_seen"),
        F.format_string(
            "%s is checked in to two classes at the same time: %s and %s", F.col("a.name"), F.col("a.title"), F.col("b.title")
        ).alias("detail"),
    )

    alerts = r1.unionByName(r2).unionByName(r3).unionByName(r4).unionByName(r5)
    return alerts.join(sessions.select("session_id", "class_title", "session_date"), "session_id", "left")


# ---- gold: snapshot for the dashboard ---------------------------------------------------------

def _collect_all(queries: dict[str, DataFrame]) -> dict[str, list[dict]]:
    """Run every aggregation as ONE Spark job.

    Each query's rows are serialised to JSON and all queries are unioned, so
    Spark schedules a single action. For class-sized data the fixed cost per
    action (not the data) dominated the run time.
    """
    keep_nulls = {"ignoreNullFields": "false"}
    parts = [
        df.select(F.lit(name).alias("query"), F.to_json(F.struct(*df.columns), keep_nulls).alias("row"))
        for name, df in queries.items()
    ]
    results: dict[str, list[dict]] = {name: [] for name in queries}
    for r in reduce(DataFrame.unionByName, parts).collect():
        results[r["query"]].append(json.loads(r["row"]))
    return results


def build_snapshot(spark: SparkSession, events: DataFrame, today: date, cfg: DetectionConfig = DetectionConfig()) -> dict:
    sessions_df, checkins, attempts = build_silver(events)
    try:
        return _snapshot(sessions_df, checkins, attempts, today, cfg)
    finally:
        for df in (sessions_df, checkins, attempts):
            df.unpersist()


def _snapshot(sessions_df, checkins, attempts, today: date, cfg: DetectionConfig) -> dict:
    present = F.when(F.col("status") == "Present", 1).otherwise(0)
    late = F.when(F.col("status") == "Late", 1).otherwise(0)
    periods = {
        "today": (today, today),
        "last_7_days": (today - timedelta(days=6), today),
        "last_30_days": (today - timedelta(days=29), today),
    }
    # Distinct students per period, all periods in one pass (conditional distinct counts).
    distinct_per_period = [
        F.countDistinct(F.when(F.col("session_date").between(start.isoformat(), end.isoformat()), F.col("nim"))).alias(name)
        for name, (start, end) in periods.items()
    ]
    trend_start = today - timedelta(days=13)

    q = _collect_all(
        {
            "sessions": sessions_df,
            "class_agg": checkins.groupBy("session_id").agg(
                F.count("*").alias("attended"),
                F.sum(present).alias("on_time"),
                F.sum(late).alias("late"),
                F.countDistinct("nim").alias("students"),
            ),
            "buckets": checkins.groupBy(
                "session_id",
                F.from_unixtime(F.floor(F.unix_timestamp("ts") / 900) * 900).alias("bucket"),
                "status",
            ).count(),
            "days": checkins.groupBy("session_id", F.col("attendance_date").alias("bucket"), "status").count(),
            "departments": checkins.groupBy("session_id", "department").agg(F.count("*").alias("attended")),
            "class_gender": checkins.groupBy("session_id", "gender").agg(F.countDistinct("nim").alias("students")),
            "attempts": attempts.groupBy("session_id", "result").count(),
            "expected": sessions_df.select(
                "session_id", F.explode("expected_by_department").alias("department", "expected")
            ),
            "alerts": detect_proxy_attendance(sessions_df, checkins, attempts, cfg),
            "trend": checkins.filter(F.col("session_date") >= trend_start.isoformat())
            .groupBy("session_date")
            .agg(F.countDistinct("nim").alias("students")),
            "latest": checkins.orderBy(F.col("ts").desc(), F.col("attendance_id").desc())
            .limit(50)
            .select(
                "attendance_id", "checked_in_at", "name", "nim", "department", "class_title", "status",
                "session_id", "added_by_admin",
            ),
            "period_students": checkins.agg(*distinct_per_period),
            "period_gender": checkins.groupBy("gender").agg(*distinct_per_period),
        }
    )

    sessions = {r["session_id"]: r for r in q["sessions"]}
    class_agg = {r["session_id"]: r for r in q["class_agg"]}
    bucket_rows, day_rows = q["buckets"], q["days"]
    dept_rows, gender_rows = q["departments"], q["class_gender"]
    attempt_rows, expected_rows = q["attempts"], q["expected"]
    trend_counts = {r["session_date"]: r["students"] for r in q["trend"]}
    # union() does not keep row order: sort the small results here
    latest = sorted(q["latest"], key=lambda r: (r["checked_in_at"], r["attendance_id"]), reverse=True)
    period_students = q["period_students"][0] if q["period_students"] else {}
    period_gender = sorted(q["period_gender"], key=lambda g: g["gender"] or "")
    # Newest first within each severity (two stable sorts).
    alerts = sorted(q["alerts"], key=lambda a: a["last_seen"] or "", reverse=True)
    alerts.sort(key=lambda a: SEVERITY_ORDER.get(a["severity"], 9))

    # -- assemble views from the aggregated rows --------------------------------------------------
    def sum_by(rows, sids, key, value):
        out = defaultdict(int)
        for r in rows:
            if r["session_id"] in sids:
                out[r[key]] += r[value] or 0
        return out

    def timeline(sids, rows):
        out = defaultdict(lambda: {"Present": 0, "Late": 0})
        for r in rows:
            if r["session_id"] in sids and r["status"] in ("Present", "Late"):
                out[r["bucket"]][r["status"]] += r["count"]
        return [{"time": k, **v} for k, v in sorted(out.items())]

    def view(sids: set, students: int, gender: list[dict], single_day: bool) -> dict:
        attended = sum(class_agg.get(s, {}).get("attended", 0) for s in sids)
        late_n = sum(class_agg.get(s, {}).get("late", 0) or 0 for s in sids)
        expected = sum(sessions[s]["expected_total"] or 0 for s in sids)
        attempt_counts = sum_by(attempt_rows, sids, "result", "count")
        dept_expected = sum_by(expected_rows, sids, "department", "expected")
        dept_attended = sum_by(dept_rows, sids, "department", "attended")
        classes = []
        for s in sorted(sids, key=lambda s: (sessions[s]["session_date"], sessions[s]["start_time"])):
            agg, meta = class_agg.get(s, {}), sessions[s]
            exp = meta["expected_total"] or 0
            classes.append(
                {
                    "session_id": s,
                    "class": meta["class_title"],
                    "date": meta["session_date"],
                    "time": f"{meta['start_time']}-{meta['end_time']}",
                    "attended": agg.get("attended", 0),
                    "on_time": agg.get("on_time", 0) or 0,
                    "late": agg.get("late", 0) or 0,
                    "expected": exp,
                    "rate": min(agg.get("attended", 0) / exp, 1.0) if exp else 0.0,
                }
            )
        return {
            "kpis": {
                "checkins": attended,
                "students": students,
                "late": late_n,
                "late_rate": late_n / attended if attended else 0.0,
                "expected": expected,
                "rate": min(attended / expected, 1.0) if expected else 0.0,
                "classes": len(sids),
                "failed_attempts": attempt_counts.get("not_found", 0),
                "proxy_blocked": attempt_counts.get("device_used", 0),
                "alerts": sum(1 for a in alerts if a["session_id"] in sids),
            },
            "timeline": timeline(sids, bucket_rows if single_day else day_rows),
            "timeline_unit": "15min" if single_day else "day",
            "departments": sorted(
                (
                    {
                        "department": d,
                        "attended": dept_attended.get(d, 0),
                        "expected": e,
                        "rate": min(dept_attended.get(d, 0) / e, 1.0) if e else 0.0,
                    }
                    for d, e in dept_expected.items()
                    if e
                ),
                key=lambda r: -r["rate"],
            ),
            "gender": gender,
            "attempts": [{"result": k, "count": v} for k, v in sorted(attempt_counts.items(), key=lambda kv: -kv[1])],
            "classes": classes,
        }

    period_views = {}
    for name, (start, end) in periods.items():
        sids = {s for s, m in sessions.items() if start.isoformat() <= m["session_date"] <= end.isoformat()}
        students = period_students.get(name) or 0
        gender = [{"gender": g["gender"], "students": g[name]} for g in period_gender if g[name]]
        period_views[name] = {
            "start": start.isoformat(),
            "end": end.isoformat(),
            **view(sids, students, gender, single_day=start == end),
        }

    class_views = {}
    for s, meta in sessions.items():
        gender = [{"gender": r["gender"], "students": r["students"]} for r in gender_rows if r["session_id"] == s]
        class_views[str(s)] = {
            "title": meta["class_title"],
            "session_date": meta["session_date"],
            "time": f"{meta['start_time']}-{meta['end_time']}",
            **view({s}, class_agg.get(s, {}).get("students", 0), gender, single_day=True),
        }

    return {
        "today": today.isoformat(),
        "periods": period_views,
        "classes": class_views,
        "trend": [
            {"date": d.isoformat(), "students": trend_counts.get(d.isoformat(), 0)}
            for d in (trend_start + timedelta(days=i) for i in range(14))
        ],
        "latest": latest,
        "alerts": alerts,
        "totals": {
            "sessions": len(sessions),
            "checkins": sum(a["attended"] for a in class_agg.values()),
            "attempts": sum(r["count"] for r in attempt_rows),
            "alerts": len(alerts),
        },
    }
