"""
agents/repo/fill_json.py — Repository → Service form contract (agents/repo/outputs/{form}.json).

The contract is the aggregation of the per-table repository JSON returned by
tool_repo.generate_files_for_table, so it always matches the generated C#.
Read by pipeline/orchestrator.py and agents/service/agent_service.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent
OUTPUTS_DIR = BASE_DIR / "outputs"

# Add parent layer5 path for core imports
sys.path.insert(0, str(BASE_DIR.parent.parent))

from core.fsutil import atomic_write_text  # noqa: E402


def build_form_contract(form_name: str, repo_jsons: list[dict]) -> dict:
    """{form_name, repository[], dto[], entity[]} from per-table repository JSON dicts."""
    repositories: list[dict] = []
    dtos: dict[tuple[str, str], dict] = {}
    entities: dict[str, dict] = {}
    for repo in repo_jsons or []:
        repo_name = repo.get("repository_name", "")
        repositories.append({
            "repository_name": repo_name,
            "interface_name": repo.get("interface_name") or f"I{repo_name}",
            "table_name": repo.get("table_name", ""),
            "function": list(repo.get("function") or []),
        })
        for dto in repo.get("dto") or []:
            dtos.setdefault((dto.get("namespace", ""), dto.get("dto_name", "")), dto)
        for entity in repo.get("entity") or []:
            entities.setdefault(entity.get("entity_name", ""), entity)
    return {
        "form_name": form_name,
        "repository": repositories,
        "dto": list(dtos.values()),
        "entity": list(entities.values()),
    }


def save_form_contract(form_name: str, repo_jsons: list[dict], outputs_dir: Path = OUTPUTS_DIR) -> Path:
    """Write outputs/{form}.json atomically (readers may run concurrently); raises on failure."""
    contract = build_form_contract(form_name, repo_jsons)
    path = Path(outputs_dir) / f"{form_name}.json"
    atomic_write_text(path, json.dumps(contract, ensure_ascii=False, indent=4))
    return path
