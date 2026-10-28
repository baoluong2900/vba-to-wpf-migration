"""
agents/service/agent_service.py — Agent Service: IService + Service.cs

Pipeline order: #2 (after Agent Repo).

Unified service input (in-memory)
---------------------------------
Assembled in this module from MongoDB ``dds``, ``agent_repo``, and ``forms``
(VBA), with local file fallbacks. See ``load_dd_json``, ``load_repo_output``,
``build_service_input``.

If ``AgentInput.dd_json`` is set, it overrides the DD document.

Generation
----------
- **tool** (default): deterministic ``{Feature}Service.cs`` via ``tool_service_gen`` (no LLM).
- **llm**: ``{Feature}Service.cs`` from ``prompts/agent_service_form.md`` via ``L5LLMClient``;
  the interface is still rendered with Jinja2 using ``tool_service_gen.generate_service_iface_methods``.

Outputs (per form):
  - ``Application/Interfaces/I{Feature}Service.cs``
  - ``Application/Services/{Feature}Service.cs``

Optional: ``AgentInput.persist_service_input_json=True`` or CLI ``--save-input``
writes ``inputs/{form}_service_input.json``.
"""
from __future__ import annotations

import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from core.config import (
    AVAILABLE_MODELS,
    COL_AGENT_REPO,
    COL_AGENT_SERVICE,
    COL_DDS,
    COL_FORMS,
    MONGO_DB,
    MONGO_URI,
)
from core.fid_resolver import FID_RE, bd_events_of, fid_for_bd_event, load_bd_events_from_file, load_form_entries
from core.models import AgentInput, AgentOutput, BaseAgent, GeneratedFile
from core.naming import dto_namespace, validate_form_name

import tool_service_gen as ts_gen
from llm.llm_client import L5LLMClient, extract_code_block

logger = logging.getLogger(__name__)

AGENT_DIR = Path(__file__).parent
INPUTS_DIR = AGENT_DIR / "inputs"
OUTPUTS_DIR = AGENT_DIR / "outputs"

LAYER4_DD_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "layer4" / "inputs" / "DD_json" / "form"
)

# VBA query / data-access operators — events whose handler contains any of
# these need a repository call even when DD left `query_mappings` empty.
RE_VBA_QUERY = re.compile(
    r"\b("
    r"DLookup|DCount|DSum|DAvg|DMax|DMin|"
    r"DoCmd\.RunSQL|DoCmd\.OpenQuery|"
    r"CurrentDb|OpenRecordset|Execute"
    r")\b",
    re.IGNORECASE,
)

# DD event_trigger → VBA handler suffix: ts_gen.vba_handler_suffix (Japanese and English DD vocabularies)

# Controls whose value a handler can pass to a query (BD control types / name prefixes)
_INPUT_CONTROL_TYPES = {"textbox", "combobox", "listbox", "checkbox", "optiongroup", "optionbutton", "togglebutton"}
_INPUT_CONTROL_PREFIXES = ("txt", "cmb", "cbo", "lst", "chk", "opt", "tgl", "grp")

# Suffixes that are conventionally form-level (no control prefix). When DD's
# module_name is a placeholder (-/empty), we are confident the handler must
# be Form_<suffix>.
FORM_LEVEL_SUFFIXES: set[str] = {
    "_Open", "_Load", "_Close", "_Unload",
    "_Activate", "_Deactivate", "_Resize",
    "_Current", "_Timer",
}

# Suffixes that, on a single form, almost always map to exactly ONE handler.
# Safe to use the "unique candidate" fallback even when DD's module_name is a
# Japanese label (not the VBA control name).
LABEL_HEURISTIC_SUFFIXES: set[str] = {
    "_AfterUpdate", "_BeforeUpdate",
    "_KeyDown", "_KeyUp", "_Timer",
}


# ──────────────────────────────────────────────
# Loaders
# ──────────────────────────────────────────────
def _try_load_dd_mongo(form_name: str) -> dict | None:
    """Load DD document from ``dds`` (primary key ``name``)."""
    try:
        from pymongo import MongoClient
    except ImportError:
        logger.warning("[agent_service] pymongo not installed — cannot load dds.")
        return None
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
        db = client[MONGO_DB]
        doc = (
            db[COL_DDS].find_one({"name": form_name}, {"_id": 0})
            or db[COL_DDS].find_one(
                {"$or": [{"form_name": form_name}, {"screen_name": form_name}]},
                {"_id": 0},
            )
        )
        client.close()
        return doc if doc else None
    except Exception as e:
        logger.warning("[agent_service] MongoDB dds load failed for %s: %s", form_name, e)
        return None


def _try_load_agent_repo_mongo(form_name: str) -> dict | None:
    """Load Agent Repo contract from ``agent_repo`` (primary key ``name``)."""
    try:
        from pymongo import MongoClient
    except ImportError:
        logger.warning("[agent_service] pymongo not installed — cannot load agent_repo.")
        return None
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
        db = client[MONGO_DB]
        doc = (
            db[COL_AGENT_REPO].find_one({"name": form_name}, {"_id": 0})
            or db[COL_AGENT_REPO].find_one({"form_name": form_name}, {"_id": 0})
            or db[COL_AGENT_REPO].find_one({"screen_name": form_name}, {"_id": 0})
        )
        client.close()
        if not doc:
            return None
        return _unwrap_agent_repo_document(doc)
    except Exception as e:
        logger.warning(
            "[agent_service] MongoDB agent_repo load failed for %s: %s", form_name, e
        )
        return None


