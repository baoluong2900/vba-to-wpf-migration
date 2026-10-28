#!/usr/bin/env python3
"""
Delete the LLM-generated files that Layer 5 deployed into the .NET solution (src/wpf), so the
next codegen run starts from a clean tree. Hand-written infrastructure (App.axaml.cs,
Persistence/DbConnectionFactory.cs, Domain/Common, Utils/, …) and the shared
ViewModels/ViewModelBase.cs are not touched.

Usage:
    python clean_generated_files.py --dry-run   # list what would be deleted
    python clean_generated_files.py             # delete
"""
import argparse
from pathlib import Path

# Resolved from this file, not the working directory, so running it elsewhere is harmless.
WPF_ROOT = Path(__file__).resolve().parent / "src" / "wpf"

GENERATED_DIRS = [
    WPF_ROOT / "vba_brain.UI.Avalonia" / "Views",
    WPF_ROOT / "vba_brain.UI.Avalonia" / "ViewModels",
    WPF_ROOT / "vba_brain.Application" / "Services",
    WPF_ROOT / "vba_brain.Application" / "DTOs",  # incl. Requests/<form>/ and Responses/<form>/
    WPF_ROOT / "vba_brain.Application" / "Interfaces",
    WPF_ROOT / "vba_brain.Infrastructure" / "Repositories",
    WPF_ROOT / "vba_brain.Infrastructure" / "Persistence" / "Repositories",
    WPF_ROOT / "vba_brain.Domain" / "Entities",
    WPF_ROOT / "vba_brain.Domain" / "Interfaces",
]
# ViewModelBase.cs is a base class (pipeline/base_gen.py) that only a full orchestrator run
# recreates; deleting it breaks single-agent deploys from the console.
KEEP_FILES = {".gitkeep", "README.md", "ViewModelBase.cs"}


def clean_generated_files(dry_run: bool = False) -> int:
    total = 0
    for dir_path in GENERATED_DIRS:
        if not dir_path.is_dir():
            print(f"⊘ {dir_path.relative_to(WPF_ROOT)} does not exist")
            continue
        for file in sorted(dir_path.rglob("*")):
            if not file.is_file() or file.name in KEEP_FILES:
                continue
            rel = file.relative_to(WPF_ROOT)
            if dry_run:
                print(f"• would delete {rel}")
                total += 1
                continue
            try:
                file.unlink()
                print(f"✓ deleted {rel}")
                total += 1
            except OSError as e:
                print(f"✗ could not delete {rel}: {e}")
    print(f"\n{'Would delete' if dry_run else 'Deleted'} {total} file(s)")
    return total


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Delete Layer 5 generated files from src/wpf.")
    parser.add_argument("--dry-run", action="store_true", help="list the files without deleting them")
    clean_generated_files(parser.parse_args().dry_run)
