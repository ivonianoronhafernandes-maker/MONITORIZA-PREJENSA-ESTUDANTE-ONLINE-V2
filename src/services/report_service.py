"""Downloadable attendance reports (CSV). Generated reports are kept in ./reports for the Recent Reports list."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from src.core.config import BASE_DIR
from src.services import stats_service

REPORTS_DIR = BASE_DIR / "reports"
KINDS = {
    "Student Attendance Report": "Student",
    "Class Report": "Class",
    "Daily Report": "Daily",
    "Summary Report": "Summary",
}


def _pct(series: pd.Series) -> pd.Series:
    return (series * 100).round(1)


def build(kind: str, start: str, end: str, class_title: str | None = None, nim: str | None = None) -> pd.DataFrame:
    """Return the report table for ``kind`` ("Student", "Class", "Daily" or "Summary")."""
    if kind == "Student":
        df = stats_service.student_rates(start, end, class_title)
        if nim:
            df = df[df["nim"] == nim]
        df = df.assign(rate=_pct(df["rate"])).sort_values("name")
        return df[["nim", "name", "gender", "department", "cohort", "held", "attended", "on_time", "late", "absent", "rate"]].rename(
            columns={"nim": "Student ID", "name": "Name", "gender": "Gender", "department": "Dept", "cohort": "Cohort",
                     "held": "Meetings", "attended": "Attended", "on_time": "On time", "late": "Late", "absent": "Absent",
                     "rate": "Attendance rate (%)"}
        )
    if kind == "Class":
        df = stats_service.class_summary(start, end, class_title)
        df = df.assign(rate=_pct(df["rate"]))
        return df.rename(columns={"class_title": "Class", "session_date": "Date", "time": "Time", "expected": "Expected",
                                  "attended": "Attended", "on_time": "On time", "late": "Late", "absent": "Absent",
                                  "rate": "Attendance rate (%)"})
    if kind == "Daily":
        df = stats_service.daily_summary(start, end, class_title)
        df = df.assign(rate=_pct(df["rate"]))
        return df.rename(columns={"date": "Date", "meetings": "Meetings", "expected": "Expected", "attended": "Attended",
                                  "on_time": "On time", "late": "Late", "absent": "Absent", "rate": "Attendance rate (%)"})
    if kind == "Summary":
        people = stats_service.student_rates(start, end, class_title)
        g = people.groupby("department", as_index=False)[["held", "attended", "late", "absent"]].sum()
        g.loc[len(g)] = ["All departments", *g[["held", "attended", "late", "absent"]].sum()]
        g["rate"] = _pct((g["attended"] / g["held"].where(g["held"] > 0)).fillna(0.0))
        return g.rename(columns={"department": "Department", "held": "Expected attendance", "attended": "Attended",
                                 "late": "Late", "absent": "Absent", "rate": "Attendance rate (%)"})
    raise ValueError(f"Unknown report type: {kind}")


def save(kind: str, start: str, end: str, df: pd.DataFrame) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"{kind}_Attendance_Report_{start}_to_{end}.csv"
    df.to_csv(path, index=False)
    return path


def recent(limit: int = 5) -> list[dict]:
    if not REPORTS_DIR.exists():
        return []
    files = sorted(REPORTS_DIR.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    return [
        {"name": p.name, "type": p.name.split("_")[0], "date": datetime.fromtimestamp(p.stat().st_mtime), "path": p}
        for p in files
    ]


# ---- Reports page: summary + per-student preview + PDF / Excel export --------------------------------

PREVIEW_COLUMNS = ["Naran Estudante", "Klase", "Prezente", "Falta", "Atrazu", "Taxa"]


def student_report(start: str, end: str, class_name: str | None = None, subject: str | None = None) -> pd.DataFrame:
    """One row per student: Present (on time), Absent, Late and attendance rate (a 0..1 fraction)."""
    people = stats_service.student_rates(start, end, class_name=class_name, subject=subject)
    people = people[people["held"] > 0] if (class_name or subject) else people
    out = pd.DataFrame(
        {
            "Naran Estudante": people["name"], "Klase": people["student_class"], "Prezente": people["on_time"],
            "Falta": people["absent"], "Atrazu": people["late"], "Taxa": people["rate"],
        }
    )
    return out.sort_values("Naran Estudante").reset_index(drop=True)


def summary(report: pd.DataFrame, total_students: int) -> dict:
    present, late, absent = int(report["Prezente"].sum()), int(report["Atrazu"].sum()), int(report["Falta"].sum())
    expected = present + late + absent
    return {
        "students": total_students, "present": present, "absent": absent, "late": late,
        "rate": (present + late) / expected if expected else 0.0,
    }


def to_excel(report: pd.DataFrame, info: dict, title: str) -> bytes:
    """Excel workbook: a Summary sheet and a Students sheet."""
    import io

    out = io.BytesIO()
    table = report.assign(Taxa=report["Taxa"].round(4))
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        pd.DataFrame(
            {"Item": ["Relatóriu", "Total Estudante", "Prezente", "Falta", "Atrazu", "Taxa Prezensa"],
             "Valór": [title, info["students"], info["present"], info["absent"], info["late"], f"{info['rate']:.1%}"]}
        ).to_excel(writer, sheet_name="Rezumu", index=False)
        table.to_excel(writer, sheet_name="Estudante", index=False)
        sheet = writer.sheets["Estudante"]
        for row in sheet.iter_rows(min_row=2, min_col=6, max_col=6):
            for cell in row:
                cell.number_format = "0.0%"
        for ws in writer.book.worksheets:
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = min(max(len(str(c.value or "")) for c in col) + 3, 46)
    return out.getvalue()


def to_pdf(report: pd.DataFrame, info: dict, title: str) -> bytes:
    """A4 PDF: title, summary line and the per-student table (repeating header across pages)."""
    import io
    from xml.sax.saxutils import escape

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36, title=title)
    styles = getSampleStyleSheet()
    story = [
        Paragraph(escape(title), styles["Title"]),
        Paragraph(
            f"Total estudante: {info['students']} &nbsp;|&nbsp; Prezente: {info['present']} &nbsp;|&nbsp; "
            f"Falta: {info['absent']} &nbsp;|&nbsp; Atrazu: {info['late']} &nbsp;|&nbsp; Taxa prezensa: {info['rate']:.1%}",
            styles["Normal"],
        ),
        Spacer(1, 12),
    ]
    rows = [PREVIEW_COLUMNS] + [
        [str(r["Naran Estudante"]), str(r["Klase"]), int(r["Prezente"]), int(r["Falta"]), int(r["Atrazu"]), f"{r['Taxa']:.0%}"]
        for _, r in report.iterrows()
    ]
    if len(rows) == 1:
        story.append(Paragraph("La iha data prezensa ba seleisaun ne'e.", styles["Normal"]))
    else:
        table = Table(rows, repeatRows=1, colWidths=[190, 80, 55, 55, 45, 50])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0a1f4d")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f7fc")]),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d5deee")), ("ALIGN", (2, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        story.append(table)
    doc.build(story)
    return buf.getvalue()
