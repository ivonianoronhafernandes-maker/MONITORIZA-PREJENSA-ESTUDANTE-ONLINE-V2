"""Konsulta dadus ba dashboard Flask (database/prezensa_tetum.db - dadus Kaggle tradús ba Tetum)."""
from __future__ import annotations

import csv
import io
import os
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = Path(os.getenv("PREZENSA_DB", ROOT / "database" / "prezensa_tetum.db"))
ESTATUTU = ["Prezente", "Atrazadu", "Falta", "Lisensa", "Sai Sedu"]
FILTER = {"prezente": "Prezente", "atrazadu": "Atrazadu", "falta": "Falta", "lisensa": "Lisensa", "saisedu": "Sai Sedu"}
BULAN = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
LOROON = ["Seg", "Ter", "Kua", "Kin", "Sex", "Sab", "Dom"]
_cache: dict = {}


def conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    return c


def rows(sql: str, params: tuple = ()) -> list[dict]:
    with conn() as c:
        return [dict(r) for r in c.execute(sql, params)]


def one(sql: str, params: tuple = ()) -> dict:
    r = rows(sql, params)
    return r[0] if r else {}


def ready() -> bool:
    if not DB.exists():
        return False
    try:
        return one("SELECT COUNT(*) n FROM prezensa")["n"] > 0
    except sqlite3.Error:
        return False


def cached(key: str):
    """Hasoru dadus ba database nia mtime: dadus foun -> kalkula fali."""
    stamp = DB.stat().st_mtime if DB.exists() else 0
    def deco(fn):
        def wrap(*a):
            k = (key, a, stamp)
            if k not in _cache:
                _cache[k] = fn(*a)
            return _cache[k]
        return wrap
    return deco


def pct(a: float, b: float) -> float:
    return round(100 * a / b, 1) if b else 0.0


def fmt_data(d: str) -> str:
    return f"{d[8:10]}/{d[5:7]}/{d[0:4]}" if d and len(d) >= 10 else (d or "")


@cached("totals")
def totals() -> dict:
    cnt = {r["estatutu"]: r["n"] for r in rows("SELECT estatutu, COUNT(*) n FROM prezensa GROUP BY estatutu")}
    total = sum(cnt.values())
    rng = one("SELECT MIN(data) a, MAX(data) b FROM prezensa")
    end = datetime.strptime(rng["b"], "%Y-%m-%d").date() if rng.get("b") else date.today()
    cut1, cut0 = (end - timedelta(days=30)).isoformat(), (end - timedelta(days=60)).isoformat()
    cur = one("SELECT COUNT(*) n FROM prezensa WHERE data > ?", (cut1,))["n"]
    prev = one("SELECT COUNT(*) n FROM prezensa WHERE data > ? AND data <= ?", (cut0, cut1))["n"]
    out = {"total": total, "estudante": one("SELECT COUNT(*) n FROM estudante")["n"], "hahu": rng.get("a"), "remata": rng.get("b"),
           "kresimentu": round(100 * (cur - prev) / prev, 1) if prev else 0.0}
    for s in ESTATUTU:
        out[s] = cnt.get(s, 0)
        out["p_" + s] = pct(cnt.get(s, 0), total)
    return out


@cached("series")
def series(periodu: str) -> dict:
    if periodu == "tinan":
        grp, lab = "substr(data,1,4)", lambda k: k
    elif periodu == "fulan":
        grp, lab = "substr(data,1,7)", lambda k: f"{BULAN[int(k[5:7]) - 1]} {k[2:4]}"
    else:
        grp, lab = "((CAST(strftime('%w', data) AS INTEGER) + 6) % 7)", lambda k: LOROON[int(k)]
    rs = rows(f"SELECT {grp} g, estatutu, COUNT(*) n FROM prezensa GROUP BY g, estatutu ORDER BY g")
    keys = sorted({str(r["g"]) for r in rs}, key=lambda k: int(k) if periodu == "semana" else k)
    tot = {k: 0 for k in keys}
    by = {k: {} for k in keys}
    for r in rs:
        k = str(r["g"])
        tot[k] += r["n"]
        by[k][r["estatutu"]] = r["n"]
    return {"label": [lab(k) for k in keys],
            "prezente": [pct(by[k].get("Prezente", 0), tot[k]) for k in keys],
            "atrazadu": [pct(by[k].get("Atrazadu", 0), tot[k]) for k in keys],
            "falta": [pct(by[k].get("Falta", 0), tot[k]) for k in keys]}


