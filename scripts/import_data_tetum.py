"""Importa data/tetum/*.csv (dadus Kaggle ne'ebé tradús ba Tetum) ba database/prezensa_tetum.db.

    python scripts/import_data_tetum.py
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "tetum"
DB = ROOT / "database" / "prezensa_tetum.db"

SCHEMA = """
DROP TABLE IF EXISTS estudante; DROP TABLE IF EXISTS prezensa; DROP TABLE IF EXISTS dezempenu;
DROP TABLE IF EXISTS tarefa_uma; DROP TABLE IF EXISTS komunikasaun;
CREATE TABLE estudante (id TEXT PRIMARY KEY, naran TEXT, data_moris TEXT, klase TEXT, kontaktu TEXT);
CREATE TABLE prezensa (id INTEGER PRIMARY KEY AUTOINCREMENT, id_estudante TEXT, data TEXT, disiplina TEXT, estatutu TEXT, oras TEXT);
CREATE TABLE dezempenu (id_estudante TEXT, disiplina TEXT, nota_teste REAL, hotu_tarefa REAL, komentariu TEXT);
CREATE TABLE tarefa_uma (id_estudante TEXT, disiplina TEXT, naran_tarefa TEXT, data_prazu TEXT, estatutu TEXT, nota TEXT, asinatura TEXT);
CREATE TABLE komunikasaun (id_estudante TEXT, data TEXT, tipu TEXT, konteudu TEXT);
"""
INDEX = """
CREATE INDEX ix_p_data ON prezensa(data); CREATE INDEX ix_p_est ON prezensa(estatutu);
CREATE INDEX ix_p_id ON prezensa(id_estudante); CREATE INDEX ix_p_dis ON prezensa(disiplina);
CREATE INDEX ix_e_klase ON estudante(klase); CREATE INDEX ix_d_id ON dezempenu(id_estudante);
CREATE INDEX ix_t_id ON tarefa_uma(id_estudante);
"""


def clock(status: pd.Series, rng: np.random.Generator) -> list:
    """Dadus Kaggle la iha oras: kria oras tuir estatutu (Prezente 07:40-08:10, Atrazadu 08:16-08:50)."""
    ranges = {"Prezente": (460, 490), "Sai Sedu": (465, 490), "Atrazadu": (496, 530)}
    out = []
    for s in status:
        if s in ranges:
            m = int(rng.integers(*ranges[s]))
            out.append(f"{m // 60:02d}:{m % 60:02d}")
        else:
            out.append(None)  # Falta / Lisensa = la iha oras
    return out


def main() -> None:
    DB.parent.mkdir(exist_ok=True)
    rng = np.random.default_rng(2026)
    con = sqlite3.connect(DB)
    con.executescript(SCHEMA)
    e = pd.read_csv(SRC / "estudante.csv", dtype=str).fillna("")
    e.columns = ["id", "naran", "data_moris", "klase", "kontaktu"]
    e.to_sql("estudante", con, if_exists="append", index=False)
    p = pd.read_csv(SRC / "prezensa.csv", dtype=str)
    p.columns = ["id_estudante", "data", "disiplina", "estatutu"]
    p = p.sort_values(["data", "id_estudante"]).reset_index(drop=True)
    p["oras"] = clock(p["estatutu"], rng)
    p.to_sql("prezensa", con, if_exists="append", index=False)
    d = pd.read_csv(SRC / "dezempeñu.csv")
    d.columns = ["id_estudante", "disiplina", "nota_teste", "hotu_tarefa", "komentariu"]
    d.to_sql("dezempenu", con, if_exists="append", index=False)
    t = pd.read_csv(SRC / "tarefa_uma.csv", dtype=str).fillna("")
    t.columns = ["id_estudante", "disiplina", "naran_tarefa", "data_prazu", "estatutu", "nota", "asinatura"]
    t.to_sql("tarefa_uma", con, if_exists="append", index=False)
    k = pd.read_csv(SRC / "komunikasaun_mestre_inan_aman.csv", dtype=str).fillna("")
    k.columns = ["id_estudante", "data", "tipu", "konteudu"]
    k.to_sql("komunikasaun", con, if_exists="append", index=False)
    con.executescript(INDEX)
    con.commit()
    for tb in ("estudante", "prezensa", "dezempenu", "tarefa_uma", "komunikasaun"):
        print(f"{tb:14s}{con.execute(f'SELECT COUNT(*) FROM {tb}').fetchone()[0]:>9,} rejistu")
    con.execute("VACUUM")
    con.close()
    print("Remata ->", DB)


if __name__ == "__main__":
    sys.exit(main())
