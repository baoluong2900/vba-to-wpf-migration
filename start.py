#!/usr/bin/env python3
"""
vba_brain Workflow Launcher
===========================
Run the web console (Next.js, :3000) and the gRPC gateway (:50051) with one command:

    python start.py

Usage:
    python start.py             # frontend + gateway
    python start.py --fe-only   # frontend only
    python start.py --be-only   # gateway only
    python start.py --clean     # wipe the .next cache first
"""

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from threading import Thread

# Fix Windows console encoding (accept Unicode output from Next.js)
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore
    except Exception:
        pass

# ───────── Paths ───────────────────────────────────────────────────────────
WORKFLOW_DIR = Path(__file__).parent.resolve()
FRONTEND_DIR = WORKFLOW_DIR / "src" / "frontend"
BACKEND_DIR  = WORKFLOW_DIR / "src" / "backend" / "api_gateway"
CONFIG_FILE  = Path("config.json")
if not CONFIG_FILE.exists():
    CONFIG_FILE  = WORKFLOW_DIR / "config.json"

IS_WINDOWS = os.name == "nt"

# ───────── Load Config ─────────────────────────────────────────────────────
def load_config() -> dict:
    if not CONFIG_FILE.exists():
        print(f"[WARN] config.json not found at {CONFIG_FILE}. Using defaults.")
        return {}
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)

# ───────── Helpers ─────────────────────────────────────────────────────────
RESET  = "\033[0m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
CYAN   = "\033[36m"
RED    = "\033[31m"
BOLD   = "\033[1m"

def log(tag: str, color: str, msg: str):
    ts = time.strftime("%H:%M:%S")
    print(f"{color}{BOLD}[{tag}]{RESET} [{ts}] {msg}", flush=True)

def redact_uri(uri: str) -> str:
    """mongodb://user:pw@host → mongodb://***@host, for logging."""
    return re.sub(r"//[^@/]+@", "//***@", uri or "")

def stream_output(proc: subprocess.Popen, tag: str, color: str):
    """Stream a child's stdout to the console with a tag prefix."""
    for line in iter(proc.stdout.readline, ""):
        if line:
            try:
                print(f"{color}[{tag}]{RESET} {line}", end="", flush=True)
            except UnicodeEncodeError:
                # Replace characters the console cannot encode (e.g. ✓ ▲)
                safe = line.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(sys.stdout.encoding or "utf-8")
                print(f"{color}[{tag}]{RESET} {safe}", end="", flush=True)

def grpc_settings(cfg: dict) -> tuple[str, int, str]:
    """(host, port, auth token) — env first, then config.json → grpc, then defaults."""
    grpc_cfg = cfg.get("grpc", {})
    host = os.environ.get("GRPC_HOST") or grpc_cfg.get("host") or "localhost"
    port = int(os.environ.get("GRPC_PORT") or grpc_cfg.get("port") or 50051)
    token = os.environ.get("GRPC_AUTH_TOKEN") or grpc_cfg.get("auth_token") or ""
    return host, port, token

def grpc_tls_ca(cfg: dict) -> str:
    """
    PEM file the console must trust: GRPC_TLS_CA / grpc.tls_ca, else — when the gateway serves
    TLS — its own certificate (enough for a self-signed one). Empty when neither applies.
    Relative paths are resolved from the repo root, as the gateway does.
    """
    grpc_cfg = cfg.get("grpc", {})
    ca = os.environ.get("GRPC_TLS_CA") or grpc_cfg.get("tls_ca") or ""
    cert = os.environ.get("GRPC_TLS_CERT") or grpc_cfg.get("tls_cert") or ""
    key = os.environ.get("GRPC_TLS_KEY") or grpc_cfg.get("tls_key") or ""
    path = ca or (cert if cert and key else "")
    if not path:
        return ""
    return str(Path(path) if Path(path).is_absolute() else WORKFLOW_DIR / path)

