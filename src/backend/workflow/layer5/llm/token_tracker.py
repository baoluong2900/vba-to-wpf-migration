"""
llm/token_tracker.py — Layer 5 Token & Cost Tracker

Singleton per-session. Accumulates:
  - prompt_tokens / completion_tokens / total_tokens per LLM call
  - Per agent:  repo | service | logic | ui
  - Per form:   F_Login | C000_MAINII | ...

Usage:
    from llm.token_tracker import get_tracker
    tracker = get_tracker()
    tracker.record(form_name="F_Login", agent="logic", task_type="viewmodel",
                   model_id="qwen3-235b", prompt_tokens=1200, completion_tokens=800)
    tracker.log_summary()
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Pricing: USD per 1M tokens (input/output separate)
# DashScope Qwen3 coder pricing (approximate, international region)
# ──────────────────────────────────────────────
_PRICE_INPUT_PER_1M: dict[str, float] = {
#     "qwen3-coder-plus":                    0.56,   # $0.56/1M input
    "qwen3-coder-480b-a35b-instruct":      1.40,   # $1.40/1M input
#     "qwen3-coder-next":                    0.14,   # $0.14/1M input
    "qwen3-235b-a22b-instruct-2507":       0.56,   # $0.56/1M input
    "default":                             1.00,
}

_PRICE_OUTPUT_PER_1M: dict[str, float] = {
#     "qwen3-coder-plus":                    2.24,   # $2.24/1M output
    "qwen3-coder-480b-a35b-instruct":      5.60,   # $5.60/1M output
#     "qwen3-coder-next":                    0.56,   # $0.56/1M output
    "qwen3-235b-a22b-instruct-2507":       2.24,   # $2.24/1M output
    "default":                             2.00,
}


@dataclass
class TokenRecord:
    """One LLM call record."""
    form_name:         str
    agent:             str       # repo | service | logic | ui
    task_type:         str       # service | viewmodel | repository | view_xaml | ...
    model_id:          str
    prompt_tokens:     int
    completion_tokens: int
    total_tokens:      int
    cost_input_usd:    float
    cost_output_usd:   float
    cost_usd:          float
    timestamp:         str = field(default_factory=lambda: datetime.now().strftime("%H:%M:%S"))


@dataclass
class TokenTracker:
    """
    Accumulates token usage across all LLM calls in one workflow run.
    Use get_tracker() to get the session singleton.
    """
    records: list[TokenRecord] = field(default_factory=list)

    def __post_init__(self):
        """Load existing report from disk if it exists."""
        self.load()

    def load(self) -> None:
        """Load records from token_report.json."""
        from core.config import LAYER5_DIR
        report_path = LAYER5_DIR / "logs" / "token_report.json"
        if not report_path.exists():
            return

        try:
            data = json.loads(report_path.read_text(encoding="utf-8"))
            records_data = data.get("records", [])
            new_records = []
            for r in records_data:
                # Reconstruct TokenRecord from dict
                prompt_tok = r.get("prompt_tokens", 0)
                compl_tok  = r.get("completion_tokens", 0)
                total_tok  = r.get("total_tokens", prompt_tok + compl_tok)
                cost_usd   = r.get("cost_usd", 0.0)
                
                # We don't have separate input/output cost in JSON yet, so we split or estimate
                # For persistence, we just need the values back
                new_records.append(TokenRecord(
                    form_name=r.get("form_name", "unknown"),
                    agent=r.get("agent", "unknown"),
                    task_type=r.get("task_type", "unknown"),
                    model_id=r.get("model_id", "unknown"),
                    prompt_tokens=prompt_tok,
                    completion_tokens=compl_tok,
                    total_tokens=total_tok,
                    cost_input_usd=0.0, # Placeholder
                    cost_output_usd=0.0, # Placeholder
                    cost_usd=cost_usd,
                    timestamp=r.get("timestamp", "")
                ))
            self.records = new_records
            logger.debug("[TokenTracker] Loaded %d records from %s", len(self.records), report_path)
        except Exception as e:
            logger.error("[TokenTracker] Failed to load report: %s", e)

    # ── Core record API ───────────────────────────────────────────

    def record(
        self,
        form_name: str,
        agent: str,
        task_type: str,
        model_id: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: Optional[int] = None,
    ) -> None:
        """Record one LLM API call with token usage."""
        total = total_tokens or (prompt_tokens + completion_tokens)

        rate_in  = _PRICE_INPUT_PER_1M.get(model_id, _PRICE_INPUT_PER_1M["default"])
        rate_out = _PRICE_OUTPUT_PER_1M.get(model_id, _PRICE_OUTPUT_PER_1M["default"])

        cost_in  = (prompt_tokens     / 1_000_000) * rate_in
        cost_out = (completion_tokens / 1_000_000) * rate_out
        cost     = cost_in + cost_out

        rec = TokenRecord(
            form_name=form_name,
            agent=agent,
            task_type=task_type,
            model_id=model_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total,
            cost_input_usd=cost_in,
            cost_output_usd=cost_out,
            cost_usd=cost,
        )
        self.records.append(rec)
        
        # Persist immediately since script might exit soon
        try:
            self.save_report()
        except Exception as e:
            logger.warning("[TokenTracker] Auto-save failed: %s", e)

        logger.info(
            "[TokenTracker] 📊 [%s][%s/%s] model=%s  "
            "in=%d out=%d total=%d  $%.5f",
            form_name, agent, task_type, model_id,
            prompt_tokens, completion_tokens, total, cost,
        )

    # ── Aggregation helpers ────────────────────────────────────────

    @property
    def total_prompt_tokens(self) -> int:
        return sum(r.prompt_tokens for r in self.records)

    @property
    def total_completion_tokens(self) -> int:
        return sum(r.completion_tokens for r in self.records)

    @property
    def total_tokens(self) -> int:
        return sum(r.total_tokens for r in self.records)

    @property
    def total_cost_usd(self) -> float:
        return sum(r.cost_usd for r in self.records)

    def summary_per_form(self) -> dict[str, dict]:
        """Tokens + cost grouped by form_name."""
        out: dict[str, dict] = {}
        for r in self.records:
            key = r.form_name
            if key not in out:
                out[key] = {"prompt": 0, "completion": 0, "total": 0, "cost_usd": 0.0, "calls": 0}
            out[key]["prompt"]     += r.prompt_tokens
            out[key]["completion"] += r.completion_tokens
            out[key]["total"]      += r.total_tokens
            out[key]["cost_usd"]   += r.cost_usd
            out[key]["calls"]      += 1
        return out

    def summary_per_agent(self) -> dict[str, dict]:
        """Tokens + cost grouped by agent."""
        out: dict[str, dict] = {}
        for r in self.records:
            key = r.agent
            if key not in out:
                out[key] = {"prompt": 0, "completion": 0, "total": 0, "cost_usd": 0.0, "calls": 0}
            out[key]["prompt"]     += r.prompt_tokens
            out[key]["completion"] += r.completion_tokens
            out[key]["total"]      += r.total_tokens
            out[key]["cost_usd"]   += r.cost_usd
            out[key]["calls"]      += 1
        return out

    def summary_per_form_agent(self) -> dict[str, dict]:
        """Tokens grouped by (form_name, agent)."""
        out: dict[str, dict] = {}
        for r in self.records:
            key = f"{r.form_name} / {r.agent}"
            if key not in out:
                out[key] = {"prompt": 0, "completion": 0, "total": 0, "cost_usd": 0.0, "calls": 0}
            out[key]["prompt"]     += r.prompt_tokens
            out[key]["completion"] += r.completion_tokens
            out[key]["total"]      += r.total_tokens
            out[key]["cost_usd"]   += r.cost_usd
            out[key]["calls"]      += 1
        return out

    # ── Log summary ────────────────────────────────────────────────

    def log_summary(self, title: str = "Session") -> None:
        """Print a formatted token + cost summary to logger."""
        if not self.records:
            logger.info("[TokenTracker] No records — no LLM calls tracked.")
            return

        sep = "─" * 72
        logger.info("")
        logger.info("┌%s┐", "─" * 70)
        logger.info("│  📊 TOKEN USAGE SUMMARY — %s%s│", title, " " * max(0, 42 - len(title)))
        logger.info("├%s┤", "─" * 70)

        # ── Per-agent breakdown ──────────────────────────────────
        logger.info("│  BY AGENT:%s│", " " * 60)
        per_agent = self.summary_per_agent()
        for agent, s in per_agent.items():
            logger.info(
                "│    %-12s  calls=%-3d  in=%-8d  out=%-8d  total=%-9d  $%.4f  │",
                agent, s["calls"], s["prompt"], s["completion"], s["total"], s["cost_usd"],
            )

        logger.info("├%s┤", "─" * 70)

        # ── Per-form breakdown ───────────────────────────────────
        logger.info("│  BY FORM:%s│", " " * 61)
        per_form = self.summary_per_form()
        for form, s in per_form.items():
            logger.info(
                "│    %-20s  calls=%-3d  in=%-8d  out=%-8d  total=%-9d  $%.4f  │",
                form[:20], s["calls"], s["prompt"], s["completion"], s["total"], s["cost_usd"],
            )

        logger.info("├%s┤", "─" * 70)

        # ── Per-form × agent detail ──────────────────────────────
        logger.info("│  BY FORM × AGENT:%s│", " " * 53)
        per_fa = self.summary_per_form_agent()
        for key, s in per_fa.items():
            logger.info(
                "│    %-30s  in=%-8d  out=%-8d  total=%-9d  $%.4f  │",
                key[:30], s["prompt"], s["completion"], s["total"], s["cost_usd"],
            )

        logger.info("├%s┤", "─" * 70)

        # ── Grand total ──────────────────────────────────────────
        logger.info(
            "│  TOTAL  calls=%-3d  prompt=%-9d  completion=%-9d  tokens=%-9d  $%.4f  │",
            len(self.records),
            self.total_prompt_tokens,
            self.total_completion_tokens,
            self.total_tokens,
            self.total_cost_usd,
        )
        logger.info("└%s┘", "─" * 70)
        logger.info("")

    def log_form_summary(self, form_name: str) -> None:
        """Log token summary for a single form after it completes."""
        recs = [r for r in self.records if r.form_name == form_name]
        if not recs:
            return

        prompt     = sum(r.prompt_tokens     for r in recs)
        completion = sum(r.completion_tokens for r in recs)
        total      = sum(r.total_tokens      for r in recs)
        cost       = sum(r.cost_usd          for r in recs)

        # Per-agent for this form
        by_agent: dict[str, dict] = {}
        for r in recs:
            if r.agent not in by_agent:
                by_agent[r.agent] = {"prompt": 0, "completion": 0, "calls": 0}
            by_agent[r.agent]["prompt"]     += r.prompt_tokens
            by_agent[r.agent]["completion"] += r.completion_tokens
            by_agent[r.agent]["calls"]      += 1

        logger.info(
            "[TokenTracker] ┌── 📋 Form: %-25s ──────────────────────────────────────┐",
            form_name,
        )
        for agent, s in by_agent.items():
            logger.info(
                "[TokenTracker] │  Agent %-10s  calls=%-3d  in=%-8d  out=%-8d",
                agent, s["calls"], s["prompt"], s["completion"],
            )
        logger.info(
            "[TokenTracker] └── TOTAL  calls=%-3d  in=%-8d  out=%-8d  total=%-8d  $%.4f",
            len(recs), prompt, completion, total, cost,
        )

    # ── Persist report ────────────────────────────────────────────

    def save_report(self, output_dir: Optional[Path] = None) -> str:
        """Save full token report to JSON file (append session)."""
        from core.config import LAYER5_DIR
        out_dir = output_dir or LAYER5_DIR / "logs"
        os.makedirs(out_dir, exist_ok=True)

        path = Path(out_dir) / "token_report.json"
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # New session data (current memory)
        new_session = {
            "timestamp":          ts,
            "total_calls":        len(self.records),
            "total_input_tokens":  self.total_prompt_tokens,
            "total_output_tokens": self.total_completion_tokens,
            "total_tokens":       self.total_tokens,
            "total_cost_usd":     round(self.total_cost_usd, 6),
            "per_agent":          {
                k: {**v, "cost_usd": round(v["cost_usd"], 6)}
                for k, v in self.summary_per_agent().items()
            },
            "per_form":           {
                k: {**v, "cost_usd": round(v["cost_usd"], 6)}
                for k, v in self.summary_per_form().items()
            },
            "records": [
                {
                    "form_name":         r.form_name,
                    "agent":             r.agent,
                    "task_type":         r.task_type,
                    "model_id":          r.model_id,
                    "prompt_tokens":     r.prompt_tokens,
                    "completion_tokens": r.completion_tokens,
                    "total_tokens":      r.total_tokens,
                    "cost_usd":          round(r.cost_usd, 6),
                    "timestamp":         r.timestamp,
                }
                for r in self.records
            ],
        }

        # For simplicity in Layer 5 (since it's per-agent exec), 
        # we keep the full session in memory and overwrite the json 
        # with the "latest" state. In Next.js we will read this latest state.
        path.write_text(json.dumps(new_session, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.debug("[TokenTracker] JSON report saved → %s", path)
        return str(path)

    def save_excel_report(self, output_dir: Optional[Path] = None) -> str:
        """Export session to Excel. Similar to Layer 2."""
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        except ImportError:
            logger.warning("[TokenTracker] openpyxl not installed — Excel export skipped.")
            return ""

        from core.config import LAYER5_DIR
        out_dir = output_dir or LAYER5_DIR / "logs"
        os.makedirs(out_dir, exist_ok=True)
        path = Path(out_dir) / "token_report.xlsx"
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Layer 5 Token Usage"
        
        # Header
        headers = ["Time", "Form", "Agent", "Task", "Model", "Input", "Output", "Total", "Cost (USD)"]
        ws.append(headers)
        header_fill = PatternFill("solid", fgColor="1E3A5F")
        header_font = Font(bold=True, color="FFFFFF")
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center")

        # Rows
        alt_fill = PatternFill("solid", fgColor="F3F4F6")
        for r in self.records:
            row = [r.timestamp, r.form_name, r.agent, r.task_type, r.model_id, 
                   r.prompt_tokens, r.completion_tokens, r.total_tokens, round(r.cost_usd, 6)]
            ws.append(row)
            if ws.max_row % 2 == 0:
                for cell in ws[ws.max_row]:
                    cell.fill = alt_fill

        # Auto-width
        for i, w in enumerate([10, 20, 12, 15, 25, 10, 10, 10, 12], 1):
            ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = w

        wb.save(str(path))
        logger.info("[TokenTracker] Excel report saved → %s", path)
        return str(path)

    def reset(self) -> None:
        """Reset all records (start fresh for a new run)."""
        self.records.clear()


# ── Singleton ──────────────────────────────────────────────────────
_tracker: Optional[TokenTracker] = None


def get_tracker() -> TokenTracker:
    """Return the session-level singleton TokenTracker."""
    global _tracker
    if _tracker is None:
        _tracker = TokenTracker()
    return _tracker


def reset_tracker() -> None:
    """Reset the singleton (call before each pipeline run)."""
    global _tracker
    _tracker = TokenTracker()
