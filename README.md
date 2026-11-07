# Grupo 1 Attendance - Student Attendance Analytics (Tetum)

**Dashboard foun (Flask, porta 5000)** tuir desene UI: sidebar azul, kartaun estatístika, Grafiku Prezensa (Semana/Fulan/Tinan), Distribuisaun Prezensa, Lista Prezensa Foun, Insights & Analytics. Lian sistema: Tetum.

```powershell
pip install -r requirements.txt
python scripts/import_data_tetum.py     # (opsionál) importa fali data/tetum/*.csv -> database/prezensa_tetum.db
python run_all.py                       # Flask + Streamlit
```
- Dashboard: http://127.0.0.1:5000/dashboard  (loke diretamente, la presiza login)
- Pájina: Dashboard, Prezensa (filtru + CSV), Estudante, Analytics, Relatóriu, Konfigurasaun
- Dadus: 364.680 rejistu prezensa, 12.156 estudante (Kaggle, tradús ba Tetum). Kolumna *Oras* kria automátiku (la iha iha dataset orijinál).
- Dashboard lama sei iha `flask_app_lama/` (backup).

---
# Flask + Streamlit (UI foun)

| Parte | Porta | Servisu |
|---|---|---|
| **Flask** `flask_app/` | 5000 | Dashboard tuir desene UI DIT (`/dashboard`), Monitorizasaun, Estudante, Matéria + API JSON (`/api/...`) |
| **Streamlit** `App.py` | 8501 | Check-in estudante (link/QR), jere estudante, relatóriu, setting; Dashboard la iha iha Streamlit: sempre loke dashboard Flask (`http://<IP>:5000/dashboard`); sidebar Streamlit iha botaun ba dashboard |

```powershell
pip install -r requirements.txt
python scripts/seed_data.py --reset     # dadus SIMULADU > 10.000 rejistu prezensa (hodi teste volume)
python run_all.py                       # lao Flask + Streamlit hamutuk
```
- Dashboard: http://127.0.0.1:5000/dashboard  - Streamlit: http://127.0.0.1:8501
- Dadus real: `python scripts/seed_data.py --reset-only` hamoos simulasaun (database halo backup automátiku).
- Atu Kafka/Spark prosesa dadus simuladu: Streamlit Settings -> *Resend all events to Kafka*.

# Grupo 1 Attendance — Student Attendance System

Streamlit app for online class attendance. Students check in with their NIM through a
class-specific link; admins create classes, share links/QR codes and watch a real-time
analytics dashboard computed by **Kafka + Spark Structured Streaming**, including
detection of proxy attendance ("titip absen").

## Architecture

```
 Student phone ──► Streamlit app ──► SQLite (attendance) + event_outbox
                                           │  background publisher (at-least-once)
                                           ▼
                                   Kafka topic "attendance-events"   (Docker)
                                           │
                                           ▼
                          Spark Structured Streaming  (Docker, micro-batch every 5 s)
                            1. append events to a Parquet event log (bronze)
                            2. clean + de-duplicate (silver)
                            3. analytics + 5 proxy-detection rules (gold)
                                           │
                                           ▼
                           data/spark/analytics.json ──► Admin dashboard
```

The dashboard shows **only** numbers computed by Spark. If Kafka is down, check-ins are
still saved and their events wait in the outbox; they are sent as soon as Kafka is back.
Event ids are deterministic, so re-sent events are never counted twice.

## Quick start (one command)

```powershell
pip install -r requirements.txt     # first time only
streamlit run App.py
```

That is all: when the app starts it brings up **Docker Desktop, Kafka, Kafka UI and Spark
by itself** in the background (`src/streaming/infrastructure.py`). The page opens at once;
the admin Dashboard shows the progress ("Starting Docker Desktop...", "Waiting for Kafka...").
A cold start takes about 2 minutes until Spark results appear.

- `start.bat` (double-click) does the same, plus installs missing packages and checks the port.
- **Admin → Settings** has *Start Kafka & Spark* / *Stop Kafka & Spark* buttons.
- Ctrl+C stops the app; Kafka and Spark keep running so the next start is fast
  (stop them with the Settings button or `stop.bat`; data is kept).
- Set `AUTO_START_PIPELINE=0` to disable the automatic start.

The Streamlit app deliberately runs on the host, not in Docker: inside a Docker Desktop
container it would see Docker's internal IP (wrong QR links for phones) and every student
would appear to come from the same gateway IP (breaking the IP-based proxy detection).

| What | Where |
|---|---|
| Admin | http://localhost:8501/admin — first login `admin` / `admin123`, then change it on **Settings** |
| Kafka UI (topic, messages) | http://localhost:8085 |
| Spark UI (streaming query, micro-batches) | http://localhost:4040 |
| Spark logs | `docker compose logs -f spark` |

