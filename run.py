#!/usr/bin/env python3
"""
AstroVed AI Chatbot — Unified Application Launcher
Supports both development (FastAPI + Vite dev server) and production (FastAPI single-service SPA).

Usage:
  Development : uv run python run.py
  Production  : uv run python run.py --prod
"""

import os
import sys
import time
import signal
import shutil
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"
ENV_FILE = ROOT_DIR / ".env"
FRONTEND_DIST_DIR = FRONTEND_DIR / "dist"


def load_root_env():
    """Load key-value pairs from root .env without overwriting existing environment variables."""
    if not ENV_FILE.is_file():
        return

    with open(ENV_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip("'\"")
            if key not in os.environ:
                os.environ[key] = val


def get_config():
    load_root_env()

    app_env = os.environ.get("APP_ENV") or os.environ.get("ENVIRONMENT") or "development"
    host = os.environ.get("HOST", "127.0.0.1")
    # Render and other cloud platforms provide dynamic PORT
    port_env = os.environ.get("PORT")
    backend_port = int(port_env or os.environ.get("BACKEND_PORT", "8000"))
    frontend_port = int(os.environ.get("FRONTEND_PORT", "5173"))

    return {
        "app_env": app_env,
        "host": host,
        "backend_port": backend_port,
        "frontend_port": frontend_port,
    }


def find_uv():
    uv_bin = shutil.which("uv")
    if uv_bin:
        return uv_bin
    # Common user paths
    user_uv = Path.home() / ".cargo" / "bin" / "uv"
    if user_uv.is_file():
        return str(user_uv)
    return "uv"


def run_production(config):
    index_html = FRONTEND_DIST_DIR / "index.html"
    if not index_html.is_file():
        print("\n" + "=" * 64, file=sys.stderr)
        print("[AstroVed Production] ERROR: Production frontend build not found at frontend/dist.", file=sys.stderr)
        print("[AstroVed Production] A one-time frontend build is required before production startup:", file=sys.stderr)
        print("                      cd frontend && npm run build", file=sys.stderr)
        print("                      Then run: uv run python run.py --prod", file=sys.stderr)
        print("=" * 64 + "\n", file=sys.stderr)
        sys.exit(1)

    host = config["host"]
    port = config["backend_port"]

    print("=" * 64)
    print(" AstroVed Chatbot — Single-Service Production Server")
    print("=" * 64)
    print(f" Environment : {config['app_env']}")
    print(f" Host        : {host}")
    print(f" Port        : {port}")
    print(f" Serving     : Static SPA from frontend/dist and API at /api")
    print("=" * 64)

    uv_cmd = find_uv()
    cmd = [
        uv_cmd,
        "run",
        "--project",
        str(BACKEND_DIR),
        "uvicorn",
        "app.main:app",
        "--host",
        host,
        "--port",
        str(port),
    ]

    try:
        subprocess.run(cmd, cwd=str(BACKEND_DIR), check=True)
    except KeyboardInterrupt:
        print("\n[AstroVed Production] Server stopped.")
    except subprocess.CalledProcessError as err:
        sys.exit(err.returncode)


def wait_for_backend(host: str, port: int, backend_proc: subprocess.Popen, timeout: float = 30.0) -> bool:
    """Wait until FastAPI health endpoint responds successfully before launching Vite."""
    connect_host = "127.0.0.1" if host in ("0.0.0.0", "") else host
    health_url = f"http://{connect_host}:{port}/api/health"
    start_time = time.time()

    while time.time() - start_time < timeout:
        code = backend_proc.poll()
        if code is not None:
            print(
                f"[AstroVed Launcher] Backend process exited unexpectedly with code {code}.",
                file=sys.stderr,
            )
            return False

        try:
            req = urllib.request.Request(health_url, headers={"User-Agent": "AstroVed-Launcher"})
            with urllib.request.urlopen(req, timeout=1.0) as res:
                if res.status == 200:
                    return True
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
            pass

        time.sleep(0.15)

    print(
        f"[AstroVed Launcher] Timed out waiting for backend to respond at {health_url}.",
        file=sys.stderr,
    )
    return False


def run_development(config):
    host = config["host"]
    backend_port = config["backend_port"]
    frontend_port = config["frontend_port"]

    print("=" * 64)
    print(" AstroVed Chatbot — Unified Development Startup")
    print("=" * 64)
    print(f" Environment  : {config['app_env']}")
    print(f" Backend URL  : http://{host}:{backend_port}")
    print(f" Frontend URL : http://{host}:{frontend_port}")
    print(f" API Proxy    : http://{host}:{frontend_port}/api -> :{backend_port}")
    print("=" * 64)

    uv_cmd = find_uv()
    npm_cmd = shutil.which("npm") or "npm"

    backend_cmd = [
        uv_cmd,
        "run",
        "--project",
        str(BACKEND_DIR),
        "uvicorn",
        "app.main:app",
        "--host",
        host,
        "--port",
        str(backend_port),
        "--reload",
    ]

    frontend_cmd = [
        npm_cmd,
        "run",
        "dev",
        "--",
        "--host",
        host,
        "--port",
        str(frontend_port),
    ]

    processes = {}

    def cleanup(signum=None, frame=None):
        print("\n[AstroVed Launcher] Stopping servers cleanly...")
        for name, proc in list(processes.items()):
            if proc and proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait(timeout=4)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
        print("[AstroVed Launcher] All servers stopped.")
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    try:
        backend_proc = subprocess.Popen(backend_cmd, cwd=str(BACKEND_DIR))
        processes["Backend"] = backend_proc
    except Exception as err:
        print(f"[AstroVed Launcher] Failed to start backend: {err}", file=sys.stderr)
        sys.exit(1)

    print("[AstroVed Launcher] Waiting for backend to be ready...")
    if not wait_for_backend(host, backend_port, backend_proc):
        cleanup()
        sys.exit(1)
    print(f"[AstroVed Launcher] Backend is ready at http://{host}:{backend_port}")

    try:
        frontend_proc = subprocess.Popen(frontend_cmd, cwd=str(FRONTEND_DIR))
        processes["Frontend"] = frontend_proc
    except Exception as err:
        print(f"[AstroVed Launcher] Failed to start frontend: {err}", file=sys.stderr)
        cleanup()
        sys.exit(1)

    # Monitor both processes
    try:
        while True:
            time.sleep(0.5)
            b_code = backend_proc.poll()
            f_code = frontend_proc.poll()

            if b_code is not None:
                print(
                    f"\n[AstroVed Launcher] Backend exited with code {b_code}. Terminating frontend...",
                    file=sys.stderr,
                )
                cleanup()
                sys.exit(b_code or 1)

            if f_code is not None:
                print(
                    f"\n[AstroVed Launcher] Frontend exited with code {f_code}. Terminating backend...",
                    file=sys.stderr,
                )
                cleanup()
                sys.exit(f_code or 1)
    except KeyboardInterrupt:
        cleanup()


def main():
    config = get_config()
    is_prod_flag = "--prod" in sys.argv or "--production" in sys.argv
    is_prod_env = config["app_env"].lower() == "production"

    if is_prod_flag or is_prod_env:
        run_production(config)
    else:
        run_development(config)


if __name__ == "__main__":
    main()