def _unwrap_agent_repo_document(doc: dict) -> dict:
    """If the document wraps the contract, return the inner dict."""
    for key in ("payload", "data", "output", "contract"):
        inner = doc.get(key)
        if isinstance(inner, dict) and (
            "repository" in inner
            or "repositories" in inner
            or "dto" in inner
            or "dtos" in inner
        ):
            return inner
    return doc


def load_dd_json(form_name: str) -> tuple[dict, Path | None, str]:
    """Load DD JSON.

    Preference order:
      1. MongoDB ``dds`` — ``{ \"name\": form_name }`` (then form_name/screen_name)
      2. inputs/{form_name}_dd.json (local snapshot)
      3. layer4/inputs/DD_json/form/{form_name}.json

    Returns ``(dd_json, file_path_or_none, origin_tag)`` where ``origin_tag`` is
    ``mongodb:dds`` or ``file:<path>``.
    """
    doc = _try_load_dd_mongo(form_name)
    if doc:
        logger.info("[agent_service] Loaded DD for %s from MongoDB (%s)", form_name, COL_DDS)
        return doc, None, "mongodb:dds"

    candidates = [
        INPUTS_DIR / f"{form_name}_dd.json",
        LAYER4_DD_DIR / f"{form_name}.json",
    ]
    for path in candidates:
        if path.exists():
            logger.info("[agent_service] Loaded DD for %s from %s", form_name, path)
            return json.loads(path.read_text(encoding="utf-8")), path, f"file:{path}"
    raise FileNotFoundError(
        f"DD JSON for '{form_name}' not found in MongoDB ({COL_DDS}) or local files. Tried:\n  - "
        + "\n  - ".join(str(p) for p in candidates)
    )


def load_repo_output(form_name: str) -> tuple[dict, Path | None, str]:
    """Load the repository contract (Agent Repo JSON shape).

    Preference order:
      1. agents/repo/outputs/{form_name}.json  ← freshest, written by Agent Repo
      2. inputs/{form_name}_repository_output.json
      3. inputs/{form_name}_repository_ouput.json  (historical typo)
      4. MongoDB ``agent_repo`` — fallback only (may be stale)

    File-based sources always win over MongoDB to ensure the Service agent uses
    the output that Agent Repo just generated in the same pipeline run.

    Returns ``(repo_dict, file_path_or_none, origin_tag)``.
    """
    # Resolve agents/repo/outputs/ relative to this file
    _repo_outputs_dir = AGENT_DIR.parent / "repo" / "outputs"

    candidates = [
        _repo_outputs_dir / f"{form_name}.json",          # freshest — fill_json output
        INPUTS_DIR / f"{form_name}_repository_output.json",
        INPUTS_DIR / f"{form_name}_repository_ouput.json", # historical typo
    ]
    for path in candidates:
        if path.exists():
            logger.info("[agent_service] Loaded repository contract from %s", path)
            return json.loads(path.read_text(encoding="utf-8")), path, f"file:{path}"

    # Fallback: MongoDB (may be from a previous run — use only when no local file exists)
    doc = _try_load_agent_repo_mongo(form_name)
    if doc:
        logger.info(
            "[agent_service] Loaded repository contract for %s from MongoDB (%s) [fallback]",
            form_name,
            COL_AGENT_REPO,
        )
        return doc, None, f"mongodb:{COL_AGENT_REPO}"

    raise FileNotFoundError(
        f"Repository contract for '{form_name}' not found in local files or MongoDB ({COL_AGENT_REPO}). Tried:\n  - "
        + "\n  - ".join(str(p) for p in candidates)
    )


def load_form_functions_from_mongo(form_name: str) -> tuple[list[dict], bool]:
    """Fetch every VBA function defined on the form from MongoDB.

    Returns a tuple (functions, ok). When MongoDB is unreachable or pymongo
    is missing, returns ([], False) so the builder degrades gracefully.
    """
    try:
        from pymongo import MongoClient
    except ImportError:
        logger.warning("[agent_service] pymongo not installed — skipping MongoDB enrichment.")
        return [], False

    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
        db = client[MONGO_DB]
        doc = (
            db[COL_FORMS].find_one({"name": form_name}, {"_id": 0})
            or db[COL_FORMS].find_one({"key": form_name}, {"_id": 0})
            or {}
        )
        client.close()
    except Exception as e:
        logger.warning("[agent_service] MongoDB lookup failed for %s: %s", form_name, e)
        return [], False

    raw = doc.get("functions") or doc.get("vba_procedures") or []
    return [_normalize_function(fn) for fn in raw if fn], True


def _normalize_function(fn: dict) -> dict:
    """Project a Mongo function entry to a stable shape."""
    return {
        "handler": fn.get("handler") or fn.get("name") or "",
        "type": fn.get("type") or "Sub",
        "input": fn.get("input") or fn.get("params") or "",
        "output": fn.get("output") or fn.get("return_type") or "",
        "code": fn.get("code") or fn.get("body") or "",
    }


