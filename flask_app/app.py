"""Dashboard Flask (porta 5000) - Student Attendance Analytics, tuir desene UI foun, lian Tetum.

    python flask_app/app.py        (ka  python run_all.py  atu lao Flask + Streamlit hamutuk)
"""
from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

from flask import Flask, Response, jsonify, redirect, render_template, request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from flask_app import data  # noqa: E402

app = Flask(__name__)
LOROON_BOOT = ["Seg", "Ter", "Kua", "Kin", "Sex", "Sab", "Dom"]
FULAN = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


@app.context_processor
def inject():
    t = date.today()
    st = os.getenv("STREAMLIT_URL", "").rstrip("/") or f"http://{request.host.split(':')[0]}:8501"
    return {"embed": request.args.get("embed") == "1", "st_url": st, "ohin": f"{LOROON_BOOT[t.weekday()]}, {t.day:02d} {FULAN[t.month - 1]} {t.year}",
            "ready": data.ready(), "user": "Admin"}


@app.get("/favicon.ico")
def favicon():
    return app.send_static_file("favicon.ico")


@app.get("/")
def home():
    return redirect("/dashboard")


@app.get("/dashboard")
def dashboard():
    return render_template("dashboard.html", active="dashboard", d=data.dashboard() if data.ready() else None)


@app.get("/api/dashboard")
def api_dashboard():
    p = request.args.get("periodu", "semana")
    return jsonify(data.dashboard(p if p in ("semana", "fulan", "tinan") else "semana"))


def _f() -> dict:
    a = request.args
    return {"estatutu": a.get("estatutu", ""), "q": a.get("q", "").strip(), "disiplina": a.get("disiplina", ""), "klase": a.get("klase", ""),
            "dari": a.get("dari", ""), "too": a.get("too", "")}


def _int(name: str, default: int, lo: int, hi: int) -> int:
    try:
        return min(max(int(request.args.get(name, default)), lo), hi)
    except ValueError:
        return default


@app.get("/api/prezensa")
def api_prezensa():
    return jsonify(data.prezensa(_int("page", 1, 1, 10**7), _int("size", 5, 1, 100), **_f()))


@app.get("/prezensa")
def prezensa():
    return render_template("prezensa.html", active="prezensa", klases=data.klase_list(), disiplinas=data.disiplina_list())


@app.get("/export/prezensa.csv")
def export_prezensa():
    return Response(data.prezensa_csv(**_f()), mimetype="text/csv", headers={"Content-Disposition": 'attachment; filename="relatoriu_prezensa.csv"'})


@app.get("/estudante")
def estudante():
    return render_template("estudante.html", active="estudante", klases=data.klase_list())


@app.get("/api/estudante")
def api_estudante():
    return jsonify(data.estudante(_int("page", 1, 1, 10**7), _int("size", 10, 1, 100), request.args.get("q", "").strip(), request.args.get("klase", "")))


@app.get("/export/estudante.csv")
def export_estudante():
    return Response(data.estudante_csv(request.args.get("q", "").strip(), request.args.get("klase", "")), mimetype="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="relatoriu_estudante.csv"'})


@app.get("/analytics")
def analytics():
    return render_template("analytics.html", active="analytics", a=data.analytics() if data.ready() else None, t=data.totals() if data.ready() else None)


@app.get("/relatoriu")
def relatoriu():
    return render_template("relatoriu.html", active="relatoriu", klases=data.klase_list(), disiplinas=data.disiplina_list(), t=data.totals() if data.ready() else None)


@app.get("/konfigurasaun")
def konfigurasaun():
    return render_template("konfigurasaun.html", active="konfigurasaun", t=data.totals() if data.ready() else None)


if __name__ == "__main__":
    app.run(host=os.getenv("FLASK_HOST", "0.0.0.0"), port=int(os.getenv("FLASK_PORT", "5000")), debug=False, threaded=True)
