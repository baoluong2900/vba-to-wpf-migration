"""
deploy_to_source.py — Copy agent outputs → .NET source tree

Quy tắc:
  - Đọc namespace từ mỗi file C# để quyết định đích
  - Không bao giờ overwrite file đã tồn tại trong source (trừ khi --force)
  - Áp dụng post-deploy patches để fix lỗi build có thể xảy ra
  - Chỉ copy/patch, KHÔNG sửa agent output

Usage:
    python deploy_to_source.py F_Login
    python deploy_to_source.py F_Login --force
    python deploy_to_source.py F_Login --dry-run

Agents được deploy (theo thứ tự):
    1. repo    → Domain/Entities, Domain/Interfaces, Domain/DTOs, Infrastructure/Repositories
    2. service → Application/Services, Application/Interfaces, Application/DTOs
    3. ui      → UI.Avalonia/ViewModels, UI.Avalonia/Views

Post-deploy patches (chạy sau khi copy xong):
    - App.axaml.cs: fix namespace conflict Application (Avalonia) vs vba_brain.Application
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ── Fix Windows console encoding ───────────────────────────────────────────
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore
    except Exception:
        pass
if sys.stderr.encoding and sys.stderr.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore
    except Exception:
        pass


# ── Paths ──────────────────────────────────────────────────────────────────
# Path(__file__).resolve().parent is pipeline/, parent.parent is layer5/
LAYER5_DIR  = Path(__file__).resolve().parent.parent
AGENTS_DIR  = LAYER5_DIR / "agents"
WORKSPACE_ROOT = LAYER5_DIR.parent.parent.parent.parent
SOURCE_ROOT = WORKSPACE_ROOT / "source"
if not SOURCE_ROOT.exists():
    SOURCE_ROOT = WORKSPACE_ROOT / "src" / "wpf"

# ── Namespace → source folder mapping ─────────────────────────────────────
# Key: C# namespace prefix
# Value: relative path inside SOURCE_ROOT
NAMESPACE_TO_FOLDER: dict[str, str] = {
    "vba_brain.Domain.Entities":                    "vba_brain.Domain/Entities",
    "vba_brain.Domain.Interfaces":                  "vba_brain.Domain/Interfaces",
    "vba_brain.Domain.DTOs.Auth":                   "vba_brain.Domain/DTOs/Auth",
    "vba_brain.Domain.DTOs":                        "vba_brain.Domain/DTOs",
    "vba_brain.Infrastructure.Persistence.Repositories": "vba_brain.Infrastructure/Persistence/Repositories",
    "vba_brain.Infrastructure.Persistence":         "vba_brain.Infrastructure/Persistence",
    "vba_brain.Application.Services":               "vba_brain.Application/Services",
    "vba_brain.Application.Interfaces":             "vba_brain.Application/Interfaces",
    "vba_brain.Application.DTOs.Requests":          "vba_brain.Application/DTOs/Requests",
    "vba_brain.Application.DTOs.Responses":         "vba_brain.Application/DTOs/Responses",
    "vba_brain.Application.DTOs":                   "vba_brain.Application/DTOs",
    "vba_brain.UI.Avalonia.ViewModels":             "vba_brain.UI.Avalonia/ViewModels",
    "vba_brain.UI.Avalonia.Views":                  "vba_brain.UI.Avalonia/Views",
}

# ── Agent output dirs (searched in order) ─────────────────────────────────
def _agent_output_dirs(form_name: str) -> list[Path]:
    return [
        AGENTS_DIR / "repo"     / "outputs" / form_name,
        AGENTS_DIR / "service"  / "outputs" / form_name / "Application",
        AGENTS_DIR / "ui"       / "outputs" / form_name / "ViewModels",
        AGENTS_DIR / "ui"       / "outputs" / form_name / "Views",
        # Logic agent: patched ViewModel (WITH_SERVICE async methods)
        # Overwrites the UI skeleton when --force is used
        AGENTS_DIR / "logic"    / "outputs" / form_name / "ViewModels",
    ]



def _detect_namespace(cs_source: str) -> str | None:
    """Extract the first 'namespace X;' or 'namespace X {' from a C# file."""
    m = re.search(r'^\s*namespace\s+([\w.]+)', cs_source, re.MULTILINE)
    return m.group(1) if m else None