def popen_group_kwargs() -> dict:
    """Start each service in its own process group so stopping it also stops its children."""
    if IS_WINDOWS:
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}

def stop_process_tree(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        if IS_WINDOWS:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True, timeout=10)
        else:
            os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=5)
    except Exception:
        try:
            if IS_WINDOWS:
                proc.kill()
            else:
                os.killpg(proc.pid, signal.SIGKILL)
        except Exception:
            pass


# ───────── Port killer ─────────────────────────────────────────────────────
def listening_pids(port: int) -> set[int]:
    """PIDs with a socket LISTENING on ``port`` — never clients merely connected to it."""
    pids: set[int] = set()
    if not IS_WINDOWS:
        result = subprocess.run(
            ["lsof", "-t", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"],
            capture_output=True, text=True, timeout=5,
        )
        pids.update(int(p) for p in result.stdout.split() if p.strip().isdigit())
        return pids
    result = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True, timeout=5)
    for line in result.stdout.splitlines():
        parts = line.split()
        # Proto  Local-Address  Foreign-Address  State  PID
        if len(parts) >= 5 and parts[3] == "LISTENING" and parts[1].rsplit(":", 1)[-1] == str(port):
            if parts[4].isdigit():
                pids.add(int(parts[4]))
    return pids

def kill_port(port: int) -> None:
    """Free ``port`` by stopping whatever is listening on it (left over from an earlier run)."""
    try:
        pids = {p for p in listening_pids(port) if p > 4 and p != os.getpid()}
    except Exception as e:
        log("LAUNCHER", YELLOW, f"Could not inspect port {port}: {e}")
        return
    for pid in pids:
        try:
            if IS_WINDOWS:
                subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, timeout=5)
            else:
                os.kill(pid, signal.SIGKILL)
            log("LAUNCHER", GREEN, f"Stopped the process listening on port {port} (PID {pid})")
        except Exception as e:
            log("LAUNCHER", RED, f"Failed to stop PID {pid} on port {port}: {e}")