@cached("insights")
def insights() -> dict:
    t = totals()
    end = datetime.strptime(t["remata"], "%Y-%m-%d").date()
    c1, c0 = (end - timedelta(days=30)).isoformat(), (end - timedelta(days=60)).isoformat()
    def share(lo: str, hi: str) -> dict:
        rs = rows("SELECT estatutu, COUNT(*) n FROM prezensa WHERE data > ? AND data <= ? GROUP BY estatutu", (lo, hi))
        tt = sum(r["n"] for r in rs)
        return {r["estatutu"]: pct(r["n"], tt) for r in rs}
    cur, prev = share(c1, end.isoformat()), share(c0, c1)
    out = []
    for key, lab, good_up in (("Prezente", "Prezensa Média", True), ("Atrazadu", "Estudante Atrazu (Late)", False), ("Falta", "Estudante La Prezente", False)):
        v = cur.get(key, 0.0)
        d = round(v - prev.get(key, 0.0), 1)
        out.append({"label": lab, "valor": v, "delta": d, "bom": (d >= 0) == good_up})
    return {"items": out}


def dashboard(periodu: str = "semana") -> dict:
    return {"totals": totals(), "series": series(periodu), "insights": insights()["items"]}


def _where(estatutu: str = "", q: str = "", disiplina: str = "", klase: str = "", dari: str = "", too: str = "") -> tuple[str, list]:
    w, p = [], []
    if estatutu in FILTER:
        w.append("p.estatutu = ?"); p.append(FILTER[estatutu])
    if q:
        w.append("(e.naran LIKE ? OR p.id_estudante LIKE ?)"); p += [f"%{q}%", f"%{q.upper()}%"]
    if disiplina:
        w.append("p.disiplina = ?"); p.append(disiplina)
    if klase:
        w.append("e.klase = ?"); p.append(klase)
    if dari:
        w.append("p.data >= ?"); p.append(dari)
    if too:
        w.append("p.data <= ?"); p.append(too)
    return (" WHERE " + " AND ".join(w)) if w else "", p