Class links automatically use this computer's Wi-Fi address (e.g. `http://192.168.1.42:8501`),
so students' phones on the same Wi-Fi can scan the QR code. If phones cannot connect, allow
Python through Windows Firewall. To use a public domain instead, set `PUBLIC_BASE_URL`.

Stop the pipeline with `docker compose down` (data kept) or `docker compose down -v`
(wipes Kafka and Spark state; then use **Settings → Resend all events to Kafka** to rebuild).

See `.env.example` for every setting.

## Language, look and access

- **Language:** Settings → General → *Lian / Language* switches the whole interface between **Tetum**,
  **English** and **Indonesia**. Texts live in `src/core/i18n_dict.py` (Tetum | English | Indonesia per line).
  The Tetum texts are written in the pages; other languages are applied when the pages are loaded
  (`src/core/i18n.py`). A text missing from the dictionary simply stays in Tetum.
- **Look:** one typeface, plain white/blue layout, no animation.
- **No sign-in:** the admin pages open directly at `/` (the dashboard). Anyone who can reach this address
  can use them, so run it on a trusted network only. Students only use the class link / QR code (`/?class=...`).
- Stored values (Present / Late / Absent) stay in English in the database and CSV imports; imports also
  accept Prezente / Atrazu / Falta.

## Student data

`data/raw/student.csv` holds the students (8,566 from the DIT list *Estudante Ativu DIT Central, Abril 2024*,
four faculty sheets). It was created from `data/raw/Estudante_Ativu_DIT_Central__ba_Anu_Letivu_2024_Abril.xls` with

    python scripts_import_students.py        # needs `pip install xlrd` for .xls (or pass an .xlsx file)

Rows without a valid registration number ("Komfirmasaun", blank) and duplicate NIMs are skipped. Add or edit
single students on the Students page. The previous test data is in `backup_data_lama/`.

## How it works

1. **Admin → Settings → Classes**
   - **Semester courses** (main use): set the weekly schedule once — e.g. Data Mining, Monday +
     Wednesday, 08:30-10:30, from the first to the last day of the semester. Every meeting is
     generated automatically; check-in opens 15 min before each meeting and closes at its end
     time. **One permanent link/QR** for the whole semester always points to today's (or the
     next) meeting. Per course: attendance grade report (on time / late / absent / %),
     meetings list, check-in log with meeting date and exact check-in time (CSV exports),
     cancel a meeting (holiday, not counted), add a student manually as Present or Late,
     pause/resume, new link.
   - **Single sessions**: one meeting with its own link/QR (make-up class, seminar).
2. **Student** opens the link and enters their NIM:
   - NIM found in `student.csv` → **Success**, student data is shown and the attendance is
     saved to the database as *Present* or *Late*.
   - NIM not found → **Confirm your NIM**.
   - Already checked in / link closed / outside class time / wrong department → clear message,
     nothing saved.
   - **One device, one student:** a phone that already checked in one NIM for a class cannot
     check in a different NIM for that class. The admin can still add a student manually.
3. **Admin → Dashboard** (from Spark): Total / Present / Absent / Late cards, attendance trend of the
   last 7 days, status donut, attendance by class and the 5 students with the lowest attendance.
   Refreshes every 5 s.
4. **Admin → Students**: search + Class / Status filters, **Add Student**, view / edit a student;
   table with class, e-mail, attendance rate and Good (≥ 80 %) / Medium (70-79 %) / Low (< 70 %) status.
5. **Admin → Attendance**: check-ins *and* absences for a date range; filter by class, subject and
   status; **Import Data** (CSV: `student_id,class,subject,date,time,status`), export CSV, remove wrong records.
6. **Admin → Analytics** (from Spark): attendance-rate gauge, Total/Present/Absent/Late tiles, trend,
   attendance by class, status donut, students with low attendance and the proxy-attendance alerts.
7. **Admin → Reports**: pick a date range / class / subject, **Generate Report**, then **Export PDF** or
   **Export Excel** (summary + per-student table).
8. **Admin → Settings** (tabs): **General** (system name, academic year, default attendance status,
   language), **Classes** (semester courses, single sessions, links and
   QR codes), **Subjects** (list of subjects), **Database** (Kafka/Spark pipeline, status, backups).

"Absent" is not stored: it is an expected student (their department is allowed in that class)
with no check-in for a meeting that already started.

## Proxy attendance detection (Spark)

| Rule | Severity | Pattern |
|---|---|---|
| `device_reuse` | high | a phone that checked in one student tried to check in others |
| `rapid_burst` | high | different students checked in back-to-back (≤ 20 s) from one IP (window function) |
| `shared_ip` | medium | ≥ 3 different students checked in from one IP address |
| `overlapping_classes` | medium | the same student is present in two classes whose times overlap |
| `nim_guessing` | low | ≥ 3 unknown NIMs tried from one device |