# ──────────────────────────────────────────────
# VBA handler matching
# ──────────────────────────────────────────────
def match_vba_handler(event: dict, functions: list[dict]) -> dict | None:
    """Best-effort link a DD event to its VBA handler.

    Strategy (conservative — avoid noisy matches across unrelated controls):
      Pass 1: ``module_name`` (when meaningful) + trigger suffix exact match.
              Works when DD's module_name == VBA control name (e.g. txtPass).
      Pass 2: Form-level event (placeholder module_name and suffix in
              FORM_LEVEL_SUFFIXES) → prefer ``Form_<suffix>`` exact; otherwise
              accept the unique candidate.
      Pass 3: Label heuristic — module_name is a Japanese label (not a VBA
              control name) and the suffix is in LABEL_HEURISTIC_SUFFIXES
              (single handler per form). Accept the only candidate.

    Per-control events (e.g. ``_Click``, ``_DblClick``) on multiple unrelated
    controls are intentionally NOT auto-matched: too easy to attach the wrong
    handler.
    """
    if not functions:
        return None

    raw_ctrl = (event.get("module_name") or "").strip()
    is_placeholder = raw_ctrl in ("", "-", "ー")
    ctrl = "" if is_placeholder else raw_ctrl

    trigger = (event.get("event_trigger") or "").strip()
    suffix = ts_gen.vba_handler_suffix(trigger)
    if not suffix:
        return None

    # Pass 1 — ctrl + suffix (when DD module_name matches VBA control name)
    if ctrl:
        for fn in functions:
            handler = (fn.get("handler") or "").strip()
            if ctrl in handler and handler.endswith(suffix):
                return fn

    candidates = [
        fn for fn in functions
        if (fn.get("handler") or "").strip().endswith(suffix)
    ]
    if not candidates:
        return None

    # Pass 2 — form-level event with placeholder module_name
    if is_placeholder and suffix in FORM_LEVEL_SUFFIXES:
        for fn in candidates:
            if (fn.get("handler") or "").strip() == f"Form{suffix}":
                return fn
        if len(candidates) == 1:
            return candidates[0]
        return None

    # Pass 3 — Japanese-label module_name + per-form single-handler suffix
    if not is_placeholder and suffix in LABEL_HEURISTIC_SUFFIXES and len(candidates) == 1:
        return candidates[0]

    return None


def vba_has_query_op(vba_code: str) -> bool:
    """True when the VBA body touches DLookup/DCount/RunSQL/OpenQuery/..."""
    if not vba_code:
        return False
    return bool(RE_VBA_QUERY.search(vba_code))


# ──────────────────────────────────────────────
# Filtering / transformation
# ──────────────────────────────────────────────
def filter_events_for_repo(
    detail_specs: list[dict],
    functions: list[dict],
    mode: str = "query_mappings_only",
) -> list[dict]:
    """Filter DD events to those that need to talk to the repository layer.

    Each kept event is enriched in-place with two extra keys:
      - ``matched_vba``  → ``{handler, type, input, output, code}`` (or ``None``)
      - ``repo_signals`` → which signals triggered inclusion (``query_mappings``
                          and/or ``vba_query_op``)

    Modes:
      - ``"query_mappings_only"`` — keep only events with non-empty
        ``query_mappings`` (the original strict rule).
      - ``"any_repo_signal"`` (default) — keep events with either a non-empty
        ``query_mappings`` OR a matched VBA handler that contains a query op.
    """
    kept: list[dict] = []
    for spec in detail_specs or []:
        mappings = spec.get("query_mappings") or []
        has_mappings = isinstance(mappings, list) and len(mappings) > 0

        matched = match_vba_handler(spec, functions)
        vba_code = (matched or {}).get("code") or ""
        has_vba_query = vba_has_query_op(vba_code)

        if mode == "query_mappings_only":
            keep = has_mappings
        else:  # any_repo_signal
            keep = has_mappings or has_vba_query

        if not keep:
            continue

        signals = []
        if has_mappings:
            signals.append("query_mappings")
        if has_vba_query:
            signals.append("vba_query_op")

        enriched = {
            **spec,
            "matched_vba": matched,
            "repo_signals": signals,
        }
        kept.append(enriched)
    return kept


def project_repository_contracts(repo_output: dict) -> dict:
    """Pick only the parts of the repository output that the service needs."""
    return {
        "repositories": repo_output.get("repository") or repo_output.get("repositories") or [],
        "dtos": repo_output.get("dto") or repo_output.get("dtos") or [],
        "entities": repo_output.get("entity") or repo_output.get("entities") or [],
    }


def _input_control_names(dd_json: dict) -> set[str]:
    """Lower-cased names of the form's input controls listed in DD sheet_2 parameter_info."""
    names: set[str] = set()
    for p in (dd_json.get("sheet_2_overview") or {}).get("parameter_info") or []:
        if not isinstance(p, dict):
            continue
        control_type = re.sub(r"\s+", "", str(p.get("data_type") or "")).lower()
        if control_type in _INPUT_CONTROL_TYPES:
            for key in ("item_name", "symbol_name"):
                value = str(p.get(key) or "").strip()
                if value:
                    names.add(value.lower())
    return names


