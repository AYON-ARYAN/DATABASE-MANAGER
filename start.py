#!/usr/bin/env python3
"""One-shot launcher for Meridian Data.

Usage:
    python start.py            # build (if needed), start, open browser
    python start.py --rebuild  # force rebuild images
    python start.py --stop     # stop the stack
    python start.py --logs     # tail logs
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND_URL = "http://localhost:8080"
BACKEND_URL = "http://localhost:5001"
READY_TIMEOUT_SEC = 180


def log(msg: str) -> None:
    print(f"[meridian] {msg}", flush=True)


def die(msg: str, code: int = 1) -> None:
    print(f"[meridian] ERROR: {msg}", file=sys.stderr, flush=True)
    sys.exit(code)


def resolve_compose_cmd() -> list[str]:
    if shutil.which("docker") is None:
        die(
            "Docker is not installed or not on PATH.\n"
            "Install Docker Desktop: https://www.docker.com/products/docker-desktop"
        )
    try:
        subprocess.run(
            ["docker", "compose", "version"],
            check=True,
            capture_output=True,
        )
        return ["docker", "compose"]
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    if shutil.which("docker-compose"):
        return ["docker-compose"]
    die(
        "Neither `docker compose` nor `docker-compose` works.\n"
        "Please install/update Docker Desktop."
    )
    return []


def docker_daemon_up() -> bool:
    try:
        subprocess.run(
            ["docker", "info"],
            check=True,
            capture_output=True,
            timeout=10,
        )
        return True
    except Exception:
        return False


def try_start_docker_desktop() -> bool:
    system = platform.system()
    if system == "Darwin":
        app_paths = [
            "/Applications/Docker.app",
            "/Applications/OrbStack.app",
            "/Applications/Rancher Desktop.app",
        ]
        for path in app_paths:
            if Path(path).exists():
                log(f"Launching {Path(path).name}...")
                subprocess.run(["open", "-a", path], check=False)
                return True
    elif system == "Windows":
        candidates = [
            r"C:\Program Files\Docker\Docker\Docker Desktop.exe",
        ]
        for path in candidates:
            if Path(path).exists():
                log("Launching Docker Desktop...")
                subprocess.Popen([path], shell=False)
                return True
    return False


def ensure_docker_running() -> None:
    if docker_daemon_up():
        return
    log("Docker daemon not running — attempting to start it...")
    if not try_start_docker_desktop():
        die(
            "Docker daemon is not running and no Docker Desktop app was found.\n"
            "Install Docker Desktop (https://www.docker.com/products/docker-desktop) "
            "or start it manually, then re-run this script."
        )
    log("Waiting for Docker daemon to come up (this can take ~30s)...")
    deadline = time.time() + 120
    dots = 0
    while time.time() < deadline:
        if docker_daemon_up():
            print()
            log("Docker daemon is up.")
            return
        print(".", end="", flush=True)
        dots += 1
        if dots % 40 == 0:
            print()
        time.sleep(2)
    print()
    die(
        "Docker daemon did not start in time.\n"
        "Open Docker Desktop manually, wait for it to finish starting, then re-run."
    )


def ensure_env_file() -> None:
    env_path = ROOT / ".env"
    example_path = ROOT / ".env.example"
    if env_path.exists():
        return
    if example_path.exists():
        shutil.copy(example_path, env_path)
        log(f"Created .env from .env.example — edit it to add your GROQ_API_KEY.")
    else:
        env_path.write_text("GROQ_API_KEY=\n")
        log("Created empty .env — add GROQ_API_KEY to enable AI features.")


def is_url_ready(url: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return 200 <= resp.status < 500
    except urllib.error.HTTPError as e:
        return 200 <= e.code < 500
    except Exception:
        return False


def wait_until_ready(url: str, label: str, timeout_sec: int = READY_TIMEOUT_SEC) -> bool:
    deadline = time.time() + timeout_sec
    dots = 0
    while time.time() < deadline:
        if is_url_ready(url):
            print()
            log(f"{label} is ready at {url}")
            return True
        print(".", end="", flush=True)
        dots += 1
        if dots % 40 == 0:
            print()
        time.sleep(1.5)
    print()
    return False


def run_compose(compose: list[str], args: list[str], check: bool = True) -> int:
    cmd = compose + args
    log("$ " + " ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT)
    if check and result.returncode != 0:
        die(f"Command failed with exit code {result.returncode}")
    return result.returncode


def cmd_up(compose: list[str], rebuild: bool) -> None:
    ensure_docker_running()
    ensure_env_file()
    args = ["up", "-d"]
    if rebuild:
        args.append("--build")
    else:
        args.append("--build")
    run_compose(compose, args)
    log("Waiting for services to become healthy...")
    backend_ok = wait_until_ready(BACKEND_URL, "Backend")
    frontend_ok = wait_until_ready(FRONTEND_URL, "Frontend")
    if not (backend_ok and frontend_ok):
        log("Services did not become ready in time. Check logs with:")
        log("    python start.py --logs")
        sys.exit(1)
    log(f"Opening {FRONTEND_URL} in your browser...")
    try:
        webbrowser.open(FRONTEND_URL)
    except Exception as e:
        log(f"Could not auto-open browser ({e}). Visit {FRONTEND_URL} manually.")
    log("Meridian is running. Stop it with:  python start.py --stop")


def cmd_down(compose: list[str]) -> None:
    run_compose(compose, ["down"], check=False)
    log("Stopped.")


def cmd_logs(compose: list[str]) -> None:
    run_compose(compose, ["logs", "-f", "--tail=100"], check=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Meridian Data launcher")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--stop", action="store_true", help="Stop the stack")
    group.add_argument("--logs", action="store_true", help="Tail container logs")
    group.add_argument("--rebuild", action="store_true", help="Force rebuild images")
    args = parser.parse_args()

    compose = resolve_compose_cmd()

    if args.stop:
        cmd_down(compose)
    elif args.logs:
        cmd_logs(compose)
    else:
        cmd_up(compose, rebuild=args.rebuild)


if __name__ == "__main__":
    main()
