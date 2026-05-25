#!/usr/bin/env python3
"""
vba_brain Workflow Launcher
=======================
Chạy cả Frontend (Next.js) và Backend (FastAPI) chỉ với 1 lệnh:

    python start.py

Cách dùng:
    python start.py             # Chạy cả FE + BE
    python start.py --fe-only   # Chỉ chạy Frontend
    python start.py --be-only   # Chỉ chạy Backend
    python start.py --help      # Xem hướng dẫn
"""

import subprocess
import sys
import os
import time
import json
import argparse
from pathlib import Path
from threading import Thread

# Fix Windows console encoding (chấp nhận ký tự Unicode từ Next.js)
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
MAGENTA = "\033[35m"
RED    = "\033[31m"
BOLD   = "\033[1m"

def log(tag: str, color: str, msg: str):
    ts = time.strftime("%H:%M:%S")
    print(f"{color}{BOLD}[{tag}]{RESET} [{ts}] {msg}", flush=True)

def stream_output(proc: subprocess.Popen, tag: str, color: str):
    """Stream stdout từ subprocess ra console với prefix tag."""
    for line in iter(proc.stdout.readline, ""):
        if line:
            try:
                print(f"{color}[{tag}]{RESET} {line}", end="", flush=True)
            except UnicodeEncodeError:
                # Thay thế ký tự không encode được (e.g. ✓ ▲)
                safe = line.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(sys.stdout.encoding or "utf-8")
                print(f"{color}[{tag}]{RESET} {safe}", end="", flush=True)


# ───────── Port killer ─────────────────────────────────────────────────────
def kill_port(port: int) -> None:
    """Kill bất kỳ process nào đang chiếm port (hỗ trợ cả Windows và macOS/Linux)."""
    if os.name != 'nt':
        # macOS / Linux
        try:
            result = subprocess.run(
                ["lsof", "-t", f"-i:{port}"],
                capture_output=True, text=True, timeout=5
            )
            pids = result.stdout.strip().split()
            for pid_str in pids:
                if pid_str:
                    pid = int(pid_str)
                    subprocess.run(["kill", "-9", str(pid)], timeout=3)
                    log("LAUNCHER", GREEN, f"Successfully killed process on port {port} (PID {pid})")
        except Exception as e:
            log("LAUNCHER", YELLOW, f"Could not kill port {port} on macOS/Linux: {e}")
    else:
        # Windows
        try:
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True, text=True, timeout=5
            )
            pids = set()
            for line in result.stdout.splitlines():
                if f":{port}" in line and ("LISTENING" in line or "ESTABLISHED" in line):
                    parts = line.split()
                    if parts:
                        try:
                            pids.add(int(parts[-1]))
                        except ValueError:
                            pass
            for pid in pids:
                if pid > 4:  # Bỏ qua System processes
                    try:
                        res = subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                                             capture_output=True, text=True, timeout=3)
                        if res.returncode == 0:
                            log("LAUNCHER", GREEN, f"Successfully killed process on port {port} (PID {pid})")
                        else:
                            log("LAUNCHER", YELLOW, f"Taskkill for PID {pid} returned code {res.returncode}: {res.stderr.strip()}")
                    except Exception as e:
                        log("LAUNCHER", RED, f"Failed to kill PID {pid}: {e}")
        except Exception as e:
            log("LAUNCHER", YELLOW, f"Could not kill port {port}: {e}")


# ───────── Frontend Runner ─────────────────────────────────────────────────
def run_frontend(cfg: dict) -> subprocess.Popen:
    fe_cfg  = cfg.get("frontend", {})
    port    = fe_cfg.get("port", 3000)
    cmd     = fe_cfg.get("dev_command", "yarn dev")

    # Giải phóng port nếu đang bị chiếm
    log("FE", GREEN, f"Checking port {port}...")
    kill_port(port)
    time.sleep(2)

    log("FE", GREEN, f"Starting Next.js → http://localhost:{port}")
    log("FE", GREEN, f"Command: {cmd}  (cwd: {FRONTEND_DIR})")

    env = os.environ.copy()
    env["PORT"] = str(port)
    env["BACKEND_URL"] = "http://127.0.0.1:8000"
    
    # Tăng giới hạn bộ nhớ (4GB là đủ cho Next.js, 8GB có thể gây lỗi allocation trên một số máy) và bật debug cho Rust/Turbopack
    env["NODE_OPTIONS"] = "--max-old-space-size=4096"
    env["RUST_BACKTRACE"] = "1"

    # Inject MongoDB config for child_process fallbacks
    mongo_cfg = cfg.get("mongodb", {})
    env["MONGO_URI"] = mongo_cfg.get("uri", "mongodb://localhost:27017")
    env["MONGO_DB"]  = mongo_cfg.get("db", "vba_brain_core")

    # Clear .next cache if requested via --clean
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
        env=env
    )
    Thread(target=stream_output, args=(proc, "FE", GREEN), daemon=True).start()
    return proc


# ───────── Backend Runner ──────────────────────────────────────────────────
def run_backend(cfg: dict) -> subprocess.Popen | None:
    port = 50051  # Unified gRPC Server Port

    # Luôn update .env từ config.json
    env_file = BACKEND_DIR / ".env"
    mongo_cfg = cfg.get("mongodb", {})
    mongo_uri = mongo_cfg.get("uri", "mongodb://localhost:27017")
    mongo_db  = mongo_cfg.get("db", "vba_brain_core")
    env_content = f"MONGO_URI={mongo_uri}\nMONGO_DB={mongo_db}\nL2_STAGE=dev\n"
    env_file.write_text(env_content, encoding="utf-8")
    log("BE", YELLOW, f"MongoDB URI → {mongo_uri}")

    # Kiểm tra xem có grpc_server.py không
    server_file = BACKEND_DIR / "grpc_server.py"
    if not server_file.exists():
        log("BE", YELLOW, "grpc_server.py not found.")
        return None

    # Giải phóng BE port
    log("BE", CYAN, f"Checking port {port}...")
    kill_port(port)
    time.sleep(2)

    log("BE", CYAN, f"Starting Unified gRPC API Gateway on port {port}")

    env = os.environ.copy()
    env["MONGO_URI"] = mongo_uri
    env["MONGO_DB"]  = mongo_db

    proc = subprocess.Popen(
        [sys.executable, "-X", "utf8", "grpc_server.py"],
        cwd=str(BACKEND_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env
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

    # Grace period: số giây đợi trước khi bắt đầu monitor (cho các process thời gian khởi động)
    STARTUP_GRACE_SECONDS = 15

    try:
        fe_proc = None
        if not args.be_only:
            fe_proc = run_frontend(cfg)
            if fe_proc:
                procs.append(fe_proc)
            time.sleep(3)  # Nhường cho FE khởi động

        if not args.fe_only:
            be_proc = run_backend(cfg)
            if be_proc:
                procs.append(be_proc)

        log("LAUNCHER", BOLD, f"All services started. Monitoring begins in {STARTUP_GRACE_SECONDS}s. Press Ctrl+C to stop.")

        # Grace period: không monitor trong lúc startup
        time.sleep(STARTUP_GRACE_SECONDS)

        # Monitor vòng lặp — chỉ dừng nếu process chết sau grace period
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
            try:
                p.terminate()
                p.wait(timeout=5)
            except Exception:
                p.kill()
        print(f"{GREEN}[LAUNCHER] All services stopped. Goodbye!{RESET}\n")


if __name__ == "__main__":
    main()
