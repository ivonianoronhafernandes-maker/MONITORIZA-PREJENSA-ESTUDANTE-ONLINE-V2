"""Start Flask (dashboard, port 5000) and Streamlit (check-in + management, port 8501) together.

    python run_all.py
"""
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
procs = [
    subprocess.Popen([sys.executable, str(ROOT / "flask_app" / "app.py")], cwd=ROOT),
    subprocess.Popen([sys.executable, "-m", "streamlit", "run", "App.py", "--server.port", "8501", "--server.headless", "true"], cwd=ROOT),
]
print("\nFlask dashboard : http://127.0.0.1:5000/dashboard\nStreamlit       : http://127.0.0.1:8501\nCtrl+C atu para.\n")
time.sleep(3)
webbrowser.open("http://127.0.0.1:5000/dashboard")  # Flask dashboard opens first
try:
    while all(p.poll() is None for p in procs):
        time.sleep(1)
except KeyboardInterrupt:
    pass
finally:
    for p in procs:
        if p.poll() is None:
            p.terminate()