def prezensa(page: int = 1, size: int = 5, **f) -> dict:
    wh, p = _where(**f)
    join = "FROM prezensa p LEFT JOIN estudante e ON e.id = p.id_estudante"
    # kontajen: se la iha filtru, uza total ne'ebé kalkula ona (lalais)
    if not wh:
        n = totals()["total"]
    elif f.get("estatutu") in FILTER and not any(f.get(k) for k in ("q", "disiplina", "klase", "dari", "too")):
        n = totals()[FILTER[f["estatutu"]]]
    else:
        n = one(f"SELECT COUNT(*) n {join}{wh}", tuple(p))["n"]
    page = max(1, page)
    rs = rows(f"SELECT p.id, e.naran, p.id_estudante nim, e.klase, p.disiplina, p.data, p.oras, p.estatutu {join}{wh} "
              f"ORDER BY p.data DESC, p.id DESC LIMIT ? OFFSET ?", tuple(p) + (size, (page - 1) * size))
    for i, r in enumerate(rs):
        r["no"] = (page - 1) * size + i + 1
        r["data"] = fmt_data(r["data"])
        r["oras"] = r["oras"] or "—"
        r["naran"] = r["naran"] or "-"
    return {"rows": rs, "total": n, "page": page, "size": size, "pages": max(1, -(-n // size))}


def prezensa_csv(**f) -> bytes:
    wh, p = _where(**f)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["NIM", "Naran Estudante", "Klase", "Disiplina", "Data", "Oras", "Estatutu"])
    with conn() as c:
        for r in c.execute("SELECT p.id_estudante, e.naran, e.klase, p.disiplina, p.data, p.oras, p.estatutu FROM prezensa p "
                           f"LEFT JOIN estudante e ON e.id = p.id_estudante{wh} ORDER BY p.data DESC, p.id DESC", tuple(p)):
            w.writerow([r[0], r[1], r[2], r[3], r[4], r[5] or "", r[6]])
    return buf.getvalue().encode("utf-8-sig")


def klase_list() -> list[str]:
    return [r["klase"] for r in rows("SELECT DISTINCT klase FROM estudante WHERE klase <> '' ORDER BY klase")]


def disiplina_list() -> list[str]:
    return [r["disiplina"] for r in rows("SELECT DISTINCT disiplina FROM prezensa ORDER BY disiplina")]


def estudante(page: int = 1, size: int = 10, q: str = "", klase: str = "") -> dict:
    w, p = [], []
    if q:
        w.append("(naran LIKE ? OR id LIKE ?)"); p += [f"%{q}%", f"%{q.upper()}%"]
    if klase:
        w.append("klase = ?"); p.append(klase)
    wh = (" WHERE " + " AND ".join(w)) if w else ""
    n = one(f"SELECT COUNT(*) n FROM estudante{wh}", tuple(p))["n"]
    page = max(1, page)
    rs = rows(f"SELECT id, naran, klase, data_moris, kontaktu FROM estudante{wh} ORDER BY naran LIMIT ? OFFSET ?", tuple(p) + (size, (page - 1) * size))
    if rs:
        ids = [r["id"] for r in rs]
        ph = ",".join("?" * len(ids))
        st = rows(f"SELECT id_estudante i, estatutu, COUNT(*) n FROM prezensa WHERE id_estudante IN ({ph}) GROUP BY i, estatutu", tuple(ids))
        agg: dict = {}
        for r in st:
            agg.setdefault(r["i"], {})[r["estatutu"]] = r["n"]
        for r in rs:
            a = agg.get(r["id"], {})
            tt = sum(a.values())
            r.update(total=tt, prezente=a.get("Prezente", 0), atrazadu=a.get("Atrazadu", 0), falta=a.get("Falta", 0), pct=pct(a.get("Prezente", 0), tt))
            r["data_moris"] = fmt_data(r["data_moris"]) or "-"
    return {"rows": rs, "total": n, "page": page, "size": size, "pages": max(1, -(-n // size))}


@cached("analytics")
def analytics() -> dict:
    def split(group_sql: str, join: str = "") -> list[dict]:
        rs = rows(f"SELECT {group_sql} g, p.estatutu s, COUNT(*) n FROM prezensa p {join} GROUP BY g, s")
        d: dict = {}
        for r in rs:
            d.setdefault(r["g"] or "-", {})[r["s"]] = r["n"]
        out = []
        for g in sorted(d):
            tt = sum(d[g].values())
            out.append({"label": g, "total": tt, "prezente": pct(d[g].get("Prezente", 0), tt), "atrazadu": pct(d[g].get("Atrazadu", 0), tt), "falta": pct(d[g].get("Falta", 0), tt)})
        return out
    top = rows("""SELECT p.id_estudante nim, e.naran, e.klase, COUNT(*) falta FROM prezensa p LEFT JOIN estudante e ON e.id = p.id_estudante
                  WHERE p.estatutu = 'Falta' GROUP BY p.id_estudante ORDER BY falta DESC, e.naran LIMIT 10""")
    nota = rows("SELECT disiplina label, ROUND(AVG(nota_teste), 1) valor FROM dezempenu WHERE nota_teste IS NOT NULL GROUP BY disiplina ORDER BY disiplina")
    tarefa = rows("""SELECT disiplina label, ROUND(100.0 * SUM(estatutu = 'Hotu') / COUNT(*), 1) valor FROM tarefa_uma GROUP BY disiplina ORDER BY disiplina""")
    return {"disiplina": split("p.disiplina"), "klase": split("e.klase", "LEFT JOIN estudante e ON e.id = p.id_estudante"),
            "top_falta": top, "nota": nota, "tarefa": tarefa, "mensajen": one("SELECT COUNT(*) n FROM komunikasaun")["n"]}


def estudante_csv(q: str = "", klase: str = "") -> bytes:
    w, p = [], []
    if q:
        w.append("(naran LIKE ? OR id LIKE ?)"); p += [f"%{q}%", f"%{q.upper()}%"]
    if klase:
        w.append("klase = ?"); p.append(klase)
    wh = (" WHERE " + " AND ".join(w)) if w else ""
    buf = io.StringIO()
    wr = csv.writer(buf)
    wr.writerow(["NIM", "Naran Estudante", "Klase", "Data Moris", "Kontaktu", "Total Prezensa", "Prezente", "Atrazadu", "Falta", "Prezente %"])
    with conn() as c:
        for r in c.execute(f"""SELECT e.id, e.naran, e.klase, e.data_moris, e.kontaktu, COUNT(p.id), SUM(p.estatutu='Prezente'),
                SUM(p.estatutu='Atrazadu'), SUM(p.estatutu='Falta') FROM estudante e LEFT JOIN prezensa p ON p.id_estudante = e.id{wh}
                GROUP BY e.id ORDER BY e.naran""", tuple(p)):
            tt = r[5] or 0
            wr.writerow([*r[:5], tt, r[6] or 0, r[7] or 0, r[8] or 0, pct(r[6] or 0, tt)])
    return buf.getvalue().encode("utf-8-sig")