def _is_input_control(name: str, input_controls: set[str]) -> bool:
    """A `Me.<name>` reference that can carry a query input (listed input control or txt/cmb/chk… prefix)."""
    if name.lower() in input_controls:
        return True
    lower = name.lower()
    for prefix in _INPUT_CONTROL_PREFIXES:
        if lower.startswith(prefix) and len(name) > len(prefix):
            nxt = name[len(prefix)]
            if nxt.isupper() or nxt.isdigit() or nxt == "_" or not nxt.isascii():
                return True
    return False


# ──────────────────────────────────────────────
# Builder
# ──────────────────────────────────────────────
def build_service_input(
    form_name: str,
    dd_json: dict,
    repo_output: dict,
    form_functions: list[dict],
    *,
    dd_path: Path | None = None,
    repo_output_path: Path | None = None,
    dd_origin: str = "",
    repo_origin: str = "",
    mongodb_ok: bool = False,
    filter_mode: str = "query_mappings_only",
) -> dict[str, Any]:
    """Assemble the canonical service input payload."""
    detail_specs: list[dict] = dd_json.get("sheet_3_detail_specs") or []
    events = filter_events_for_repo(detail_specs, form_functions, mode=filter_mode)

    # Enrich events with dynamic parameter mappings from VBA code
    me_ctrl_pattern = re.compile(r"\bMe\.([a-zA-Z0-9_\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]+)\b")
    excluded_names = {"timerinterval", "recordsource", "filter", "filteron", "orderby", "orderbyon", "caption", "hwnd", "name", "dirty"}
    input_controls = _input_control_names(dd_json)

    for event in events:
        vba_code = (event.get("matched_vba") or {}).get("code") or ""
        if not vba_code:
            continue

        # Scan VBA code for input controls (Me.Requery / Me.Visible / labels are not inputs)
        found_controls = set()
        for match in me_ctrl_pattern.finditer(vba_code):
            name = match.group(1).strip()
            if name.lower() in excluded_names or ts_gen.is_label_control(name):
                continue
            if _is_input_control(name, input_controls):
                found_controls.add(name)

        if not found_controls:
            continue

        # Get or create query_mappings list (copied: the DD dict may be shared with other agents)
        qms = event.get("query_mappings")
        if not qms or not isinstance(qms, list):
            # Create a default query mapping if none exist
            qms = [{
                "sheet_name": f"{event.get('module_id')}_AutoQuery",
                "logic_query_name": "AutoQuery",
                "type": "SELECT",
                "parameters": []
            }]
        else:
            qms = [dict(qm, parameters=list(qm.get("parameters") or [])) for qm in qms]
        event["query_mappings"] = qms

        # Track existing mapped controls
        seen_controls = set()
        for qm in qms:
            for p in qm.get("parameters") or []:
                mapping = (p.get("mapping") or "").strip()
                ctrl = mapping.rsplit(".", 1)[-1] if "." in mapping else (p.get("name") or "")
                if ctrl:
                    seen_controls.add(ctrl.lower())

        # Add newly found controls to the first query mapping
        first_qm = qms[0]
        if "parameters" not in first_qm or not isinstance(first_qm["parameters"], list):
            first_qm["parameters"] = []

        for ctrl_name in sorted(found_controls):
            if ctrl_name.lower() not in seen_controls:
                first_qm["parameters"].append({
                    "name": ctrl_name,
                    "io": "I",
                    "mapping": f"<パラメータ>.{ctrl_name}"
                })
                seen_controls.add(ctrl_name.lower())

    return {
        "form_name": form_name,
        "screen_id": dd_json.get("screen_id") or form_name,
        "screen_name": dd_json.get("screen_name") or form_name,
        "source": {
            "dd_path": str(dd_path) if dd_path else "",
            "repo_output_path": str(repo_output_path) if repo_output_path else "",
            "dd_origin": dd_origin,
            "repo_origin": repo_origin,
            "mongodb_forms": bool(mongodb_ok),
            "filter_mode": filter_mode,
        },
        "stats": {
            "detail_specs_total": len(detail_specs),
            "events_kept": len(events),
            "events_with_query_mappings": sum(
                1 for e in events if "query_mappings" in e.get("repo_signals", [])
            ),
            "events_with_vba_query_op": sum(
                1 for e in events if "vba_query_op" in e.get("repo_signals", [])
            ),
            "vba_functions": len(form_functions),
        },
        "events": events,
        "vba_functions": form_functions,
        "repository_contracts": project_repository_contracts(repo_output),
    }


def save_service_input(form_name: str, payload: dict) -> Path:
    """Persist the service input next to the other inputs/ snapshots."""
    INPUTS_DIR.mkdir(parents=True, exist_ok=True)
    out = INPUTS_DIR / f"{form_name}_service_input.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


