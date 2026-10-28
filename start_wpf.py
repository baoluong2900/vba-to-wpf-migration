#!/usr/bin/env python3
"""
vba_brain WPF Launcher
==================
Build và chạy ứng dụng WPF (.NET 10) chỉ với 1 lệnh:

    python start_wpf.py

Cách dùng:
    python start_wpf.py              # Build + Run
    python start_wpf.py --build-only # Chỉ build, không chạy
    python start_wpf.py --run-only   # Chạy không build lại (dùng build cũ)
    python start_wpf.py --release    # Build Release mode
    python start_wpf.py --clean      # Clean trước khi build
    python start_wpf.py --help       # Xem hướng dẫn
"""

import subprocess
import sys
import os
import time
import argparse
from pathlib import Path

# Fix Windows console encoding
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ───────── Paths ───────────────────────────────────────────────────────────
WORKFLOW_DIR = Path(__file__).parent.resolve()
SOLUTION_DIR = WORKFLOW_DIR / "src" / "wpf"
PROJECT_DIR  = SOLUTION_DIR / "vba_brain.UI.Avalonia"
PROJECT_FILE = PROJECT_DIR / "vba_brain.UI.Avalonia.csproj"

# ───────── Colors ──────────────────────────────────────────────────────────
RESET  = "\033[0m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
CYAN   = "\033[36m"
RED    = "\033[31m"
BOLD   = "\033[1m"
MAGENTA = "\033[35m"

def log(tag: str, color: str, msg: str):
    ts = time.strftime("%H:%M:%S")
    print(f"{color}{BOLD}[{tag}]{RESET} [{ts}] {msg}", flush=True)


