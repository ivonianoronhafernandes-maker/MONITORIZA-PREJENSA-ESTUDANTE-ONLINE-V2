"""Checks the Spark computations (spark_jobs/gold.py) on events produced by the real app code.

Two steps, because Spark runs in Docker while the app runs on the host:

  1. host   :  python tests/test_spark_gold.py export data/spark/test_events.json
  2. docker :  docker compose run --rm --no-deps spark-test

Step 2 runs  spark-submit tests/test_spark_gold.py check <file>  inside the Spark image.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import date, time, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


# ---- step 1: produce events with the application code (host) -----------------------------------

def export(path: Path) -> None:
    sys.path.insert(0, str(ROOT))
    os.environ["DATABASE_PATH"] = str(Path(tempfile.mkdtemp()) / "spark_test.db")

    from src.core.config import now_local
    from src.data import database as db
    from src.services import attendance_service, class_service
    from src.services.attendance_service import check_in

    today = now_local().date()
    make = class_service.create_session
    cs = make(course_name="Big Data", class_name="CS-A", lecturer="L", room="R", session_date=today,
              start_time=time(0, 0), end_time=time(23, 59), late_after_minutes=24 * 60, enforce_schedule=False)
    acc = make(course_name="Accounting", class_name="ACC-1", lecturer="L", room="R", session_date=today,
               start_time=time(0, 0), end_time=time(23, 59), departments=["ACC"], enforce_schedule=False)
    old = make(course_name="Old", class_name="Past", lecturer="L", room="R", session_date=today - timedelta(days=3),
               start_time=time(8, 0), end_time=time(10, 0), enforce_schedule=False)
    gone = make(course_name="Deleted", class_name="X", lecturer="L", room="R", session_date=today,
                start_time=time(8, 0), end_time=time(9, 0), enforce_schedule=False)

    # Normal students, each on their own phone / IP
    check_in(cs, "2401020110102", device_id="d1", ip_address="10.0.0.1")
    check_in(cs, "2401020110041", device_id="d2", ip_address="10.0.0.2")
    # R1: phone d3 checks in one student, then tries two friends (both blocked by the app)
    check_in(cs, "2401020110126", device_id="d3", ip_address="10.0.0.3")
    check_in(cs, "2401020110147", device_id="d3", ip_address="10.0.0.3")
    check_in(cs, "2401020110059", device_id="d3", ip_address="10.0.0.3")
    # R2 + R3: three students from one IP (e.g. one laptop, three browsers) within seconds
    for dev, nim in (("e1", "2401020110093"), ("e2", "2401020110092"), ("e3", "2401020110016")):
        check_in(cs, nim, device_id=dev, ip_address="10.0.0.9")
    # R4: guessing NIMs
    for fake in ("111", "222", "333"):
        check_in(cs, fake, device_id="g1", ip_address="10.0.0.7")
    # R5: the same student present in two overlapping classes
    check_in(acc, "2403070110002", device_id="a1", ip_address="10.0.1.1")
    check_in(cs, "2403070110002", admin_override=True)
    # Past class, a deleted class and a deleted record
    check_in(old, "2401020110063", device_id="o1", ip_address="10.0.2.1")
    check_in(gone, "2401020110086", device_id="x1", ip_address="10.0.3.1")
    class_service.delete_session(gone.id)
    wrong = check_in(cs, "2401020110003", device_id="w1", ip_address="10.0.4.1")
    attendance_service.delete_record(wrong.record["id"])

    rows = db.fetch_df("SELECT event_id, event_type, payload FROM event_outbox ORDER BY id").values.tolist()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"today": today.isoformat(), "cs": cs.id, "acc": acc.id, "rows": rows}), encoding="utf-8"
    )
    print(f"exported {len(rows)} events to {path}")


# ---- step 2: run gold.py in Spark and verify (Docker) -----------------------------------------

def check(path: Path) -> None:
    sys.path.insert(0, str(ROOT / "spark_jobs"))
    from pyspark.sql import SparkSession

    import gold

    data = json.loads(path.read_text(encoding="utf-8"))
    rows = [tuple(r) for r in data["rows"]] * 2  # Kafka is at-least-once: duplicates must not count twice
    spark = (
        SparkSession.builder.master("local[*]").appName("gold-test")
        .config("spark.sql.session.timeZone", "UTC").config("spark.sql.shuffle.partitions", "1")
        .config("spark.sql.adaptive.enabled", "false")
        .config("spark.ui.enabled", "false").getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")
    try:
        snap = gold.build_snapshot(spark, spark.createDataFrame(rows, gold.RAW_SCHEMA), date.fromisoformat(data["today"]))
    finally:
        spark.stop()

    json.dumps(snap)
    k = snap["periods"]["today"]["kpis"]
    # CS: 102, 041, 126, 093, 092, 016, 2403070110002 (admin) = 7; ACC: 1; deleted class/record ignored
    assert k["checkins"] == 8, k
    assert k["students"] == 7, k  # 2403070110002 counted once across both classes
    assert k["classes"] == 2, k
    assert k["failed_attempts"] == 3 and k["proxy_blocked"] == 2, k
    acc_expected = snap["classes"][str(data["acc"])]["kpis"]["expected"]
    assert acc_expected == 9 and k["expected"] == 47 + acc_expected, k
    assert snap["periods"]["last_7_days"]["kpis"]["checkins"] == 9
    assert snap["classes"][str(data["cs"])]["kpis"]["checkins"] == 7
    assert {d["department"] for d in snap["classes"][str(data["acc"])]["departments"]} == {"ACC"}

    rules = {a["rule"]: a for a in snap["alerts"]}
    assert set(rules) == {"device_reuse", "shared_ip", "rapid_burst", "nim_guessing", "overlapping_classes"}, rules
    assert set(rules["device_reuse"]["nims"]) == {"2401020110126", "2401020110147", "2401020110059"}
    assert rules["shared_ip"]["occurrences"] == 3
    assert rules["rapid_burst"]["occurrences"] == 2
    assert rules["nim_guessing"]["occurrences"] == 3
    assert rules["overlapping_classes"]["nims"] == ["2403070110002"]
    assert [a["severity"] for a in snap["alerts"]] == sorted(
        (a["severity"] for a in snap["alerts"]), key=gold.SEVERITY_ORDER.get
    )
    assert len(snap["trend"]) == 14 and snap["trend"][-1]["students"] == 7
    assert len(snap["latest"]) == 9

    print("KPIs today:", json.dumps(k))
    for a in snap["alerts"]:
        print(f"  [{a['severity']}] {a['rule']}: {a['detail']}")
    print("ok spark gold test")


if __name__ == "__main__":
    mode, file = sys.argv[1], Path(sys.argv[2])
    export(file) if mode == "export" else check(file)