# ──────────────────────────────────────────────
# End-to-end helper
# ──────────────────────────────────────────────
def build_and_save(
    form_name: str,
    filter_mode: str = "query_mappings_only",
) -> tuple[dict, Path]:
    """Full pipeline: load → enrich → filter → save."""
    dd_json, dd_path, dd_origin = load_dd_json(form_name)
    repo_output, repo_path, repo_origin = load_repo_output(form_name)
    form_functions, mongo_ok = load_form_functions_from_mongo(form_name)

    payload = build_service_input(
        form_name=form_name,
        dd_json=dd_json,
        repo_output=repo_output,
        form_functions=form_functions,
        dd_path=dd_path,
        repo_output_path=repo_path,
        dd_origin=dd_origin,
        repo_origin=repo_origin,
        mongodb_ok=mongo_ok,
        filter_mode=filter_mode,
    )
    out = save_service_input(form_name, payload)
    return payload, out



def contract_method_key(module_id: str, bd_event: dict | None, ui_event_map: dict) -> str:
    """Service-contract key: the BD module_id (= F-ID used by UI/Logic); non-F### ids via core.fid_resolver."""
    if not FID_RE.match(module_id) and bd_event:
        return fid_for_bd_event(bd_event, ui_event_map) or module_id
    return module_id


def contract_vba_handler(bd_event: dict | None, event: dict) -> str:
    """VBA handler of a contract method: BD event notes when they name one, else the matched VBA handler."""
    notes = ((bd_event or {}).get("notes") or "").strip()
    if notes and notes != "-" and not notes.startswith("["):
        return notes
    return (event.get("matched_vba") or {}).get("handler") or ""