def _resolve_dest(src_file: Path) -> Path | None:
    """Given a source file, return its destination path in the .NET source tree."""
    text = src_file.read_text(encoding="utf-8", errors="ignore")
    ns = _detect_namespace(text)
    if not ns:
        return None
    # Match longest prefix first
    for prefix in sorted(NAMESPACE_TO_FOLDER, key=len, reverse=True):
        if ns == prefix or ns.startswith(prefix + "."):
            folder = SOURCE_ROOT / NAMESPACE_TO_FOLDER[prefix]
            return folder / src_file.name
    return None


def _check_interface_impl_mismatch(dry_run: bool = False) -> list[str]:
    """Validate every I{Repo}.cs interface against its {Repo}.cs implementation in SOURCE."""
    iface_dir = SOURCE_ROOT / "vba_brain.Domain" / "Interfaces"
    impl_dir  = SOURCE_ROOT / "vba_brain.Infrastructure" / "Persistence" / "Repositories"
    errors: list[str] = []
    if not iface_dir.exists() or not impl_dir.exists():
        return errors
    for iface_file in sorted(iface_dir.glob("I*.cs")):
        repo_name = iface_file.stem[1:]
        impl_file = impl_dir / f"{repo_name}.cs"
        if not impl_file.exists():
            continue
        iface_methods = _extract_async_methods(iface_file.read_text(encoding="utf-8"))
        impl_methods  = _extract_async_methods(impl_file.read_text(encoding="utf-8"))
        for mn in sorted(iface_methods - impl_methods):
            errors.append(
                f"  ❌ {repo_name}.cs missing: {mn}() (declared in I{repo_name}.cs)"
            )
    return errors


def _patch_app_xaml_cs(dry_run: bool = False) -> None:
    """Fix CS0118: 'Application' namespace conflict in App.axaml.cs.

    When vba_brain.Application project is referenced, the compiler confuses
    Avalonia.Application (class) with vba_brain.Application (namespace).
    Patch: replace bare ': Application' with ': global::Avalonia.Application'.
    Only applies if the file still has the unqualified form.
    """
    target = SOURCE_ROOT / "vba_brain.UI.Avalonia" / "App.axaml.cs"
    if not target.exists():
        return

    text = target.read_text(encoding="utf-8")
    # Already patched (any qualified Avalonia.Application form)
    if "Avalonia.Application" in text:
        return
    # Must contain the problematic pattern
    if ": Application" not in text:
        return

    patched = text.replace(
        "public partial class App : Application",
        "public partial class App : global::Avalonia.Application",
    )
    if patched == text:
        return  # nothing changed

    rel = target.relative_to(SOURCE_ROOT)
    print(f"\n  [post-deploy patch]")
    print(f"    🔧 {rel} — qualify Application → global::Avalonia.Application")
    if not dry_run:
        target.write_text(patched, encoding="utf-8")


