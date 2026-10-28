"""Base-class templates, form status, backups and the token report (layer5/pipeline, layer5/llm)."""
from __future__ import annotations

import json

from core.models import AgentOutput
from llm.token_tracker import TokenRecord, TokenTracker
from pipeline import backup_layer5
from pipeline.base_gen import RELAY_COMMAND_CS
from pipeline.orchestrator import FormResult, L5Orchestrator


def test_relay_command_template_reports_instead_of_crashing():
    assert "public static event Action<Exception>? UnhandledException;" in RELAY_COMMAND_CS
    assert "catch (Exception ex)" in RELAY_COMMAND_CS
    assert 'Console.Error.WriteLine($"[RelayCommand] Unhandled exception: {ex}");' in RELAY_COMMAND_CS


def _result(build_success=True, **statuses):
    result = FormResult(form_name="F_X", build_success=build_success, build_attempts=2)
    for name, status in statuses.items():
        result.agent_results[name] = AgentOutput(agent=name, form_name="F_X", status=status,
                                                 error=None if status == "success" else f"{name} broke")
    return result


def test_form_status_requires_every_agent_and_the_build():
    ok = dict(repo="success", service="success", ui="success", logic="success")
    assert L5Orchestrator._form_status(_result(**ok)) == ("success", None)
    assert L5Orchestrator._form_status(_result(**ok, graphview="error")) == ("success", None)  # advisory
    status, error = L5Orchestrator._form_status(_result(**{**ok, "logic": "error"}))
    assert status == "error" and "logic: logic broke" in error
    status, error = L5Orchestrator._form_status(_result(build_success=False, **ok))
    assert status == "error" and "build failed after 2 attempt(s)" in error


def test_backup_keeps_per_form_files_apart(tmp_path, monkeypatch):
    src = tmp_path / "layer5" / "agents" / "logic" / "outputs"
    for form in ("F_A", "F_B"):
        (src / form).mkdir(parents=True)
        (src / form / "method_outputs.json").write_text(json.dumps([form]), encoding="utf-8")
    monkeypatch.setattr(backup_layer5, "BASE_DIR", tmp_path / "layer5")
    monkeypatch.setattr(backup_layer5, "DATABASE_JSON_DIR", tmp_path / "data")
    backup_layer5.backup_agent("logic")
    for form in ("F_A", "F_B"):
        assert json.loads((tmp_path / "data" / "agent_logic" / form / "method_outputs.json").read_text()) == [form]


def test_token_report_writes_json_and_xlsx_atomically(tmp_path):
    tracker = TokenTracker.__new__(TokenTracker)      # skip loading the real logs/token_report.json
    tracker.records = [TokenRecord("F_X", "ui", "view_xaml", "m", 10, 5, 15, 0.0, 0.0, 0.0)]
    tracker.save_report(tmp_path)
    data = json.loads((tmp_path / "token_report.json").read_text(encoding="utf-8"))
    assert data["total_calls"] == 1 and data["records"][0]["form_name"] == "F_X"
    assert (tmp_path / "token_report.xlsx").stat().st_size > 0
    assert not list(tmp_path.glob(".*.tmp"))
