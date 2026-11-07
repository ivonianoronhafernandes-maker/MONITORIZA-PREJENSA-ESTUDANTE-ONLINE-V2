"""Starts Kafka + Spark (docker compose) together with the Streamlit app.

Runs in a background thread so the app opens immediately; the dashboard shows
the progress. Nothing here blocks check-ins: events wait in the outbox until
Kafka is up.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from src.core.config import BASE_DIR, settings

logger = logging.getLogger("attendance.infrastructure")

# Hide the console windows that docker.exe would open on Windows.
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def _run(*args: str, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        list(args), cwd=BASE_DIR, capture_output=True, text=True, timeout=timeout, creationflags=_NO_WINDOW
    )


def docker_running() -> bool:
    try:
        return _run("docker", "info", "--format", "{{.ServerVersion}}", timeout=20).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _docker_desktop_exe() -> Path | None:
    docker = shutil.which("docker")
    candidates = []
    if docker:  # ...\DockerDesktop\resources\bin\docker.exe -> ...\DockerDesktop\Docker Desktop.exe
        candidates.append(Path(docker).resolve().parents[2] / "Docker Desktop.exe")
    candidates.append(Path(r"C:\Program Files\Docker\Docker\Docker Desktop.exe"))
    return next((c for c in candidates if c.exists()), None)


class PipelineLauncher(threading.Thread):
    """Brings up the docker compose services and reports progress."""

    STATES = ("waiting", "starting_docker", "starting_containers", "waiting_kafka", "running", "stopped", "error", "disabled")

    def __init__(self, timeout_seconds: int = 240):
        super().__init__(name="pipeline-launcher", daemon=True)
        self.timeout_seconds = timeout_seconds
        self.state = "waiting"
        self.message = "Checking Docker, Kafka and Spark..."
        self.updated_at = time.time()
        self._lock = threading.Lock()

    def _set(self, state: str, message: str) -> None:
        self.state, self.message, self.updated_at = state, message, time.time()
        log = logger.error if state == "error" else logger.info
        log("pipeline: %s", message)

    def run(self) -> None:
        with self._lock:
            try:
                self._start()
            except Exception as exc:  # never crash the app because of Docker
                self._set("error", f"Could not start Kafka/Spark: {exc}")

    def _start(self) -> None:
        if not shutil.which("docker"):
            self._set("error", "Docker is not installed. Install Docker Desktop to run Kafka and Spark.")
            return

        deadline = time.time() + self.timeout_seconds
        if not docker_running():
            exe = _docker_desktop_exe()
            if exe is None:
                self._set("error", "Docker is not running and Docker Desktop was not found. Start Docker manually.")
                return
            self._set("starting_docker", "Starting Docker Desktop (can take a minute)...")
            subprocess.Popen([str(exe)], creationflags=_NO_WINDOW)
            while not docker_running():
                if time.time() > deadline:
                    self._set("error", "Docker Desktop did not start in time. Start it manually, then press Start in Settings.")
                    return
                time.sleep(3)

        self._set("starting_containers", "Starting Kafka, Kafka UI and Spark (docker compose up -d)...")
        result = _run("docker", "compose", "up", "-d", timeout=self.timeout_seconds)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip().splitlines()[-3:]
            self._set("error", "docker compose up failed: " + " | ".join(detail))
            return

        self._set("waiting_kafka", "Waiting for Kafka to be ready...")
        while not self._kafka_healthy():
            if time.time() > deadline:
                self._set("error", "Kafka did not become healthy in time. Check: docker compose logs kafka")
                return
            time.sleep(3)
        self._set("running", "Kafka and Spark are running.")

    def _kafka_healthy(self) -> bool:
        cid = _run("docker", "compose", "ps", "-q", "kafka").stdout.strip()
        if not cid:
            return False
        health = _run("docker", "inspect", "--format", "{{.State.Health.Status}}", cid).stdout.strip()
        return health == "healthy"

    def status(self) -> dict:
        return {"state": self.state, "message": self.message, "updated_at": self.updated_at}


_launcher: PipelineLauncher | None = None
_launcher_lock = threading.Lock()


def start(force: bool = False) -> PipelineLauncher:
    """Start (or restart) the launcher thread; safe to call on every page run."""
    global _launcher
    with _launcher_lock:
        if _launcher is None or (force and not _launcher.is_alive()):
            _launcher = PipelineLauncher()
            if settings.auto_start_pipeline or force:
                _launcher.start()
            else:
                _launcher._set("disabled", "Auto start is off (AUTO_START_PIPELINE=0). Use Start in Settings.")
        return _launcher


def stop() -> None:
    """Stop Kafka, Kafka UI and Spark (data is kept in Docker volumes)."""
    launcher = start()
    result = _run("docker", "compose", "stop", timeout=120)
    if result.returncode == 0:
        launcher._set("stopped", "Kafka and Spark are stopped. Press Start to run them again.")
    else:
        launcher._set("error", "docker compose stop failed: " + (result.stderr or "").strip()[-200:])


def status() -> dict:
    return start().status()
