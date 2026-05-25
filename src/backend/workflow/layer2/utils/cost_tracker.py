"""
llm/cost_tracker.py — Theo dõi token usage và chi phí ước tính.

Singleton: get_tracker() trả về instance dùng chung trong một session.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from config import LOG_DIR

logger = logging.getLogger(__name__)

# Chi phí ước tính theo USD / 1M tokens (input / output riêng biệt)
_PRICE_INPUT_PER_1M: dict[str, float] = {
    "gemini-2.0-flash":     0.10,
    "gemini-1.5-flash":     0.10,
    "gemini-2.5-pro":       1.25,
    "gpt-4o":               2.50,
    "gpt-4o-mini":          0.15,
    "claude-3-5-sonnet":    3.00,
    "deepseek-v3":          0.27,
    "deepseek-chat":        0.14,
    "deepseek-reasoner":    0.55,
    "qwen-max":             2.80,
    "qwen-plus":            0.56,
    "qwen-turbo":           0.04,
    "qwen-long":            0.07,
    "qwen3-coder-instruct": 0.14,
    "default":              1.00,
}

_PRICE_OUTPUT_PER_1M: dict[str, float] = {
    "gemini-2.0-flash":     0.40,
    "gemini-1.5-flash":     0.40,
    "gemini-2.5-pro":       5.00,
    "gpt-4o":               10.0,
    "gpt-4o-mini":          0.60,
    "claude-3-5-sonnet":    15.0,
    "deepseek-v3":          1.10,
    "deepseek-chat":        0.28,
    "deepseek-reasoner":    2.19,
    "qwen-max":             8.40,
    "qwen-plus":            1.68,
    "qwen-turbo":           0.11,
    "qwen-long":            0.21,
    "qwen3-coder-instruct": 0.56,
    "default":              2.00,
}


@dataclass
class TokenRecord:
    item_name: str
    model_id: str
    stage: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    flow_type: str = "Unknown"


@dataclass
class CostTracker:
    """Tracks token usage and estimated cost for a pipeline run."""
    records: list[TokenRecord] = field(default_factory=list)
    last_model_id: str = "Unknown"

    @property
    def total_input_tokens(self) -> int:
        return sum(r.input_tokens for r in self.records)

    @property
    def total_output_tokens(self) -> int:
        return sum(r.output_tokens for r in self.records)

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    @property
    def total_cost(self) -> float:
        return sum(r.cost_usd for r in self.records)

    def record(
        self,
        item_name: str,
        model_id: str,
        stage: str,
        input_tokens: int,
        output_tokens: int,
        flow_type: str = "Unknown",
    ) -> None:
        rate_in  = _PRICE_INPUT_PER_1M.get(model_id, _PRICE_INPUT_PER_1M["default"])
        rate_out = _PRICE_OUTPUT_PER_1M.get(model_id, _PRICE_OUTPUT_PER_1M["default"])
        
        self.last_model_id = model_id
        cost = (max(1, input_tokens) / 1_000_000 * rate_in) + (max(1, output_tokens) / 1_000_000 * rate_out)
        rec = TokenRecord(
            item_name=item_name,
            model_id=model_id,
            stage=stage,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            flow_type=flow_type,
        )
        self.records.append(rec)
        logger.debug(
            "[CostTracker] %s | %s | in=%d out=%d | $%.5f",
            item_name, model_id, input_tokens, output_tokens, cost,
        )

    def save_report(self, label: str = "", flow_type: str = "Unknown") -> str:
        """Lưu cost report vào file JSON chung (token_log.json), append thêm bản ghi mới."""
        path = Path(LOG_DIR) / "token_log.json"
        os.makedirs(LOG_DIR, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_session = {
            "timestamp": ts,
            "screen_name": label or "unknown",
            "flow_type": flow_type,
            "total_requests": len(self.records),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost, 6),
            "records": [
                {
                    "item": r.item_name,
                    "model": r.model_id,
                    "stage": r.stage,
                    "input_tokens": r.input_tokens,
                    "output_tokens": r.output_tokens,
                    "cost_usd": round(r.cost_usd, 6),
                    "flow_type": r.flow_type
                } for r in self.records
            ]
        }

        history = []
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    history = json.load(f)
                    if not isinstance(history, list):
                        history = [history] # Convert old format
            except Exception:
                history = []

        history.append(new_session)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
            
        logger.info("[CostTracker] JSON report appended → %s", path)
        return str(path)

    def save_excel_report(self, label: str = "", flow_type: str = "Unknown") -> str:
        """Xuất cost report vào file Excel chung (token_log.xlsx), append thêm dòng mới."""
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        except ImportError:
            logger.warning("[CostTracker] openpyxl not installed — Excel export skipped.")
            return ""

        os.makedirs(LOG_DIR, exist_ok=True)
        path = Path(LOG_DIR) / "token_log.xlsx"
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        if path.exists():
            try:
                wb = openpyxl.load_workbook(str(path))
                ws = wb.active
            except Exception:
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = "Token Usage History"
                self._create_excel_header(ws)
        else:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Token Usage History"
            self._create_excel_header(ws)

        # ── Styles ────────────────────────────────────────────────────────
        thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), 
                            top=Side(style='thin'), bottom=Side(style='thin'))
        center_align = Alignment(horizontal="center", vertical="center")
        alt_fill = PatternFill("solid", fgColor="F3F4F6")

        # ── Append Records ────────────────────────────────────────────────
        start_row = ws.max_row + 1
        for i, r in enumerate(self.records, 1):
            total_tok = r.input_tokens + r.output_tokens
            # Format: ID, Date, Flow, Screen, Item, Model, Stage, In, Out, Total, Cost
            row = [
                ws.max_row, 
                ts,
                r.flow_type,
                label,
                r.item_name,
                r.model_id,
                r.stage,
                r.input_tokens,
                r.output_tokens,
                total_tok,
                round(r.cost_usd, 6)
            ]
            ws.append(row)
            
            # Apply basic styling to the new row
            for cell in ws[ws.max_row]:
                cell.border = thin_border
                if (ws.max_row - 1) % 2 == 0:
                    cell.fill = alt_fill

        try:
            wb.save(str(path))
            logger.info("[CostTracker] Excel report appended → %s", path)
        except Exception as e:
            logger.error("[CostTracker] Failed to save Excel (maybe file is open?): %s", e)

        return str(path)

    def _create_excel_header(self, ws):
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        headers = ["ID", "Timestamp", "Flow", "Screen", "Item", "Model", "Stage", "Input", "Output", "Total", "Cost (USD)"]
        ws.append(headers)
        header_fill = PatternFill("solid", fgColor="1E3A5F")
        header_font = Font(bold=True, color="FFFFFF")
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center")
        
        # Set widths
        widths = [5, 18, 12, 25, 30, 20, 20, 10, 10, 10, 12]
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = w


# ── Singleton ──────────────────────────────────────────────────────────────
_tracker: CostTracker | None = None


def get_tracker() -> CostTracker:
    """Trả về singleton CostTracker cho session hiện tại."""
    global _tracker
    if _tracker is None:
        _tracker = CostTracker()
    return _tracker