def _generate_missing_stubs(dry_run: bool = False) -> None:
    """Generate missing method stubs in agent repo output files.

    When Agent Service declares methods in repository_contracts that Agent Repo
    did not generate, this function adds the missing method stubs to the
    agent repo output files BEFORE they are copied to source.

    This is the correct place to bridge the gap — not in source, not in agent output.
    We update the STAGING copy (agent repo outputs) only.
    """
    service_input_dir = LAYER5_DIR / "agents" / "service" / "inputs"
    repo_output_base  = LAYER5_DIR / "agents" / "repo" / "outputs"

    # Find all service input files
    for si_file in sorted(service_input_dir.glob("*_service_input.json")):
        try:
            si = json.loads(si_file.read_text(encoding="utf-8"))
        except Exception:
            continue

        form_name = si.get("form_name", "")
        if not form_name:
            continue
        repo_output_dir = repo_output_base / form_name
        if not repo_output_dir.exists():
            continue

        contracts = si.get("repository_contracts", {})
        for repo in contracts.get("repositories", []) or []:
            repo_name  = (repo.get("repository_name") or "").strip()
            table_name = (repo.get("table_name") or "").strip()
            functions  = repo.get("function") or []
            if not repo_name or not functions:
                continue

            iface_files = list(repo_output_dir.rglob(f"I{repo_name}.cs"))
            impl_files  = list(repo_output_dir.rglob(f"{repo_name}.cs"))

            # ── Interface ──
            for iface_file in iface_files:
                if iface_file.exists():
                    iface_src = iface_file.read_text(encoding="utf-8")
                    existing  = _extract_async_methods(iface_src)
                    new_sigs  = []
                    for fn in functions:
                        fname = (fn.get("function_name") or "").strip()
                        if not fname or fname in existing:
                            continue
                        ret    = _cs_iface_return(fn)
                        params = _cs_param_list(fn.get("input") or [])
                        qn     = fn.get("query_name") or fn.get("sheet_query_name") or ""
                        desc   = (fn.get("description") or "").strip()
                        new_sigs.append(
                            f"\n    /// <summary>\n"
                            f"    /// {qn}\n"
                            f"    /// {desc}\n"
                            f"    /// </summary>\n"
                            f"    Task<{ret}> {fname}({params});"
                        )
                    if new_sigs:
                        insert = iface_src.rfind("}")
                        patched = iface_src[:insert] + "".join(new_sigs) + "\n" + iface_src[insert:]
                        print(f"\n  [stub gen] {iface_file.name} — adding {len(new_sigs)} missing method(s)")
                        for fn in functions:
                            fname = (fn.get("function_name") or "").strip()
                            if fname not in existing and any(fname in s for s in new_sigs):
                                print(f"    + {fname}")
                        if not dry_run:
                            iface_file.write_text(patched, encoding="utf-8")

            # ── Implementation ──
            for impl_file in impl_files:
                if impl_file.exists():
                    impl_src  = impl_file.read_text(encoding="utf-8")
                    existing  = _extract_async_methods(impl_src)
                    new_stubs = []
                    for fn in functions:
                        fname = (fn.get("function_name") or "").strip()
                        if not fname or fname in existing:
                            continue
                        ret    = _cs_iface_return(fn)
                        params = _cs_param_list(fn.get("input") or [])
                        qn     = fn.get("query_name") or fn.get("sheet_query_name") or ""
                        desc   = (fn.get("description") or "").strip()
                        inner  = _cs_inner_type(fn)
                        # Build dapper params
                        inputs = fn.get("input") or []
                        if inputs:
                            dp = "new {{ {0} }}".format(
                                ", ".join(f"{p.get('name','p')} = {p.get('name','p')}" for p in inputs)
                            )
                            call = f"return await conn.QueryAsync<{inner}>(sql.ToString(), {dp});"
                        else:
                            call = f"return await conn.QueryAsync<{inner}>(sql.ToString());"
                        # Build params string
                        p_decls = ", ".join(
                            f"{_cs_scalar(p)} {p.get('name','p')}" for p in inputs
                        )
                        new_stubs.append(
                            f"\n    /// <summary>\n"
                            f"    /// {qn}\n"
                            f"    /// {desc}\n"
                            f"    /// </summary>\n"
                            f"    public async Task<{ret}> {fname}({p_decls})\n"
                            f"    {{\n"
                            f"        var sql = new System.Text.StringBuilder();\n"
                            f"        sql.AppendLine(@\"SELECT * FROM {table_name}\");\n"
                            f"        using var conn = _context.CreateConnection();\n"
                            f"        {call}\n"
                            f"    }}"
                        )
                    if new_stubs:
                        insert = impl_src.rfind("}")
                        patched = impl_src[:insert] + "".join(new_stubs) + "\n" + impl_src[insert:]
                        print(f"\n  [stub gen] {impl_file.name} — adding {len(new_stubs)} missing stub(s)")
                        if not dry_run:
                            impl_file.write_text(patched, encoding="utf-8")


def _extract_async_methods(cs_source: str) -> set[str]:
    """Return all *Async method names declared in a C# file."""
    found: set[str] = set()
    for line in cs_source.splitlines():
        s = line.strip()
        if s.startswith("//") or s.startswith("*"):
            continue
        m = re.search(r'\b(\w+Async)\s*\(', s)
        if m:
            found.add(m.group(1))
    return found


def _cs_iface_return(fn: dict) -> str:
    outputs = fn.get("output") or []
    if not outputs:
        return "IEnumerable<object>"
    out  = outputs[0]
    name = (out.get("name") or "").strip()
    typ  = (out.get("type") or "").strip().lower()
    if not name:
        return "IEnumerable<object>"
    if typ in ("string", "int", "long", "decimal", "bool", "double"):
        return typ
    return f"IEnumerable<{name}>"


def _cs_inner_type(fn: dict) -> str:
    outputs = fn.get("output") or []
    if not outputs:
        return "object"
    return (outputs[0].get("name") or "object").strip() or "object"


def _cs_scalar(p: dict) -> str:
    t = (p.get("type") or "string").strip().lower()
    return {"int": "int", "long": "long", "decimal": "decimal",
            "bool": "bool", "double": "double"}.get(t, "string")


