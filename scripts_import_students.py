"""Convert the DIT "Estudante Ativu" Excel list (one sheet per faculty) into data/raw/student.csv.

Usage:  python scripts_import_students.py [file.xls|file.xlsx]

Rows without a valid registration number (e.g. "Komfirmasaun") are skipped because a student
needs a NIM to check in. Duplicate NIMs are kept once. Needs xlrd for .xls (pip install xlrd) or an .xlsx file.
"""
from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
DEFAULT_SRC = ROOT / "data" / "raw" / "Estudante_Ativu_DIT_Central__ba_Anu_Letivu_2024_Abril.xls"
OUT = ROOT / "data" / "raw" / "student.csv"
NIM_OK = re.compile(r"^\d[\d.\-/]*\d$")
COLUMNS = ["Cap waktu", "Naran Kompletu", "Nim", "Sexu", "Fakuldade", "Departamentu", "Turno", "Email"]


def read_sheet(df: pd.DataFrame) -> pd.DataFrame:
    header_row = next(i for i in range(len(df)) if str(df.iat[i, 1]).strip().lower().startswith("naran estudante"))
    body = df.iloc[header_row + 1:]
    rows = []
    for _, r in body.iterrows():
        no, name = str(r[0]).strip(), str(r[1]).strip()
        if not re.fullmatch(r"\d+(\.0)?", no) or not name or name.lower() == "nan":
            continue
        sex = next((str(v).strip().upper() for v in (r[3], r[4]) if pd.notna(v) and str(v).strip()), "")
        rows.append(
            {
                "name": name, "nim": str(r[5]).strip() if pd.notna(r[5]) else "", "sex": sex,
                "faculty": str(r[6]).strip(), "department": str(r[7]).strip(),
                "cohort": re.sub(r"\.0$", "", str(r[10]).strip()) if pd.notna(r[10]) else "",
            }
        )
    return pd.DataFrame(rows)


def main(src: Path) -> None:
    sheets = pd.read_excel(src, sheet_name=None, header=None)
    stamp = f"{datetime.now():%Y/%m/%d %I:%M:%S %p} GMT+9"
    frames, report = [], []
    for name, raw in sheets.items():
        part = read_sheet(raw)
        report.append((name.strip(), len(part)))
        frames.append(part)
    df = pd.concat(frames, ignore_index=True)
    total = len(df)
    df = df[df["nim"].map(lambda v: bool(NIM_OK.match(v)))]
    no_nim = total - len(df)
    df["key"] = df["nim"].str.replace(r"\s+", "", regex=True).str.upper()
    dups = int(df.duplicated("key").sum())
    df = df.drop_duplicates("key")
    out = pd.DataFrame(
        {
            "Cap waktu": stamp, "Naran Kompletu": df["name"], "Nim": df["nim"], "Sexu": df["sex"].map({"M": "Mane", "F": "Feto"}).fillna(""),
            "Fakuldade": df["faculty"], "Departamentu": df["department"], "Turno": df["cohort"], "Email": "",
        }
    )[COLUMNS]
    out.to_csv(OUT, index=False, quoting=1, encoding="utf-8")
    for n, c in report:
        print(f"{n}: {c} students")
    print(f"Total rows: {total} | without valid NIM (skipped): {no_nim} | duplicate NIM (skipped): {dups} | written: {len(out)} -> {OUT}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SRC)
