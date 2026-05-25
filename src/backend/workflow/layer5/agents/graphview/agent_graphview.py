"""
Agent GraphView phase 1.

Input:
  inputs/mapping_{form}.json
  inputs/dependency_{form}.json

Output:
  outputs/review_{form}.json

This agent reviews actual WPF source structures against original Access/VBA mapping contracts.
It features dynamic AI mapping, deterministic C# parsing, and MongoDB persistence.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from pymongo import MongoClient

try:
    from core.models import AgentInput, AgentOutput, BaseAgent, GeneratedFile
    from core.config import MONGO_URI, MONGO_DB, vba_brain_PROJECT_DIR
    from llm.llm_client import L5LLMClient, parse_json_response
except Exception:  # pragma: no cover - allows direct script execution
    AgentInput = AgentOutput = BaseAgent = GeneratedFile = None  # type: ignore
    # Resolve config.json from workflow/ root
    workflow_dir = Path(__file__).resolve().parent.parent.parent.parent.parent
    config_file = workflow_dir / "config.json"
    MONGO_URI = "mongodb://localhost:27017"
    MONGO_DB = "vba_brain_core"
    if config_file.exists():
        try:
            cfg = json.loads(config_file.read_text(encoding="utf-8"))
            mongo_cfg = cfg.get("mongodb", {})
            MONGO_URI = mongo_cfg.get("uri", MONGO_URI)
            MONGO_DB = mongo_cfg.get("db", MONGO_DB)
        except Exception:
            pass
    vba_brain_PROJECT_DIR = Path(__file__).resolve().parent.parent.parent.parent / "source"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AgentGraphView")

GRAPHVIEW_DIR = Path(__file__).resolve().parent
INPUTS_DIR = GRAPHVIEW_DIR / "inputs"
OUTPUTS_DIR = GRAPHVIEW_DIR / "outputs"


@dataclass(frozen=True)
class GraphNode:
    id: str
    label: str
    kind: str
    raw: dict[str, Any]


@dataclass(frozen=True)
class GraphEdge:
    source: str
    target: str
    label: str
    raw: dict[str, Any]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _node_data(node: dict[str, Any]) -> dict[str, Any]:
    return node.get("data", node)


def _edge_data(edge: dict[str, Any]) -> dict[str, Any]:
    return edge.get("data", edge)


def _kind_from_id(node_id: str, explicit: str = "") -> str:
    kind = explicit or ""
    if kind:
        if kind == "repository":
            return "repository"
        if kind == "navigation":
            return "navigation"
        if kind == "macro-handler":
            return "macro-handler"
        return kind
    if node_id.startswith("view:") or node_id.startswith("window:"):
        return "view"
    if node_id.startswith("viewmodel:") or "ViewModel" in node_id:
        return "viewmodel"
    if node_id.startswith("handler:macro:"):
        return "macro-handler"
    if node_id.startswith("handler:") or node_id.startswith("command:") or node_id.startswith("method:"):
        return "handler"
    if node_id.startswith("service:navigation") or "NavigationService" in node_id:
        return "navigation"
    if node_id.startswith("service:"):
        return "service"
    if node_id.startswith("repository:") or "Repository" in node_id:
        return "repository"
    if node_id.startswith("entity:"):
        return "entity"
    return node_id.split(":", 1)[0] if ":" in node_id else "unknown"


def _extract_nodes(payload: dict[str, Any]) -> list[GraphNode]:
    raw_nodes = payload.get("nodes")
    if raw_nodes is None:
        raw_nodes = payload.get("elements", {}).get("nodes", [])
    nodes: list[GraphNode] = []
    for raw in raw_nodes or []:
        data = _node_data(raw)
        node_id = str(data.get("id", ""))
        if not node_id:
            continue
        nodes.append(
            GraphNode(
                id=node_id,
                label=str(data.get("label", node_id)),
                kind=_kind_from_id(node_id, str(data.get("kind") or data.get("type") or "")),
                raw=data,
            )
        )
    return nodes


def _extract_edges(payload: dict[str, Any]) -> list[GraphEdge]:
    raw_edges = payload.get("edges")
    if raw_edges is None:
        raw_edges = payload.get("elements", {}).get("edges", [])
    edges: list[GraphEdge] = []
    for raw in raw_edges or []:
        data = _edge_data(raw)
        source = str(data.get("source", ""))
        target = str(data.get("target", ""))
        if not source or not target:
            continue
        edges.append(GraphEdge(source=source, target=target, label=str(data.get("label", "")), raw=data))
    return edges


def _aliases_for_node(node: GraphNode) -> set[str]:
    aliases = {node.id}
    if node.label:
        aliases.add(node.label)
    aliases.add(node.id.replace("window:", "view:"))
    aliases.add(node.id.replace("repo:", "repository:"))
    aliases.add(node.id.replace("method:", "handler:"))
    return {alias for alias in aliases if alias}


def _build_alias_index(nodes: list[GraphNode]) -> dict[str, GraphNode]:
    index: dict[str, GraphNode] = {}
    for node in nodes:
        for alias in _aliases_for_node(node):
            index.setdefault(alias, node)
    return index


def _edge_key(source: str, target: str) -> str:
    return f"{source}->{target}"


def _parse_wpf_edge(edge_text: str) -> tuple[str, str]:
    text = edge_text.replace("→", "->")
    if "->" not in text:
        return "", ""
    source, target = text.split("->", 1)
    target = target.split("(", 1)[0]
    return source.strip(), target.strip()


def _expected_edge_steps(mapping_edge: dict[str, Any]) -> list[tuple[str, str]]:
    flow = mapping_edge.get("expected_flow")
    if isinstance(flow, list) and len(flow) >= 2:
        return [(str(flow[i]), str(flow[i + 1])) for i in range(len(flow) - 1)]

    source = mapping_edge.get("wpf_source")
    target = mapping_edge.get("wpf_target")
    if source and target:
        return [(str(source), str(target))]

    source, target = _parse_wpf_edge(str(mapping_edge.get("wpf_edge", "")))
    if source and target:
        return [(source, target)]
    return []


def _resolve_alias(alias_index: dict[str, GraphNode], value: str) -> GraphNode | None:
    if value in alias_index:
        return alias_index[value]
    normalized = value.replace("window:", "view:").replace("repo:", "repository:")
    if normalized in alias_index:
        return alias_index[normalized]
    return None


def _actual_edge_lookup(nodes: list[GraphNode], edges: list[GraphEdge]) -> set[str]:
    alias_index = _build_alias_index(nodes)
    keys: set[str] = set()
    for edge in edges:
        source = _resolve_alias(alias_index, edge.source)
        target = _resolve_alias(alias_index, edge.target)
        if source and target:
            keys.add(_edge_key(source.id, target.id))
            for source_alias in _aliases_for_node(source):
                for target_alias in _aliases_for_node(target):
                    keys.add(_edge_key(source_alias, target_alias))
        keys.add(_edge_key(edge.source, edge.target))
    return keys


def _mapping_nodes(mapping: dict[str, Any]) -> list[dict[str, Any]]:
    return list(mapping.get("node_mapping") or mapping.get("nodeMapping") or [])


def _mapping_edges(mapping: dict[str, Any]) -> list[dict[str, Any]]:
    return list(mapping.get("edge_mapping") or mapping.get("edgeMapping") or [])


def _mapping_wpf_id(item: dict[str, Any]) -> str:
    return str(item.get("wpf_id") or item.get("wpfId") or "")


def _mapping_wpf_kind(item: dict[str, Any]) -> str:
    return str(item.get("wpf_kind") or item.get("wpfKind") or _kind_from_id(_mapping_wpf_id(item)))


def _review_nodes(mapping: dict[str, Any], dependency_nodes: list[GraphNode]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    alias_index = _build_alias_index(dependency_nodes)
    node_status: dict[str, Any] = {}
    issues: list[dict[str, Any]] = []

    expected_ids = set()
    for item in _mapping_nodes(mapping):
        wpf_id = _mapping_wpf_id(item)
        if not wpf_id:
            continue
        expected_ids.add(wpf_id)
        actual = _resolve_alias(alias_index, wpf_id)
        status = "ok" if actual else "missing"
        node_status[wpf_id] = {
            "status": status,
            "source": item.get("vba_id") or item.get("vbaId"),
            "target": wpf_id,
            "expected": {
                "id": wpf_id,
                "kind": _mapping_wpf_kind(item),
                "file": item.get("wpf_file") or item.get("wpfFile"),
            },
            "actual": actual.raw if actual else None,
        }
        if not actual:
            issues.append(
                {
                    "rule": "missing-node",
                    "status": "missing",
                    "message": f"Missing expected node: {wpf_id}",
                    "source": item.get("vba_id") or item.get("vbaId"),
                    "target": wpf_id,
                    "expected": node_status[wpf_id]["expected"],
                    "actual": None,
                }
            )

    for actual in dependency_nodes:
        if actual.id not in expected_ids and actual.id not in node_status:
            node_status[actual.id] = {
                "status": "extra",
                "source": None,
                "target": actual.id,
                "expected": None,
                "actual": actual.raw,
            }

    return node_status, issues


def _review_edges(mapping: dict[str, Any], dependency_nodes: list[GraphNode], dependency_edges: list[GraphEdge]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    alias_index = _build_alias_index(dependency_nodes)
    actual_keys = _actual_edge_lookup(dependency_nodes, dependency_edges)
    edge_status: dict[str, Any] = {}
    issues: list[dict[str, Any]] = []

    for item_index, mapping_edge in enumerate(_mapping_edges(mapping)):
        steps = _expected_edge_steps(mapping_edge)
        for step_index, (expected_source, expected_target) in enumerate(steps):
            source_node = _resolve_alias(alias_index, expected_source)
            target_node = _resolve_alias(alias_index, expected_target)
            source_id = source_node.id if source_node else expected_source
            target_id = target_node.id if target_node else expected_target
            key = _edge_key(expected_source, expected_target)
            actual_key = _edge_key(source_id, target_id)
            status = "ok" if key in actual_keys or actual_key in actual_keys else "missing"
            status_key = f"{key}#{item_index}:{step_index}"
            edge_status[status_key] = {
                "status": status,
                "source": expected_source,
                "target": expected_target,
                "expected": {
                    "source": expected_source,
                    "target": expected_target,
                    "label": mapping_edge.get("wpf_label") or mapping_edge.get("wpf_edge"),
                    "vba_edge": mapping_edge.get("vba_edge"),
                },
                "actual": {
                    "source": source_id,
                    "target": target_id,
                }
                if status == "ok"
                else None,
            }
            if status != "ok":
                issues.append(
                    {
                        "rule": "missing-flow",
                        "status": "missing",
                        "message": f"Missing expected flow: {expected_source} -> {expected_target}",
                        "source": expected_source,
                        "target": expected_target,
                        "expected": edge_status[status_key]["expected"],
                        "actual": None,
                    }
                )

    return edge_status, issues


def _find_layer_issues(nodes: list[GraphNode], edges: list[GraphEdge]) -> list[dict[str, Any]]:
    node_by_id = {node.id: node for node in nodes}
    issues: list[dict[str, Any]] = []

    def kind(node_id: str) -> str:
        node = node_by_id.get(node_id)
        return node.kind if node else _kind_from_id(node_id)

    for edge in edges:
        source_kind = kind(edge.source)
        target_kind = kind(edge.target)
        rule = ""
        message = ""

        if source_kind == "view" and target_kind != "viewmodel":
            rule = "view-layer-violation"
            message = "View must bind only to ViewModel"
        elif source_kind == "viewmodel" and target_kind == "repository":
            rule = "viewmodel-repository-direct"
            message = "ViewModel must not call Repository directly"
        elif source_kind in {"handler", "macro-handler"} and target_kind == "repository":
            rule = "handler-repository-direct"
            message = "Handler must call Repository through Service"
        elif source_kind == "service" and target_kind in {"view", "viewmodel"}:
            rule = "service-ui-reference"
            message = "Service must not reference View/ViewModel"
        elif source_kind == "repository" and target_kind in {"service", "viewmodel", "view", "navigation"}:
            rule = "repository-dependency-direction"
            message = "Repository must not call Service/ViewModel/View/Navigation"

        if rule:
            issues.append(
                {
                    "rule": rule,
                    "status": "mismatch",
                    "message": message,
                    "source": edge.source,
                    "target": edge.target,
                    "expected": "valid layer direction",
                    "actual": {
                        "sourceKind": source_kind,
                        "targetKind": target_kind,
                        "label": edge.label,
                    },
                }
            )

    return issues


def build_review(mapping: dict[str, Any], dependency: dict[str, Any], form_name: str) -> dict[str, Any]:
    dependency_nodes = _extract_nodes(dependency)
    dependency_edges = _extract_edges(dependency)

    node_status, node_issues = _review_nodes(mapping, dependency_nodes)
    edge_status, edge_issues = _review_edges(mapping, dependency_nodes, dependency_edges)
    layer_issues = _find_layer_issues(dependency_nodes, dependency_edges)
    issues = node_issues + edge_issues + layer_issues

    summary = {
        "ok": sum(1 for item in list(node_status.values()) + list(edge_status.values()) if item["status"] == "ok"),
        "missing": sum(1 for item in list(node_status.values()) + list(edge_status.values()) if item["status"] == "missing"),
        "mismatch": len(layer_issues),
        "extra": sum(1 for item in node_status.values() if item["status"] == "extra"),
    }

    return {
        "formName": form_name,
        "phase": 1,
        "status": "PASS" if summary["missing"] == 0 and summary["mismatch"] == 0 else "FAIL",
        "summary": summary,
        "nodeStatus": node_status,
        "edgeStatus": edge_status,
        "issues": issues,
    }


# ── Task 2: Implement dynamic VBA Graph extractor in Python ────────────────────────────────

def strip_vba_line_quote_comment(line: str) -> str:
    i = 0
    in_double = False
    while i < len(line):
        c = line[i]
        if c == '"':
            in_double = not in_double
            i += 1
            continue
        if not in_double and c == "'":
            return line[:i]
        i += 1
    return line


def strip_vba_comments(code: str) -> str:
    lines = code.splitlines()
    bare_lines = []
    for ln in lines:
        t = ln.lstrip()
        if t.lower().startswith("rem ") or t.lower() == "rem":
            bare_lines.append("")
        else:
            bare_lines.append(strip_vba_line_quote_comment(ln))
    return "\n".join(bare_lines)


def extract_open_query(code: str) -> list[str]:
    matches1 = re.findall(r'DoCmd\.OpenQuery\s+"([^"]+)"', code, re.IGNORECASE)
    matches2 = re.findall(r"DoCmd\.OpenQuery\s+'([^']+)'", code, re.IGNORECASE)
    return list(set(matches1 + matches2))


def extract_open_form(code: str) -> list[str]:
    matches1 = re.findall(r'DoCmd\.OpenForm\s+"([^"]+)"', code, re.IGNORECASE)
    matches2 = re.findall(r"DoCmd\.OpenForm\s+'([^']+)'", code, re.IGNORECASE)
    return list(set(matches1 + matches2))


def extract_close_form(code: str) -> list[str]:
    matches1 = re.findall(r'DoCmd\.Close\s+acForm\s*,\s*"([^"]+)"', code, re.IGNORECASE)
    matches2 = re.findall(r"DoCmd\.Close\s+acForm\s*,\s*'([^']+)'", code, re.IGNORECASE)
    return list(set(matches1 + matches2))


def extract_open_report(code: str) -> list[str]:
    matches1 = re.findall(r'DoCmd\.OpenReport\s+"([^"]+)"', code, re.IGNORECASE)
    matches2 = re.findall(r"DoCmd\.OpenReport\s+'([^']+)'", code, re.IGNORECASE)
    return list(set(matches1 + matches2))


def extract_run_macro(code: str) -> list[str]:
    matches1 = re.findall(r'DoCmd\.RunMacro\s+"([^"]+)"', code, re.IGNORECASE)
    matches2 = re.findall(r"DoCmd\.RunMacro\s+'([^']+)'", code, re.IGNORECASE)
    return list(set(matches1 + matches2))


def build_vba_graph(form_name: str) -> dict[str, Any]:
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB]
    
    nodes = []
    edges = []
    added_nodes = set()
    added_edges = set()

    def add_node(node_id: str, label: str, node_type: str, badge: str = None):
        if node_id not in added_nodes:
            added_nodes.add(node_id)
            nodes.append({"data": {"id": node_id, "label": label, "type": node_type, "badge": badge}})

    def add_edge(source: str, target: str, label: str = None):
        edge_id = f"{source}__{target}"
        if edge_id not in added_edges:
            added_edges.add(edge_id)
            edges.append({"data": {"id": edge_id, "source": source, "target": target, "label": label}})

    # Load all macros
    all_macros = {}
    try:
        macro_docs = list(db["macros"].find({}, {"macro_name": 1, "steps": 1, "references": 1}))
        for m in macro_docs:
            all_macros[m["macro_name"]] = m
    except Exception as e:
        logger.warning("Failed to load macros: %s", e)

    resolved_macros = set()
    def resolve_macro(macro_name: str, parent_id: str, depth: int = 0):
        if depth > 3 or macro_name in resolved_macros:
            return
        resolved_macros.add(macro_name)
        macro_id = f"macro:{macro_name}"
        add_node(macro_id, macro_name, "macro")
        add_edge(parent_id, macro_id, "calls")

        mac = all_macros.get(macro_name)
        if not mac:
            return
        refs = mac.get("references", {})
        for form_ref in refs.get("forms", []):
            add_node(f"form:{form_ref}", form_ref, "form")
            add_edge(macro_id, f"form:{form_ref}", "opens form")
        for q_ref in refs.get("queries", []):
            add_node(f"query:{q_ref}", q_ref, "query")
            add_edge(macro_id, f"query:{q_ref}", "runs query")
        for step in mac.get("steps", []):
            if step.get("action") == "RunMacro" and step.get("macro_name"):
                resolve_macro(step["macro_name"], macro_id, depth + 1)

    # Load the form
    doc = db["forms"].find_one({"name": form_name})
    if not doc:
        # Fallback to reports
        doc = db["reports"].find_one({"name": form_name})
        if not doc:
            raise ValueError(f"Form or Report '{form_name}' not found in MongoDB")
        type_str = "report"
    else:
        type_str = "form"

    root_id = f"{type_str}:{form_name}"
    add_node(root_id, form_name, type_str)

    # Record source
    rs = doc.get("record_source") or doc.get("properties", {}).get("data", {}).get("recordsource")
    if rs and isinstance(rs, str) and not rs.strip().upper().startswith("SELECT"):
        add_node(f"query:{rs}", rs, "query")
        add_edge(root_id, f"query:{rs}", "record source")

    functions = doc.get("functions") or doc.get("vba_procedures") or []
    event_count = len(functions)

    for fn in functions:
        handler = fn.get("handler", "unknown")
        code_raw = fn.get("code", "")
        code = strip_vba_comments(code_raw)
        event_id = f"event:{form_name}::{handler}"
        add_node(event_id, handler, "event")
        add_edge(root_id, event_id, "event")

        refs_fn = fn.get("references", {})
        macro_names = set()
        for m in refs_fn.get("macros", []):
            if m and isinstance(m, str):
                macro_names.add(m)
        for m in extract_run_macro(code):
            macro_names.add(m)
        for macro_call in macro_names:
            resolve_macro(macro_call, event_id, 0)

        for mod_ref in refs_fn.get("modules", []):
            if mod_ref and isinstance(mod_ref, str):
                add_node(f"module:{mod_ref}", mod_ref, "module")
                add_edge(event_id, f"module:{mod_ref}", "references")

        query_names = set()
        for q in refs_fn.get("queries", []):
            if q and isinstance(q, str):
                query_names.add(q)
        for q in extract_open_query(code):
            query_names.add(q)
        for q_name in query_names:
            add_node(f"query:{q_name}", q_name, "query")
            add_edge(event_id, f"query:{q_name}", "opens query")

        for f_name in extract_open_form(code):
            add_node(f"form:{f_name}", f_name, "form")
            add_edge(event_id, f"form:{f_name}", "opens form")

        for f_name in extract_close_form(code):
            add_node(f"form:{f_name}", f_name, "form")
            add_edge(event_id, f"form:{f_name}", "closes form")

        for r_name in extract_open_report(code):
            add_node(f"report:{r_name}", r_name, "report")
            add_edge(event_id, f"report:{r_name}", "opens report")

    for node in nodes:
        if node["data"]["id"] == root_id:
            node["data"]["badge"] = f"{event_count} events"

    client.close()
    return {
        "success": True,
        "elements": {
            "nodes": nodes,
            "edges": edges
        },
        "stats": {
            "nodes": len(nodes),
            "edges": len(edges),
            "events": len([n for n in nodes if n["data"]["type"] == "event"]),
            "macros": len([n for n in nodes if n["data"]["type"] == "macro"]),
            "modules": len([n for n in nodes if n["data"]["type"] == "module"]),
            "queries": len([n for n in nodes if n["data"]["type"] == "query"]),
            "forms": len([n for n in nodes if n["data"]["type"] == "form" and n["data"]["id"] != root_id])
        }
    }


# ── Task 4: Implement deterministic C# & XAML static parser in Python ───────────────────────

def walk_files(dir_path: Path, extensions: set[str]) -> list[Path]:
    out = []
    if not dir_path.exists():
        return out
    for p in dir_path.rglob("*"):
        if p.is_file() and p.suffix.lower() in extensions:
            out.append(p)
    return out


def parse_actual_source_graph(source_root: Path, screen_name: str, upstream_files: list[GeneratedFile] = None) -> dict[str, Any]:
    in_memory_files = {}
    if upstream_files:
        for gf in upstream_files:
            in_memory_files[gf.path.replace("\\", "/")] = gf.content

    physical_files = walk_files(source_root, {".cs", ".xaml", ".csproj", ".sln", ".json"})
    
    all_paths = set(in_memory_files.keys())
    for f in physical_files:
        try:
            rel = f.relative_to(source_root).as_posix()
            all_paths.add(rel)
        except Exception:
            pass

    def read_file_content(rel_path: str) -> str:
        rel_path = rel_path.replace("\\", "/")
        if rel_path in in_memory_files:
            return in_memory_files[rel_path]
        phys = source_root / rel_path
        if phys.exists():
            return phys.read_text(encoding="utf-8")
        # Try relative within directory
        for p in physical_files:
            try:
                if p.relative_to(source_root).as_posix() == rel_path or p.name == Path(rel_path).name:
                    return p.read_text(encoding="utf-8")
            except Exception:
                pass
        return ""

    nodes = {}
    edges = []
    edge_seen = set()

    def add_node(id_str: str, label: str, node_type: str, badge: str = None, vba_label: str = None):
        if id_str not in nodes:
            nodes[id_str] = {
                "data": {
                    "id": id_str,
                    "label": label,
                    "type": node_type,
                    "badge": badge,
                    "vbaLabel": vba_label,
                    "mappingStatus": "mapped"
                }
            }

    def add_edge(source: str, target: str, label: str = None):
        if source == target:
            return
        key = f"{source}->{target}->{label or ''}"
        if key in edge_seen:
            return
        edge_seen.add(key)
        edges.append({
            "data": {
                "id": f"actual:{len(edges)}",
                "source": source,
                "target": target,
                "label": label
            }
        })

    view_path = None
    vm_path = None
    for p in all_paths:
        if p.endswith(f"Views/{screen_name}.xaml") or p.endswith(f"Views/{screen_name}View.xaml") or p.endswith(f"/{screen_name}.xaml") or p.endswith(f"/{screen_name}View.xaml") or p == f"{screen_name}.xaml" or p == f"{screen_name}View.xaml":
            view_path = p
        if p.endswith(f"ViewModels/{screen_name}.cs") or p.endswith(f"ViewModels/{screen_name}ViewModel.cs") or p.endswith(f"/{screen_name}ViewModel.cs") or p.endswith(f"/{screen_name}.cs") or p == f"{screen_name}ViewModel.cs" or p == f"{screen_name}.cs":
            vm_path = p

    view_label = Path(view_path).stem if view_path else f"{screen_name}View"
    vm_label = Path(vm_path).stem if vm_path else f"{screen_name}ViewModel"

    if view_path:
        add_node(f"view:{screen_name}", view_label, "view", view_path, screen_name)
    if vm_path:
        add_node(f"viewmodel:{screen_name}", vm_label, "viewmodel", vm_path, screen_name)
    if view_path and vm_path:
        add_edge(f"view:{screen_name}", f"viewmodel:{screen_name}", "DataContext")

    service_paths = [p for p in all_paths if "/Services/" in p or p.startswith("Services/") or p.endswith("Service.cs")]
    repository_paths = [p for p in all_paths if "/Repositories/" in p or p.startswith("Repositories/") or p.endswith("Repository.cs")]

    service_classes = [Path(p).stem for p in service_paths if not Path(p).stem.startswith("I")]
    repository_classes = [Path(p).stem for p in repository_paths if not Path(p).stem.startswith("I")]

    vm_code = read_file_content(vm_path) if vm_path else ""
    xaml_code = read_file_content(view_path) if view_path else ""

    xaml_commands = re.findall(r'Command\s*=\s*"\{Binding\s+([^,}\s]+)', xaml_code)
    
    vm_commands = set()
    matches1 = re.findall(r'\b(?:ICommand|RelayCommand|DelegateCommand|AsyncRelayCommand)\s+([A-Za-z_][A-Za-z0-9_]*)', vm_code)
    for m in matches1:
        vm_commands.add(m)
    matches2 = re.findall(r'\b([A-Za-z_][A-Za-z0-9_]*Command)\b', vm_code)
    for m in matches2:
        vm_commands.add(m)
    for c in xaml_commands:
        vm_commands.add(c)

    for command in vm_commands:
        handler_id = f"handler:{screen_name}|{command}"
        add_node(handler_id, command, "handler", "ICommand", f"{screen_name}::{command}")
        if vm_path:
            add_edge(f"viewmodel:{screen_name}", handler_id, "binds command")

    def constructor_params(code: str, suffix: str) -> list[str]:
        names = set()
        re_pattern = re.compile(r'\bI?([A-Za-z_][A-Za-z0-9_]*' + re.escape(suffix) + r')\b')
        for m in re_pattern.finditer(code):
            names.add(m.group(1))
        return list(names)

    def method_calls_to_classes(code: str, class_names: list[str]) -> list[str]:
        found = set()
        for cls in class_names:
            base = cls[1:] if (cls.startswith("I") and len(cls) > 1 and cls[1].isupper()) else cls
            base_clean = base
            if base_clean.endswith("Service"):
                base_clean = base_clean[:-7]
            elif base_clean.endswith("Repository"):
                base_clean = base_clean[:-10]
            var_pattern = re.compile(r'\b_?[a-zA-Z0-9]*' + re.escape(base_clean) + r'[a-zA-Z0-9]*\.', re.IGNORECASE)
            class_pattern = re.compile(r'\b' + re.escape(cls) + r'\b')
            if var_pattern.search(code) or class_pattern.search(code):
                found.add(cls)
        return list(found)

    services_in_vm = set(constructor_params(vm_code, "Service") + method_calls_to_classes(vm_code, service_classes))
    repositories_in_vm = set(constructor_params(vm_code, "Repository") + method_calls_to_classes(vm_code, repository_classes))
    uses_navigation = bool(re.search(r'NavigationService|INavigationService|\.Navigate|\.Show\(|new\s+[A-Za-z_][A-Za-z0-9_]*View\b', vm_code))

    for service in services_in_vm:
        is_nav = "navigation" in service.lower()
        sid = "service:navigation" if is_nav else f"service:{service}"
        label = "NavigationService" if is_nav else service
        kind = "navigation" if is_nav else "service"
        add_node(sid, label, kind, "Application/Services")
        for command in (vm_commands if vm_commands else ["ViewModel"]):
            tgt_id = f"handler:{screen_name}|{command}" if command != "ViewModel" else f"viewmodel:{screen_name}"
            add_edge(tgt_id, sid, "uses navigation" if is_nav else "calls service")

    if uses_navigation and not any("navigation" in s.lower() for s in services_in_vm):
        add_node("service:navigation", "NavigationService", "navigation", "Application/Navigation")
        for command in vm_commands:
            add_edge(f"handler:{screen_name}|{command}", "service:navigation", "uses navigation")

    for repo in repositories_in_vm:
        add_node(f"repository:{repo}", repo, "repository", "Infrastructure/Repositories")
        add_edge(f"viewmodel:{screen_name}", f"repository:{repo}", "direct repository")

    for service_path_item in service_paths:
        service_name = Path(service_path_item).stem
        if service_name.startswith("I"):
            continue
        code = read_file_content(service_path_item)
        is_nav = "navigation" in service_name.lower()
        sid = "service:navigation" if is_nav else f"service:{service_name}"
        label = "NavigationService" if is_nav else service_name
        kind = "navigation" if is_nav else "service"
        add_node(sid, label, kind, service_path_item)

        repos_in_service = set(constructor_params(code, "Repository") + method_calls_to_classes(code, repository_classes))
        for repo in repos_in_service:
            add_node(f"repository:{repo}", repo, "repository", "Infrastructure/Repositories")
            add_edge(sid, f"repository:{repo}", "uses repository")

    for repo_path_item in repository_paths:
        repo_name = Path(repo_path_item).stem
        if repo_name.startswith("I"):
            continue
        add_node(f"repository:{repo_name}", repo_name, "repository", repo_path_item)

    node_list = list(nodes.values())
    count_type = lambda t: len([n for n in node_list if n["data"]["type"] == t])
    return {
        "nodes": node_list,
        "edges": edges,
        "files": list(all_paths),
        "stats": {
            "nodes": len(node_list),
            "edges": len(edges),
            "views": count_type("view"),
            "viewmodels": count_type("viewmodel"),
            "handlers": count_type("handler"),
            "services": count_type("service"),
            "repositories": count_type("repository"),
            "navigation": count_type("navigation")
        }
    }


# ── Translation Normalizer Heuristics ──────────────────────────────────────────────────────

def load_jp_to_en_mappings() -> dict[str, Any]:
    forms = {}
    events = {}
    queries = {}
    macros = {}

    def normalize_key(val: str) -> str:
        val = unicodedata.normalize('NFKC', val)
        val = re.sub(r'(?<=[A-Za-z\u3040-\u30ff\u3400-\u9fff_])II(?=[_\s]|$)', 'Ⅱ', val)
        return val.strip()

    try:
        f_path = GRAPHVIEW_DIR / "outputs" / "forms" / "listFormJpToEn.json"
        if f_path.exists():
            f_data = json.loads(f_path.read_text(encoding="utf-8-sig"))
            for row in f_data.get("items", []):
                acc = row.get("access_form_name")
                view = row.get("wpf_view_name")
                vm = row.get("wpf_viewmodel_name", "")
                if acc and view:
                    forms[acc] = {"view": view, "vm": vm}
                    forms[normalize_key(acc)] = {"view": view, "vm": vm}
    except Exception as e:
        logger.warning("Failed to load listFormJpToEn.json: %s", e)

    try:
        e_path = GRAPHVIEW_DIR / "outputs" / "events" / "listEventJpToEn.json"
        if e_path.exists():
            e_data = json.loads(e_path.read_text(encoding="utf-8-sig"))
            for row in e_data.get("items", []):
                acc = row.get("access_form_name")
                hint = row.get("handler_hint")
                dotnet = row.get("suggested_dotnet_handler_name")
                if acc and hint and dotnet:
                    events[f"{acc}::{hint}"] = dotnet
                    events[f"{normalize_key(acc)}::{normalize_key(hint)}"] = dotnet
    except Exception as e:
        logger.warning("Failed to load listEventJpToEn.json: %s", e)

    try:
        q_path = GRAPHVIEW_DIR / "outputs" / "queries" / "listQueryJpToEn.json"
        if q_path.exists():
            q_data = json.loads(q_path.read_text(encoding="utf-8-sig"))
            for row in q_data.get("items", []):
                acc = row.get("access_query_name")
                dotnet = row.get("suggested_dotnet_type_name")
                if acc and dotnet:
                    queries[acc] = dotnet
                    queries[normalize_key(acc)] = dotnet
    except Exception as e:
        logger.warning("Failed to load listQueryJpToEn.json: %s", e)

    try:
        m_path = GRAPHVIEW_DIR / "outputs" / "macros" / "listMacroJpToEn.json"
        if m_path.exists():
            m_data = json.loads(m_path.read_text(encoding="utf-8-sig"))
            for row in m_data.get("items", []):
                acc = row.get("access_macro_name")
                dotnet = row.get("suggested_dotnet_type_name")
                if acc and dotnet:
                    macros[acc] = dotnet
                    macros[normalize_key(acc)] = dotnet
    except Exception as e:
        logger.warning("Failed to load listMacroJpToEn.json: %s", e)

    modules = {}
    try:
        mod_path = GRAPHVIEW_DIR / "outputs" / "modules" / "listModuleJpToEn.json"
        if mod_path.exists():
            mod_data = json.loads(mod_path.read_text(encoding="utf-8-sig"))
            for row in mod_data.get("items", []):
                acc = row.get("access_module_name")
                dotnet = row.get("suggested_dotnet_type_name")
                if acc and dotnet:
                    modules[acc] = dotnet
                    modules[normalize_key(acc)] = dotnet
    except Exception as e:
        logger.warning("Failed to load listModuleJpToEn.json: %s", e)

    return {"forms": forms, "events": events, "queries": queries, "macros": macros, "modules": modules, "normalize_key": normalize_key}


# ── MongoDB persistence seeder ─────────────────────────────────────────────────────────────

def seed_files_to_mongo(form_name: str, mapping: dict, dependency: dict, review: dict):
    try:
        client = MongoClient(MONGO_URI)
        db = client[MONGO_DB]
        col = db["agent_graphview"]
        now = datetime.now()
        
        files_to_save = [
            {"file_name": f"mapping_{form_name}.json", "file_type": "mapping", "content": mapping},
            {"file_name": f"dependency_{form_name}.json", "file_type": "dependency", "content": dependency},
            {"file_name": f"review_{form_name}.json", "file_type": "review", "content": review},
        ]
        
        for item in files_to_save:
            col.update_one(
                {"file_name": item["file_name"]},
                {
                    "$setOnInsert": {"created_at": now},
                    "$set": {
                        "form_name": form_name,
                        "file_name": item["file_name"],
                        "file_type": item["file_type"],
                        "content": item["content"],
                        "updated_at": now
                    }
                },
                upsert=True
            )
        client.close()
        logger.info(f"Successfully seeded GraphView files for {form_name} into MongoDB collection 'agent_graphview'")
    except Exception as e:
        logger.error(f"Failed to seed GraphView files into MongoDB: {e}")


def run_graphview_review(form_name: str, inputs_dir: Path = INPUTS_DIR, outputs_dir: Path = OUTPUTS_DIR) -> dict[str, Any]:
    mapping_path = inputs_dir / f"mapping_{form_name}.json"
    dependency_path = inputs_dir / f"dependency_{form_name}.json"
    review_path = outputs_dir / f"review_{form_name}.json"

    if not mapping_path.exists() or not dependency_path.exists():
        logger.info("Local inputs not found. Running dynamic generation...")
        vba_graph = build_vba_graph(form_name)
        jp_maps = load_jp_to_en_mappings()
        user_prompt = {
            "form_name": form_name,
            "vba_graph": vba_graph["elements"],
            "translation_hints": {
                "forms": {k: v for k, v in jp_maps["forms"].items() if k.lower() == form_name.lower()},
                "events": {k: v for k, v in jp_maps["events"].items() if k.lower().startswith(form_name.lower() + "::")},
                "queries": {k: v for k, v in jp_maps["queries"].items()},
                "macros": {k: v for k, v in jp_maps["macros"].items()},
                "modules": {k: v for k, v in jp_maps["modules"].items()}
            },
            "generated_files": []
        }
        
        # Invoke LLM Client
        prompt_file = GRAPHVIEW_DIR / "prompts" / "agent_graphview.md"
        system_prompt = prompt_file.read_text(encoding="utf-8")
        
        llm = L5LLMClient()
        raw_response = llm.generate_code(
            task_type="viewmodel",
            system_prompt=system_prompt,
            user_prompt=json.dumps(user_prompt, ensure_ascii=False, indent=2),
            agent="graphview",
            form_name=form_name,
        )
        mapping = parse_json_response(raw_response)
        
        dependency = parse_actual_source_graph(vba_brain_PROJECT_DIR, form_name)
        
        inputs_dir.mkdir(parents=True, exist_ok=True)
        outputs_dir.mkdir(parents=True, exist_ok=True)
        
        dep_content = {
            "formName": form_name,
            "phase": 1,
            "sourceRoot": str(vba_brain_PROJECT_DIR),
            "elements": {"nodes": dependency["nodes"], "edges": dependency["edges"]},
            "nodes": dependency["nodes"],
            "edges": dependency["edges"],
            "stats": dependency["stats"],
            "files": dependency["files"],
        }
        
        _write_json(mapping_path, mapping)
        _write_json(dependency_path, dep_content)
        
        review = build_review(mapping, dependency, form_name)
        _write_json(review_path, review)
        
        seed_files_to_mongo(form_name, mapping, dep_content, review)
        return review

    mapping = _read_json(mapping_path)
    dependency = _read_json(dependency_path)
    review = build_review(mapping, dependency, form_name)
    _write_json(review_path, review)
    
    seed_files_to_mongo(form_name, mapping, dependency, review)
    return review


if BaseAgent is not None:

    class AgentGraphView(BaseAgent):
        @property
        def name(self) -> str:
            return "graphview"

        async def run(self, input: AgentInput) -> AgentOutput:
            try:
                # 1. VBA Graph Extractor
                vba_graph = build_vba_graph(input.form_name)
                
                # 2. Dynamic AI mapping generator
                jp_maps = load_jp_to_en_mappings()
                user_prompt = {
                    "form_name": input.form_name,
                    "vba_graph": vba_graph["elements"],
                    "translation_hints": {
                        "forms": {k: v for k, v in jp_maps["forms"].items() if k.lower() == input.form_name.lower()},
                        "events": {k: v for k, v in jp_maps["events"].items() if k.lower().startswith(input.form_name.lower() + "::")},
                        "queries": {k: v for k, v in jp_maps["queries"].items()},
                        "macros": {k: v for k, v in jp_maps["macros"].items()},
                        "modules": {k: v for k, v in jp_maps["modules"].items()}
                    },
                    "generated_files": [f.path for f in input.upstream_files] if input.upstream_files else []
                }
                
                system_prompt = self.load_prompt("agent_graphview.md")
                llm = L5LLMClient()
                raw_response = llm.generate_code(
                    task_type="viewmodel",
                    system_prompt=system_prompt,
                    user_prompt=json.dumps(user_prompt, ensure_ascii=False, indent=2),
                    agent=self.name,
                    form_name=input.form_name,
                )
                mapping = parse_json_response(raw_response)
                
                # 3. Deterministic WPF static parser
                dependency = parse_actual_source_graph(vba_brain_PROJECT_DIR, input.form_name, input.upstream_files)
                
                dep_content = {
                    "formName": input.form_name,
                    "phase": 1,
                    "sourceRoot": str(vba_brain_PROJECT_DIR),
                    "elements": {"nodes": dependency["nodes"], "edges": dependency["edges"]},
                    "nodes": dependency["nodes"],
                    "edges": dependency["edges"],
                    "stats": dependency["stats"],
                    "files": dependency["files"],
                }
                
                INPUTS_DIR.mkdir(parents=True, exist_ok=True)
                OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
                
                _write_json(INPUTS_DIR / f"mapping_{input.form_name}.json", mapping)
                _write_json(INPUTS_DIR / f"dependency_{input.form_name}.json", dep_content)
                
                # 4. Review & validation
                review = build_review(mapping, dependency, input.form_name)
                _write_json(OUTPUTS_DIR / f"review_{input.form_name}.json", review)
                
                # 5. Seed to MongoDB
                seed_files_to_mongo(input.form_name, mapping, dep_content, review)
                
                content = json.dumps(review, ensure_ascii=False, indent=2)
                return AgentOutput(
                    agent=self.name,
                    form_name=input.form_name,
                    files=[
                        GeneratedFile(
                            path=f"review_{input.form_name}.json",
                            content=content,
                            generator="deterministic",
                            agent=self.name,
                        )
                    ],
                    status="success" if review["status"] == "PASS" else "error",
                    metadata={"summary": review["summary"], "review_path": str(OUTPUTS_DIR / f"review_{input.form_name}.json")},
                )
            except Exception as exc:
                logger.error(f"Agent GraphView failed: {exc}", exc_info=True)
                return AgentOutput(agent=self.name, form_name=input.form_name, status="error", error=str(exc))


def _main() -> int:
    parser = argparse.ArgumentParser(description="Run Agent GraphView phase 1 review.")
    parser.add_argument("form_arg", nargs="?", help="Access form name, e.g. F_Login")
    parser.add_argument("--form", default="F_Login", help="Access form name, e.g. F_Login")
    parser.add_argument("--model", default="", help="Ignored. GraphView review is deterministic.")
    parser.add_argument("--inputs-dir", default=str(INPUTS_DIR), help="Directory containing mapping/dependency JSON")
    parser.add_argument("--outputs-dir", default=str(OUTPUTS_DIR), help="Directory for review JSON")
    args = parser.parse_args()

    form_name = args.form_arg or args.form
    review = run_graphview_review(form_name, Path(args.inputs_dir), Path(args.outputs_dir))
    print(json.dumps({"status": review["status"], "summary": review["summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