# ───────── Frontend Runner ─────────────────────────────────────────────────
def run_frontend(cfg: dict) -> subprocess.Popen:
    fe_cfg  = cfg.get("frontend", {})
    port    = fe_cfg.get("port", 3000)
    cmd     = fe_cfg.get("dev_command", "yarn dev")

    log("FE", GREEN, f"Checking port {port}...")
    kill_port(port)

    log("FE", GREEN, f"Starting Next.js → http://localhost:{port}")
    log("FE", GREEN, f"Command: {cmd}  (cwd: {FRONTEND_DIR})")

    # Values already in the environment win over config.json.
    env = os.environ.copy()
    env["PORT"] = str(port)
    # 4GB is enough for Next.js (8GB can fail to allocate on some machines); Rust backtraces for Turbopack.
    env.setdefault("NODE_OPTIONS", "--max-old-space-size=4096")
    env.setdefault("RUST_BACKTRACE", "1")

    # Some API routes read MongoDB directly.
    mongo_cfg = cfg.get("mongodb", {})
    env.setdefault("MONGO_URI", mongo_cfg.get("uri", "mongodb://localhost:27017"))
    env.setdefault("MONGO_DB", mongo_cfg.get("db", "vba_brain_core"))

    # Where the API routes find the gateway, and the token it expects (if any).
    host, grpc_port, token = grpc_settings(cfg)
    client_host = "localhost" if host in ("0.0.0.0", "::", "[::]") else host
    env.setdefault("GRPC_SERVER_ADDRESS", f"{client_host}:{grpc_port}")
    if token:
        env.setdefault("GRPC_AUTH_TOKEN", token)
    if tls_ca := grpc_tls_ca(cfg):
        env["GRPC_TLS_CA"] = tls_ca  # your own GRPC_TLS_CA wins; it is only made absolute for the console

    if cfg.get("_clean_cache"):
        log("FE", YELLOW, "Cleaning .next cache...")
        dot_next = FRONTEND_DIR / ".next"
        if dot_next.exists():
            try:
                import shutil
                shutil.rmtree(dot_next)
                log("FE", GREEN, "Successfully cleaned .next cache.")
            except Exception as e:
                log("FE", RED, f"Failed to clean .next cache: {e}")

    proc = subprocess.Popen(
        cmd,
        shell=True,
        cwd=str(FRONTEND_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        **popen_group_kwargs(),
    )
    Thread(target=stream_output, args=(proc, "FE", GREEN), daemon=True).start()
    return proc


# ───────── Backend Runner ──────────────────────────────────────────────────
def run_backend(cfg: dict) -> subprocess.Popen | None:
    server_file = BACKEND_DIR / "grpc_server.py"
    if not server_file.exists():
        log("BE", YELLOW, "grpc_server.py not found.")
        return None

    host, port, token = grpc_settings(cfg)
    log("BE", CYAN, f"Checking port {port}...")
    kill_port(port)

    # Values already in the environment win over config.json.
    env = os.environ.copy()
    mongo_cfg = cfg.get("mongodb", {})
    env.setdefault("MONGO_URI", mongo_cfg.get("uri", "mongodb://localhost:27017"))
    env.setdefault("MONGO_DB", mongo_cfg.get("db", "vba_brain_core"))
    log("BE", YELLOW, f"MongoDB URI → {redact_uri(env['MONGO_URI'])}")
    log("BE", CYAN, f"Starting Unified gRPC API Gateway on {host}:{port} (auth: {'token' if token else 'off'})")

    proc = subprocess.Popen(
        [sys.executable, "-X", "utf8", "grpc_server.py"],
        cwd=str(BACKEND_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        **popen_group_kwargs(),
    )
    Thread(target=stream_output, args=(proc, "BE", CYAN), daemon=True).start()
    return proc


# ───────── Main ────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="vba_brain Workflow Launcher — Runs FE + BE together"
    )
    parser.add_argument("--fe-only", action="store_true", help="Run Frontend only")
    parser.add_argument("--be-only", action="store_true", help="Run Backend only")
    parser.add_argument("--clean", action="store_true", help="Clean frontend cache (.next) before starting")
    args = parser.parse_args()

    cfg = load_config()
    if args.clean:
        cfg["_clean_cache"] = True

    print(f"\n{BOLD}{CYAN}{'='*55}")
    print("  vba_brain Workflow Launcher")
    print(f"{'='*55}{RESET}\n")

    procs: list[subprocess.Popen] = []

    # Grace period before monitoring starts (lets the services boot)
    STARTUP_GRACE_SECONDS = 15

    try:
        fe_proc = None
        if not args.be_only:
            fe_proc = run_frontend(cfg)
            if fe_proc:
                procs.append(fe_proc)
            time.sleep(3)  # let the frontend start first

        if not args.fe_only:
            be_proc = run_backend(cfg)
            if be_proc:
                procs.append(be_proc)

        log("LAUNCHER", BOLD, f"All services started. Monitoring begins in {STARTUP_GRACE_SECONDS}s. Press Ctrl+C to stop.")
        time.sleep(STARTUP_GRACE_SECONDS)

        # Stop everything as soon as one service dies after the grace period
        while True:
            time.sleep(2)
            for p in procs:
                if p.poll() is not None:
                    log("LAUNCHER", RED, f"A service exited unexpectedly (PID {p.pid}). Stopping all.")
                    if p == fe_proc:
                        log("LAUNCHER", YELLOW, "Frontend service crashed. This may be due to Turbopack memory leaks or a corrupted cache.")
                        log("LAUNCHER", BOLD, "-> Try running with: python start.py --clean")
                    raise KeyboardInterrupt

    except KeyboardInterrupt:
        print(f"\n{YELLOW}[LAUNCHER] Shutting down all services...{RESET}")
        for p in procs:
            stop_process_tree(p)
        print(f"{GREEN}[LAUNCHER] All services stopped. Goodbye!{RESET}\n")


if __name__ == "__main__":
    main()