Thresholds are set in `docker-compose.yml` (`SHARED_IP_MIN_STUDENTS`, `BURST_SECONDS`,
`NIM_GUESS_MIN_ATTEMPTS`). Alerts are signals to review, not proof. A student who clears
cookies or switches browser gets a new device id; the IP-based rules cover part of that.

## Project structure

```
App.py                           entry point + page routing
start.bat / start.ps1            one-command start (Docker + Kafka + Spark + app)
stop.bat                         stop Kafka, Kafka UI and Spark
docker-compose.yml               Kafka (KRaft), topic init, Kafka UI, Spark job
.streamlit/config.toml           theme: colours, Plus Jakarta Sans font, dark sidebar
assets/                          logo.svg / icon.svg (sidebar logo)
data/raw/student.csv             student master data (source of truth for NIM lookup)
data/spark/                      Spark output read by the dashboard (analytics.json, spark_status.json)
database/attendance.db           SQLite database (created automatically)
spark_jobs/
  attendance_stream.py           Structured Streaming: Kafka -> bronze log -> snapshot (foreachBatch)
  gold.py                        Spark computations: silver tables, analytics, proxy detection
src/
  core/config.py                 settings from environment variables, local time zone
  core/events.py                 domain events -> outbox
  core/browser.py                cookies (device id, admin session), client IP
  data/student_repository.py     loads + cleans student.csv (dedupe, typo fixes)
  data/database.py               SQLite schema, migrations and helpers
  streaming/outbox.py            transactional outbox
  streaming/kafka_publisher.py   background thread: outbox -> Kafka
  streaming/backfill.py          puts pre-existing rows into the outbox
  streaming/runtime.py           starts the publisher once per Streamlit server
  streaming/infrastructure.py    starts Docker Desktop + docker compose together with the app
  services/class_service.py      class sessions, tokens, links, session events
  services/course_service.py     semester courses: meeting generation, current meeting, grade report
  services/attendance_service.py check-in rules, attendance/attempt events
  services/spark_analytics.py    reads Spark results for the dashboard
  services/analytics_service.py  class roster (who has not checked in yet)
  services/auth_service.py       admin accounts and sign-in
  ui/components.py               shared CSS, live clock, confetti, chart styling, QR
  ui/theme.py                    admin look: navy sidebar, pastel KPI cards, tables, pills, donut
  ui/shell.py                    top bar (search, alerts, account) and sidebar status
  services/stats_service.py      per-student / per-class / per-day statistics from the database
  services/dashboard_views.py    shapes the Spark snapshot for the dashboard and analytics pages
  services/report_service.py     CSV reports
  ui/student/checkin_page.py     student check-in page
  ui/admin/*.py                  dashboard, students, classes, attendance, analytics, reports, settings, login
tests/test_attendance.py         app tests (python tests/test_attendance.py)
tests/test_spark_gold.py         Spark tests (export on host, check in Docker - see file header)
```

## Kafka events (topic `attendance-events`, key = class id)

| Event | Sent when |
|---|---|
| `class_session.created` | a class is created (includes expected students per department) |
| `class_session.deleted` | a class is deleted |
| `attendance.recorded` | a student is checked in (student data, status, device id, IP) |
| `attendance.deleted` | an admin removes a record |
| `attendance.checkin_attempted` | every attempt, including failures (result, device id, IP) |

## Tests

```powershell
python tests\test_attendance.py                                  # app
python tests\test_spark_gold.py export data\spark\test_events.json  # Spark, step 1 (host)
docker compose run --rm --no-deps -T spark-test                  # Spark, step 2 (Docker)
```

## Data cleaning applied to student.csv

- Tetum headers mapped to `nim, name, gender, faculty, department, cohort, registered_at`.
- Duplicate submissions of the same NIM → latest kept.
- `Mane/Feto/Fero` → `Male/Female`; `Bunesse and Management` → `Business and Management`.
- Names trimmed and title-cased; NIM lookups ignore spaces and letter case.

## Performance note

On a 4-core laptop Spark recomputes the snapshot in about 6 s once warmed up (the first
micro-batches after start are slower while the JVM warms up), so a check-in reaches the
dashboard within roughly 5–15 s.
\n## UI attendance analytics (update)\n\nThe Flask UI now includes **Dashboard, Monitorizasaun, Estudante, Matéria, Analytics, Data Import, Data Pipeline, Relatóriu, and Settings**. The dashboard is intentionally attendance-first and shows an empty state until attendance records are supplied.\n\n**Data status:** `data/raw/student.csv` contains **10,164 student records**. These are student master records, not attendance records. The SQLite `attendance` table currently has **0 attendance records** in the supplied database. The 10,164 student list has not been converted into attendance history; no attendance data was fabricated or imported by this UI update. The Data Import page is a placeholder until the actual attendance list is available.\n