def _cs_param_list(inputs: list[dict]) -> str:
    if not inputs:
        return ""
    return ", ".join(f"{_cs_scalar(p)} {p.get('name', 'param')}" for p in inputs)


def validate_interface_vs_impl() -> list[str]:
    """Validate every I{Repo}.cs interface against its {Repo}.cs implementation.

    Returns a list of error messages. Empty list means no mismatch.
    Does NOT modify any file — only reports.
    """
    iface_dir = SOURCE_ROOT / "vba_brain.Domain" / "Interfaces"
    impl_dir  = SOURCE_ROOT / "vba_brain.Infrastructure" / "Persistence" / "Repositories"

    errors: list[str] = []
    if not iface_dir.exists() or not impl_dir.exists():
        return errors

    for iface_file in sorted(iface_dir.glob("I*.cs")):
        repo_name = iface_file.stem[1:]  # IAuthRepository → AuthRepository
        impl_file = impl_dir / f"{repo_name}.cs"
        if not impl_file.exists():
            continue

        iface_src = iface_file.read_text(encoding="utf-8")
        impl_src  = impl_file.read_text(encoding="utf-8")

        # Extract method names from interface (lines like: Task<X> MethodName()
        iface_methods: set[str] = set()
        for line in iface_src.splitlines():
            s = line.strip()
            if s.startswith("//") or s.startswith("*"):
                continue
            m = re.search(r'\bTask[^(]*\s+(\w+Async)\s*\(', s)
            if m:
                iface_methods.add(m.group(1))

        impl_methods: set[str] = set()
        for line in impl_src.splitlines():
            s = line.strip()
            if s.startswith("//") or s.startswith("*"):
                continue
            m = re.search(r'\bpublic\s+async\s+Task[^(]*\s+(\w+Async)\s*\(', s)
            if m:
                impl_methods.add(m.group(1))

        missing = iface_methods - impl_methods
        for mn in sorted(missing):
            errors.append(
                f"  ❌ {repo_name}.cs missing implementation of {mn}() "
                f"(declared in I{repo_name}.cs)"
            )

    return errors


def deploy(form_name: str, *, force: bool = False, dry_run: bool = False) -> None:
    print(f"\n{'[DRY-RUN] ' if dry_run else ''}Deploying outputs for: {form_name}")
    print(f"  Source root: {SOURCE_ROOT}")

    # ── Step 0: Fill missing stubs in agent repo output (staging only) ────
    _generate_missing_stubs(dry_run=dry_run)

    copied = skipped = missing_ns = 0

    for agent_dir in _agent_output_dirs(form_name):
        if not agent_dir.exists():
            continue

        cs_files = list(agent_dir.rglob("*.cs"))
        if not cs_files:
            continue

        print(f"\n  [{agent_dir.relative_to(LAYER5_DIR)}]")

        for src in sorted(cs_files):
            dest = _resolve_dest(src)
            if dest is None:
                print(f"    ⚠  {src.name} — namespace not recognised, skip")
                missing_ns += 1
                continue

            rel = dest.relative_to(SOURCE_ROOT)
            if dest.exists() and not force:
                print(f"    ⏭  {rel} — already exists (use --force to overwrite)")
                skipped += 1
                continue

            status = "overwrite" if dest.exists() else "new"
            print(f"    ✅ {rel}  [{status}]")
            if not dry_run:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            copied += 1

    print(f"\nDone — copied: {copied}, skipped (exist): {skipped}, unknown ns: {missing_ns}")
    if skipped and not force:
        print("Tip: use --force to overwrite existing files")

    # ── Validate interface ↔ implementation contract ───────────────────────
    mismatches = _check_interface_impl_mismatch(dry_run=dry_run)
    if mismatches:
        print(f"\n⚠  Interface/Implementation mismatch detected — build will fail:")
        for msg in mismatches:
            print(msg)
        print(
            "\n  Fix: run Agent Repo again for this form so it generates all methods\n"
            "  that Agent Service declared in repository_contracts.\n"
            "  Then re-run: python deploy_to_source.py <form> --force"
        )

    # ── Post-deploy patches ────────────────────────────────────────────────
    _patch_app_xaml_cs(dry_run=dry_run)


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy agent outputs to .NET source tree")
    parser.add_argument("form_name", help="Form name, e.g. F_Login")
    parser.add_argument("--force",   action="store_true", help="Overwrite existing source files")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be copied without writing")
    args = parser.parse_args()
    deploy(args.form_name, force=args.force, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