class ServiceAgent(BaseAgent):
    """Generate I{Feature}Service.cs and {Feature}Service.cs from DD + repo contract + VBA."""

    @property
    def name(self) -> str:
        return "service"

    async def run(self, input: AgentInput) -> AgentOutput:
        form_name = input.form_name
        logger.info("[Agent Service] Starting for form: %s", form_name)

        try:
            validate_form_name(form_name)
            service_input = self._build_input(form_name, input)

            events: list[dict] = service_input.get("events", []) or []
            vba_functions: list[dict] = service_input.get("vba_functions", []) or []
            repo_contracts: dict = service_input.get("repository_contracts", {}) or {}

            feature = self._form_to_feature_name(form_name)
            codegen_mode = (input.service_codegen_mode or "tool").strip().lower()

            generated_files: list[GeneratedFile] = []

            if not events:
                logger.warning(
                    "[Agent Service] No events to generate for %s — empty filter result.",
                    form_name,
                )
            else:
                iface_file, impl_file, req_file, res_file = await self._gen_form_service(
                    form_name=form_name,
                    feature=feature,
                    service_input=service_input,
                    codegen_mode=codegen_mode,
                    model_override=input.model_override,
                    upstream_files=input.upstream_files,
                    include_comments=input.service_include_comments,
                )
                generated_files.extend([iface_file, impl_file, req_file, res_file])

            self._save_outputs(form_name, generated_files)

            # ── Save service_contract ({form}.json) for downstream agents (Logic + UI) ──
            # Not optional: without it Logic/UI cannot wire the service, so a failure fails the run.
            self._save_service_contract(form_name, feature, service_input, input.bd_json)

            logger.info(
                "[Agent Service] ✅ Generated %d files for %s (IF: %s) via %s",
                len(generated_files), form_name, f"I{feature}Service",
                codegen_mode,
            )

            # ── Auto Backup ──
            try:
                layer5_dir = str(Path(__file__).resolve().parent.parent.parent)
                if layer5_dir not in sys.path:
                    sys.path.insert(0, layer5_dir)
                from pipeline import backup_layer5
                backup_layer5.backup_agent(self.name)
            except Exception as exc:
                logger.error("Auto-backup failed: %s", exc)

            return AgentOutput(
                agent="service",
                form_name=form_name,
                files=generated_files,
                status="success",
                metadata={
                    "feature": feature,
                    "service_codegen_mode": codegen_mode,
                    "events": len(events),
                    "vba_functions": len(vba_functions),
                    "repositories": len(repo_contracts.get("repositories", [])),
                    "dd_origin": service_input.get("source", {}).get("dd_origin", ""),
                    "repo_origin": service_input.get("source", {}).get("repo_origin", ""),
                },
            )

        except Exception as e:
            logger.error(
                "[Agent Service] Failed for %s: %s", form_name, e, exc_info=True
            )
            return AgentOutput(
                agent="service",
                form_name=form_name,
                status="error",
                error=str(e),
            )

    def _build_input(self, form_name: str, input: AgentInput) -> dict:
        """Assemble unified service input (Mongo-first for DD + agent_repo)."""
        filter_mode = input.service_filter_mode or "query_mappings_only"

        if input.dd_json:
            dd_json = input.dd_json
            dd_path = None
            dd_origin = "agent_input"
        else:
            dd_json, dd_path, dd_origin = load_dd_json(form_name)

        # ── Repo contract: prefer in-memory pass-through from pipeline ──────
        # The orchestrator may pass the freshly generated repo contract via
        # mongodb_data["repo_contract"] to avoid a round-trip to MongoDB and
        # eliminate timing issues (MongoDB not yet synced after Agent Repo run).
        if input.mongodb_data and input.mongodb_data.get("repo_contract"):
            repo_output = input.mongodb_data["repo_contract"]
            repo_path = None
            repo_origin = "pipeline:in_memory"
            logger.info(
                "[agent_service] Using repo contract from pipeline memory for %s", form_name
            )
        else:
            repo_output, repo_path, repo_origin = load_repo_output(form_name)

        if input.mongodb_data and "form" in input.mongodb_data:
            form_doc = input.mongodb_data.get("form") or {}
            functions = form_doc.get("functions") or form_doc.get("vba_procedures") or []
            functions = [_normalize_function(f) for f in functions if f]
            mongo_ok = True
        else:
            functions, mongo_ok = load_form_functions_from_mongo(form_name)

        payload = build_service_input(
            form_name=form_name,
            dd_json=dd_json,
            repo_output=repo_output,
            form_functions=functions,
            dd_path=dd_path,
            repo_output_path=repo_path,
            dd_origin=dd_origin,
            repo_origin=repo_origin,
            mongodb_ok=mongo_ok,
            filter_mode=filter_mode,
        )
        if input.persist_service_input_json:
            save_service_input(form_name, payload)
        return payload

    async def _gen_form_service(
        self,
        form_name: str,
        feature: str,
        service_input: dict,
        *,
        codegen_mode: str,
        model_override: Any,
        upstream_files: list[GeneratedFile],
        include_comments: bool = False,
    ) -> tuple[GeneratedFile, GeneratedFile, GeneratedFile, GeneratedFile]:
        service_name = f"{feature}Service"
        iface_name = f"I{service_name}"

        # Generate Request & Response DTOs
        req_code, res_code = ts_gen.generate_service_dtos(service_input)
        req_file = GeneratedFile(
            path=f"Application/DTOs/Requests/{feature}ServiceRequests.cs",
            content=req_code,
            generator="deterministic",
            agent="service",
        )
        res_file = GeneratedFile(
            path=f"Application/DTOs/Responses/{feature}ServiceResponses.cs",
            content=res_code,
            generator="deterministic",
            agent="service",
        )

        methods = ts_gen.generate_service_iface_methods(service_input)
        iface_code = self._render_iface(
            service_name=service_name,
            methods=methods,
            usings=[
                dto_namespace(form_name, "Requests"),
                dto_namespace(form_name, "Responses"),
            ],
            form_name=form_name,
            purpose=f"Application service for {form_name}.",
        )
        iface_file = GeneratedFile(
            path=f"Application/Interfaces/{iface_name}.cs",
            content=iface_code,
            generator="jinja2",
            agent="service",
        )

        if codegen_mode == "llm":
            impl_code = self._llm_generate_service_impl(
                form_name=form_name,
                feature=feature,
                iface_code=iface_code,
                service_input=service_input,
                model_override=model_override,
                upstream_files=upstream_files or [],
            )
            impl_generator = "llm"
        else:
            impl_code = ts_gen.generate_service_impl(service_input, include_comments=include_comments)
            impl_generator = "tool"

        impl_file = GeneratedFile(
            path=f"Application/Services/{service_name}.cs",
            content=impl_code,
            generator=impl_generator,
            agent="service",
        )

        return iface_file, impl_file, req_file, res_file

    def _llm_generate_service_impl(
        self,
        form_name: str,
        feature: str,
        iface_code: str,
        service_input: dict,
        model_override: Any,
        upstream_files: list[GeneratedFile],
    ) -> str:
        system = self.load_prompt("agent_service_form.md")
        payload_for_llm = {
            "form_name": service_input.get("form_name"),
            "screen_id": service_input.get("screen_id"),
            "screen_name": service_input.get("screen_name"),
            "source": service_input.get("source"),
            "events": service_input.get("events"),
            "vba_functions": service_input.get("vba_functions"),
            "repository_contracts": service_input.get("repository_contracts"),
        }
        upstream_cs = [
            {"path": gf.path, "content": gf.content}
            for gf in upstream_files
            if gf.path.endswith(".cs")
        ]
        user = (
            f"## Form\n{form_name} (feature: {feature})\n\n"
            f"## Target interface (implement exactly)\n```csharp\n{iface_code}\n```\n\n"
            f"## Events + contracts (JSON)\n```json\n"
            f"{json.dumps(payload_for_llm, ensure_ascii=False, indent=2)}\n```\n\n"
        )
        if upstream_cs:
            user += (
                "## Upstream generated C# (Agent Repo — reference only)\n```json\n"
                f"{json.dumps(upstream_cs, ensure_ascii=False, indent=2)}\n```\n"
            )
        llm = L5LLMClient()
        mo: Any = model_override
        if isinstance(mo, str):
            mo = AVAILABLE_MODELS.get(mo)
        raw = llm.generate_code(
            task_type="service",
            system_prompt=system,
            user_prompt=user,
            model=mo,
            agent="service",
            form_name=form_name,
        )
        return extract_code_block(raw, language="csharp")

    def _render_iface(
        self,
        service_name: str,
        methods: list[dict],
        usings: list[str],
        form_name: str,
        purpose: str,
    ) -> str:
        try:
            from codegen.jinja_engine import render_service_interface

            return render_service_interface(
                service_name=service_name,
                methods=methods,
                usings=usings,
                form_name=form_name,
                purpose=purpose,
            )
        except ImportError:
            lines = ["namespace vba_brain.Application.Interfaces;", ""]
            for u in usings:
                lines.append(f"using {u};")
            if usings:
                lines.append("")
            lines.append(f"public interface I{service_name}")
            lines.append("{")
            for m in methods:
                if m.get("comment"):
                    lines.append(f"    /// <summary>{m['comment']}</summary>")
                lines.append(f"    {m['return_type']} {m['name']}({m['params']});")
            lines.append("}")
            return "\n".join(lines)

    @staticmethod
    def _form_to_feature_name(form_name: str) -> str:
        """Feature name shared with tool_service_gen (graphview JP→EN maps, else the cleaned form name)."""
        return ts_gen.form_to_feature(form_name)

    def _save_outputs(self, form_name: str, files: list[GeneratedFile]) -> None:
        """Save generated files to outputs/ AND deploy to .NET source tree."""
        OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        for gf in files:
            out = OUTPUTS_DIR / form_name / gf.path
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(gf.content, encoding="utf-8")

        # ── Deploy to .NET source tree ──
        try:
            from pipeline.file_writer import SolutionWriter
            writer = SolutionWriter()
            writer.write_all(files, overwrite=True)
            logger.info("[Agent Service] Deployed %d file(s) to source.", len(files))
        except Exception as _de:
            logger.warning("[Agent Service] Source deploy failed: %s", _de)

    @staticmethod
    def _contract_prop(prop: dict) -> dict:
        entry = {"name": prop["name"], "type": prop.get("type") or "string"}
        if prop["name"].startswith("TODO") and prop.get("description"):
            entry["name_jp"] = prop["description"]
        if prop.get("description"):
            entry["description"] = prop["description"]
        if prop.get("control"):
            entry["control"] = prop["control"]
        return entry

    def _save_service_contract(
        self,
        form_name: str,
        feature: str,
        service_input: dict,
        bd_json: dict | None = None,
    ) -> Path:
        """
        Save the service contract ({form}.json) — single source of truth for downstream agents.

        Built from the same plan as the generated C# (tool_service_gen.build_service_plan), so
        method / class / property names always match {Feature}Service.cs and its DTOs.

        Schema:
        {
          "form_name":          "F_Login",
          "feature":            "FLogin",
          "service_class":      "FLoginService",
          "iface_class":        "IFLoginService",
          "service_field":      "_fLoginService",   // DI field name in ViewModel
          "namespace":          "vba_brain.Application.Services",
          "request_namespace":  "vba_brain.Application.DTOs.Requests.F_Login",
          "response_namespace": "vba_brain.Application.DTOs.Responses.F_Login",
          "methods": {
            "F000": {
              "method_name":     "F000Async",
              "return_type":     "Task<F000Response>",
              "request_class":   "F000Request",
              "response_class":  "F000Response",
              "request_props":   [{"name": "Id", "type": "string", "description": "ユーザーID", "control": "txtID"}],
              "response_props":  [{"name": "Success", "type": "bool"}, ...],
              "repo_calls":      [{"repository": "...", "function": "...", "query": "..."}],
              "method_code":     "...",              // same C# as in the service class
              "event_trigger":   "画面を開く時",
              "event_content":   "...",
              "vba_handler":     "Form_Open",        // BD event notes
              "vm_method_name":  "F000Async"         // mirrors ui_event_map
            },
            ...
          },
          "repository": [...]                        // repository contract the service was built from
        }
        """
        from core.fsutil import atomic_write_text

        plan = ts_gen.build_service_plan(service_input)
        service_name = plan["service_name"]
        # DI field name: IFLoginService → _fLoginService
        svc_field = "_" + service_name[0].lower() + service_name[1:]

        # F-ID registry (agents/ui/configs/ui_event_map.json) + BD events, shared with UI / Logic
        ui_event_map = load_form_entries(form_name)
        bd_by_module: dict[str, dict] = {}
        for bd_event in bd_events_of(bd_json) or load_bd_events_from_file(form_name):
            bd_by_module.setdefault((bd_event.get("module_id") or "").strip(), bd_event)

        methods: dict[str, dict] = {}
        for ev_plan in plan["events"]:
            mid = (ev_plan["module_id"] or "").strip()
            if not mid:
                continue
            bd_event = bd_by_module.get(mid)
            key = contract_method_key(mid, bd_event, ui_event_map)
            if key in methods:
                n = 2
                while f"{key}_{n}" in methods:
                    n += 1
                logger.warning("[Agent Service] Duplicate module_id %s in DD — later event kept as %s_%d", key, key, n)
                key = f"{key}_{n}"
            vba_handler = contract_vba_handler(bd_event, ev_plan["event"])

            # vm_method_name: từ ui_event_map nếu có, fallback = method_name
            vm_entry = ui_event_map.get(key) if isinstance(ui_event_map.get(key), dict) else {}
            methods[key] = {
                "method_name":    ev_plan["method_name"],
                "return_type":    f"Task<{ev_plan['response_class']}>",
                "request_class":  ev_plan["request_class"],
                "response_class": ev_plan["response_class"],
                "request_props":  [self._contract_prop(p) for p in ev_plan["request_props"]],
                "response_props": [{"name": p["name"], "type": p["type"]} for p in ev_plan["response_props"]],
                "repo_calls":     ev_plan["repo_calls"],
                "method_code":    ev_plan["method_code"],   # ← C# method body (same as in Service.cs)
                "event_trigger":  ev_plan["trigger"],
                "event_content":  (ev_plan["event"].get("event_content") or "")[:200],
                "vba_handler":    vba_handler,
                "vm_method_name": vm_entry.get("vm_method_name") or ev_plan["method_name"],
            }

        contract = {
            "form_name":           form_name,
            "feature":             plan["feature"],
            "service_class":       service_name,
            "iface_class":         plan["iface_name"],
            "service_field":       svc_field,
            "namespace":           "vba_brain.Application.Services",
            "request_namespace":   plan["request_namespace"],
            "response_namespace":  plan["response_namespace"],
            "methods":             methods,
            # Repository contract the service was generated from
            "repository":          (service_input.get("repository_contracts") or {}).get("repositories") or [],
        }

        # ── Save as {form_name}.json (original JP name — readable, matches form name) ──
        contract_path = OUTPUTS_DIR / form_name / f"{form_name}.json"
        contract_json = json.dumps(contract, ensure_ascii=False, indent=2)
        atomic_write_text(contract_path, contract_json)
        logger.info("[Agent Service] contract saved → %s", contract_path)

        # ── Backup to database_json/agent_service/ ──────────────────────────
        try:
            _backup_dir = Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent \
                          / "data/database_json" / "agent_service"
            _backup_file = _backup_dir / f"{form_name}.json"
            atomic_write_text(_backup_file, contract_json)
            logger.info("[Agent Service] Backup saved → %s", _backup_file)
        except Exception as _be:
            logger.warning("[Agent Service] Backup failed: %s", _be)

        # ── Upsert into MongoDB agent_service collection ─────────────────────
        try:
            from pymongo import MongoClient
            from datetime import datetime, timezone
            _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
            _col = _client[MONGO_DB][COL_AGENT_SERVICE]
            _payload = {
                **contract,
                "name": form_name,
                "updated_at": datetime.now(tz=timezone.utc).isoformat(),
            }
            _result = _col.update_one(
                {"name": form_name},
                {"$set": _payload},
                upsert=True,
            )
            _client.close()
            _action = "INSERTED" if _result.upserted_id else "UPDATED"
            logger.info("[Agent Service] MongoDB %s %s ← %s", COL_AGENT_SERVICE, _action, form_name)
        except Exception as _me:
            logger.warning("[Agent Service] MongoDB upsert failed for %s: %s", form_name, _me)

        return contract_path


