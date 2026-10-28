"""Launcher helpers (start.py) — nothing is started or killed here."""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

_spec = importlib.util.spec_from_file_location("start_launcher", Path(__file__).resolve().parents[2] / "start.py")
start = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(start)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for var in ("GRPC_HOST", "GRPC_PORT", "GRPC_AUTH_TOKEN"):
        monkeypatch.delenv(var, raising=False)


def test_grpc_settings_defaults():
    assert start.grpc_settings({}) == ("localhost", 50051, "")


def test_grpc_settings_from_config():
    cfg = {"grpc": {"host": "0.0.0.0", "port": 6000, "auth_token": "t"}}
    assert start.grpc_settings(cfg) == ("0.0.0.0", 6000, "t")


def test_environment_wins_over_config(monkeypatch):
    monkeypatch.setenv("GRPC_PORT", "7000")
    monkeypatch.setenv("GRPC_AUTH_TOKEN", "from-env")
    assert start.grpc_settings({"grpc": {"port": 6000, "auth_token": "t"}}) == ("localhost", 7000, "from-env")


def test_redact_uri():
    assert start.redact_uri("mongodb://u:p@h:27017/db") == "mongodb://***@h:27017/db"


def test_posix_lookup_asks_lsof_for_listeners_only(monkeypatch):
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        return SimpleNamespace(stdout="123\n456\n")

    monkeypatch.setattr(start, "IS_WINDOWS", False)
    monkeypatch.setattr(subprocess, "run", fake_run)
    assert start.listening_pids(3000) == {123, 456}
    assert "-sTCP:LISTEN" in seen["cmd"], "connected clients (e.g. the browser) must never be killed"


NETSTAT = """
  Proto  Local Address          Foreign Address        State           PID
  TCP    0.0.0.0:3000           0.0.0.0:0              LISTENING       1111
  TCP    127.0.0.1:52000        127.0.0.1:3000         ESTABLISHED     2222
  TCP    0.0.0.0:30001          0.0.0.0:0              LISTENING       3333
  TCP    [::]:3000              [::]:0                 LISTENING       4444
"""


def test_windows_lookup_matches_local_listening_port_exactly(monkeypatch):
    monkeypatch.setattr(start, "IS_WINDOWS", True)
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: SimpleNamespace(stdout=NETSTAT))
    # Not 2222 (a client connected to :3000) and not 3333 (port 30001).
    assert start.listening_pids(3000) == {1111, 4444}
