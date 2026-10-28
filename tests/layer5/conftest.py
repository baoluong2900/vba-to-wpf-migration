"""
Layer 5 tests run in their own pytest session:  pytest tests/layer5

Layer 5's top-level packages (`agents`, `core`, `llm`, `pipeline`) are imported by bare name,
and Layer 2 also has a top-level `agents` package — one interpreter can only hold one of them.
When another layer's `agents` is already loaded (e.g. `pytest tests`), these tests are skipped
with a hint instead of failing on confusing import errors.
"""
from __future__ import annotations

import sys
from pathlib import Path

LAYER5_DIR = Path(__file__).resolve().parents[2] / "src" / "backend" / "workflow" / "layer5"

_agents = sys.modules.get("agents")
_agents_dir = Path(next(iter(getattr(_agents, "__path__", [])), "")).resolve() if _agents else None

if _agents_dir is not None and _agents_dir.parent != LAYER5_DIR:
    collect_ignore_glob = ["test_*.py"]
    print("\n[tests/layer5] skipped in this session — run `pytest tests/layer5` on its own.", file=sys.stderr)
elif str(LAYER5_DIR) not in sys.path:
    sys.path.insert(0, str(LAYER5_DIR))