# ───────── Clean ───────────────────────────────────────────────────────────
def clean_project() -> bool:
    """dotnet clean — xóa bin/obj."""
    log("CLEAN", YELLOW, "Cleaning project...")
    result = subprocess.run(
        ["dotnet", "clean", str(PROJECT_FILE), "--verbosity", "minimal"],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if result.returncode == 0:
        log("CLEAN", GREEN, "Clean succeeded ✓")
        return True
    else:
        log("CLEAN", RED, f"Clean failed:\n{result.stderr or result.stdout}")
        return False


# ───────── Build ───────────────────────────────────────────────────────────
def build_project(configuration: str = "Debug") -> bool:
    """dotnet build — compile project."""
    log("BUILD", CYAN, f"Building vba_brain.csproj ({configuration})...")
    log("BUILD", CYAN, f"Project: {PROJECT_FILE}")

    start = time.time()
    result = subprocess.run(
        ["dotnet", "build", str(PROJECT_FILE),
         "--configuration", configuration,
         "--verbosity", "minimal"],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    elapsed = time.time() - start

    # Parse output
    stdout = result.stdout or ""
    stderr = result.stderr or ""
    output = stdout + stderr

    # Đếm warnings và errors
    warnings = output.count("warning ")
    errors = output.count("error ")

    if result.returncode == 0:
        log("BUILD", GREEN, f"Build succeeded ✓  ({elapsed:.1f}s, {warnings} warnings)")

        # Tìm output dll path
        for line in stdout.splitlines():
            if "vba_brain ->" in line:
                dll_path = line.split("->")[-1].strip()
                log("BUILD", GREEN, f"Output: {dll_path}")
                break
        return True
    else:
        log("BUILD", RED, f"Build FAILED ✗  ({elapsed:.1f}s, {errors} errors)")
        # Hiển thị errors
        for line in output.splitlines():
            if "error " in line.lower():
                log("BUILD", RED, f"  {line.strip()}")
        return False


# ───────── Run ─────────────────────────────────────────────────────────────
def run_project(configuration: str = "Debug") -> subprocess.Popen | None:
    """dotnet run — chạy ứng dụng WPF."""
    log("RUN", MAGENTA, "Starting vba_brain WPF Application...")

    env = os.environ.copy()
    env["DOTNET_ENVIRONMENT"] = "Development" if configuration == "Debug" else "Production"

    try:
        proc = subprocess.Popen(
            ["dotnet", "run",
             "--project", str(PROJECT_FILE),
             "--configuration", configuration,
             "--no-build"],  # Đã build rồi, không cần build lại
            cwd=str(PROJECT_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env
        )
        log("RUN", MAGENTA, f"vba_brain started (PID {proc.pid})")
        return proc
    except FileNotFoundError:
        log("RUN", RED, "dotnet SDK not found! Install .NET 10 SDK first.")
        return None
    except Exception as e:
        log("RUN", RED, f"Failed to start: {e}")
        return None


# ───────── Check SDK ───────────────────────────────────────────────────────
def check_dotnet_sdk() -> bool:
    """Kiểm tra .NET SDK có cài chưa."""
    try:
        result = subprocess.run(
            ["dotnet", "--version"],
            capture_output=True, text=True, timeout=5
        )
        version = result.stdout.strip()
        log("SDK", GREEN, f".NET SDK {version} ✓")
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        log("SDK", RED, ".NET SDK not found! Download: https://dotnet.microsoft.com/download")
        return False


# ───────── NuGet Restore ───────────────────────────────────────────────────
def restore_packages() -> bool:
    """dotnet restore — tải NuGet packages nếu cần."""
    log("RESTORE", CYAN, "Restoring NuGet packages...")
    result = subprocess.run(
        ["dotnet", "restore", str(PROJECT_FILE), "--verbosity", "minimal"],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if result.returncode == 0:
        log("RESTORE", GREEN, "Restore succeeded ✓")
        return True
    else:
        log("RESTORE", RED, f"Restore failed:\n{result.stderr or result.stdout}")
        return False


# ───────── Main ────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="vba_brain WPF Launcher — Build & Run ứng dụng WPF"
    )
    parser.add_argument("--build-only", action="store_true",
                        help="Chỉ build, không chạy ứng dụng")
    parser.add_argument("--run-only", action="store_true",
                        help="Chạy ứng dụng không build lại (dùng build cũ)")
    parser.add_argument("--release", action="store_true",
                        help="Build ở Release mode (tối ưu performance)")
    parser.add_argument("--clean", action="store_true",
                        help="Clean project trước khi build")
    args = parser.parse_args()

    configuration = "Release" if args.release else "Debug"

    print(f"\n{BOLD}{MAGENTA}{'='*55}")
    print("  vba_brain WPF Launcher")
    print("  .NET 10 — Clean Architecture + MVVM + Dapper")
    print(f"{'='*55}{RESET}\n")

    # Check prerequisites
    if not check_dotnet_sdk():
        sys.exit(1)

    if not PROJECT_FILE.exists():
        log("LAUNCHER", RED, f"Project file not found: {PROJECT_FILE}")
        sys.exit(1)

    # Clean nếu yêu cầu
    if args.clean:
        if not clean_project():
            sys.exit(1)

    # Build
    if not args.run_only:
        if not restore_packages():
            sys.exit(1)

        if not build_project(configuration):
            sys.exit(1)

    if args.build_only:
        log("LAUNCHER", GREEN, "Build complete. Exiting (--build-only).")
        return

    # Run
    proc = run_project(configuration)
    if proc is None:
        sys.exit(1)

    try:
        log("LAUNCHER", BOLD, "Application is running. Press Ctrl+C to stop.")

        # Stream output
        for line in iter(proc.stdout.readline, ""):
            if line:
                try:
                    print(f"{MAGENTA}[APP]{RESET} {line}", end="", flush=True)
                except UnicodeEncodeError:
                    safe = line.encode("utf-8", errors="replace").decode("utf-8")
                    print(f"{MAGENTA}[APP]{RESET} {safe}", end="", flush=True)

        # Process đã exit
        rc = proc.wait()
        if rc == 0:
            log("LAUNCHER", GREEN, "Application exited normally.")
        else:
            log("LAUNCHER", YELLOW, f"Application exited with code {rc}.")

    except KeyboardInterrupt:
        print(f"\n{YELLOW}[LAUNCHER] Stopping application...{RESET}")
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        print(f"{GREEN}[LAUNCHER] Application stopped. Goodbye!{RESET}\n")


if __name__ == "__main__":
    main()
