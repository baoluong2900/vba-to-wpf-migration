"""agents/repo/fill_json — the form contract is the aggregation of the per-table repository JSON."""
from __future__ import annotations

import json

from agents.repo import fill_json


def _repo(name: str, dto_ns: str, dto_name: str) -> dict:
    return {
        "repository_name": f"{name}Repository",
        "interface_name": f"I{name}Repository",
        "table_name": name,
        "function": [{"function_name": "GetAsync", "query_name": f"Q_{name}", "input": [], "output": []}],
        "dto": [{"dto_name": dto_name, "namespace": dto_ns, "fields": []}],
        "entity": [{"entity_name": f"{name}Entity", "namespace": "vba_brain.Domain.Entities", "fields": []}],
    }


def test_contract_keeps_per_table_dtos_with_their_namespaces():
    contract = fill_json.build_form_contract("F_X", [
        _repo("A", "vba_brain.Domain.DTOs.A", "SearchDto"),
        _repo("B", "vba_brain.Domain.DTOs.B", "SearchDto"),
    ])
    assert contract["form_name"] == "F_X"
    assert [r["repository_name"] for r in contract["repository"]] == ["ARepository", "BRepository"]
    assert {(d["namespace"], d["dto_name"]) for d in contract["dto"]} == {
        ("vba_brain.Domain.DTOs.A", "SearchDto"), ("vba_brain.Domain.DTOs.B", "SearchDto")}
    assert [e["entity_name"] for e in contract["entity"]] == ["AEntity", "BEntity"]


def test_save_form_contract_writes_json(tmp_path):
    path = fill_json.save_form_contract("F_X", [_repo("A", "ns", "D")], outputs_dir=tmp_path)
    assert path == tmp_path / "F_X.json"
    assert json.loads(path.read_text(encoding="utf-8"))["repository"][0]["table_name"] == "A"