async def main():
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Agent Service — IService + Service.cs (Mongo dds + agent_repo; tool or --llm)",
    )
    parser.add_argument("form_name", help="Form name (e.g. F_Login)")
    parser.add_argument(
        "--filter-mode",
        choices=["any_repo_signal", "query_mappings_only"],
        default="query_mappings_only",
        help="Event filter when assembling service input.",
    )
    parser.add_argument(
        "--save-input",
        action="store_true",
        help="Also write agents/service/inputs/{form}_service_input.json (debug snapshot).",
    )
    parser.add_argument(
        "--dump-service-input",
        action="store_true",
        help="Only build and save inputs/{form}_service_input.json, then exit.",
    )
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Generate {Feature}Service.cs with LLM (default: deterministic tool_service_gen).",
    )
    parser.add_argument(
        "--include-comments",
        action="store_true",
        help="Include inline Japanese step comments in the generated service class.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override LLM model id when using --llm (see core.config AVAILABLE_MODELS).",
    )
    args = parser.parse_args()

    if args.dump_service_input:
        payload, out = build_and_save(args.form_name, filter_mode=args.filter_mode)
        stats = payload["stats"]
        print(f"\n[OK] Wrote service input -> {out}")
        print(f"  dd_origin           = {payload['source']['dd_origin']}")
        print(f"  repo_origin         = {payload['source']['repo_origin']}")
        print(
            f"  events_kept         = {stats['events_kept']} / {stats['detail_specs_total']}"
            f"  (via query_mappings={stats['events_with_query_mappings']}, "
            f"via vba_query_op={stats['events_with_vba_query_op']})"
        )
        print(f"  vba_functions       = {stats['vba_functions']}")
        print(f"  forms_vba_mongodb   = {payload['source']['mongodb_forms']}")
        print(f"  filter_mode         = {payload['source']['filter_mode']}")
        return

    agent = ServiceAgent()
    model_override = AVAILABLE_MODELS.get(args.model) if args.model else None
    codegen_mode = "llm" if args.llm else "tool"
    result = await agent.run(
        AgentInput(
            form_name=args.form_name,
            service_filter_mode=args.filter_mode,
            persist_service_input_json=args.save_input,
            service_codegen_mode=codegen_mode,
            model_override=model_override,
            service_include_comments=args.include_comments,
        )
    )

    if result.status == "success":
        print(f"\n[OK] Generated {len(result.files)} files for {args.form_name}:")
        for f in result.files:
            print(f"   -> {f.path}  ({f.generator})")
        print(f"\nMetadata: {result.metadata}")
    else:
        print(f"\n[ERROR] {result.error}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
