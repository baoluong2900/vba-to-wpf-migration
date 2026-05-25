import json
import os
from typing import TypedDict, Annotated, List, Optional
from langgraph.graph import StateGraph, END
from config import (
    GROQ_API_KEY,
    MEGALLM_API_KEY,
    ModelConfig,
    TARGET_LANGUAGE
)
from utils.logger import get_logger
from utils.cost_tracker import get_tracker
from utils.llm_client import LLMClient

logger = get_logger(__name__)

# --- State Definition ---
class LogicState(TypedDict):
    module_id: str
    title: str
    code: str
    queries: List[dict]
    model_cfg: ModelConfig
    analysis_result: Optional[dict]
    error: Optional[str]
    retry_count: int
    raw_response: Optional[str]

# --- Prompt ---
def _get_system_prompt() -> str:
    lang = "English" if TARGET_LANGUAGE.lower() in ("en", "english") else "Japanese"
    lang_rule = "English" if TARGET_LANGUAGE.lower() in ("en", "english") else "Japanese (日本語)"
    forbidden = (
        'e.g., "Open screen", "Update data", "Show message", "Print"'
        if TARGET_LANGUAGE.lower() in ("en", "english")
        else 'e.g., "画面を開く", "データを更新する", "メッセージを表示する", "印刷する"'
    )
    return f"""\
You are an expert {lang} technical documentation writer specializing in Microsoft Access VBA and SQL.

Your task: Given a VBA procedure and its related SQL queries, write a very brief one-sentence summary in {lang} of what the code does from a business/operations perspective.

OUTPUT FORMAT (strict JSON):
{{
  "module_id": "<same as input>",
  "event_content": "<one-sentence summary>",
  "action_type": "<MUST be one of: READ, CREATE, UPDATE, DELETE, NAV, UI, VALID, FILE, SYS, ETC>",
  "notes": "<any important business/operational notes, warnings, or constraints. leave empty string if none>"
}}

RULES:
- The summary and notes MUST be in {lang_rule}.
- Keep event_content extremely brief (max 1 sentence).
- ALWAYS describe what the code does from a BUSINESS/USER perspective.
- STRICTLY FORBIDDEN in BOTH event_content and notes: raw VBA code, variable names, or technical jargon. Translate them into natural business actions ({forbidden}).
- ALWAYS describe what the code does. Do NOT return an empty string for event_content.

- action_type MUST strictly follow the list above. Do NOT create new types.
- Output ONLY the JSON object.
"""


# --- Nodes ---

def preprocess_node(state: LogicState) -> LogicState:
    """Truncate code and SQL to fit in context/rate limits."""
    code = state["code"]
    if len(code) > 4000:
        state["code"] = code[:4000] + "\n...(VBA truncated)"
    
    for q in state["queries"]:
        sql = q.get("sql", "")
        if len(sql) > 500:
            q["sql"] = sql[:500] + "...(SQL truncated)"
    
    return state

# (Langchain factories deleted, using LLMClient instead)


def analyze_node(state: LogicState) -> LogicState:
    """Call the LLM to analyze the code."""
    cfg = state["model_cfg"]

    query_lines = [f"[{q.get('query_name', '')}]\n{q.get('sql', '')}" for q in state.get("queries", [])]
    query_block = "\n\n".join(query_lines) if query_lines else "なし"
    
    user_content = (
        f"Module ID: {state['module_id']}\n"
        f"Title: {state['title']}\n\n"
        f"=== VBA Code ===\n{state['code']}\n\n"
        f"=== Related SQL Queries ===\n{query_block}\n\n"
        "分析結果をJSONで出力してください。"
    )

    try:
        client = LLMClient()
        raw, usage = client.chat_with_usage(cfg, _get_system_prompt(), user_content)
        state["raw_response"] = raw
        state["error"] = None
        
        # Record usage in Layer 2 Cost Tracker
        tracker = get_tracker()
        tracker.record(
            item_name=state["module_id"],
            model_id=cfg.model_id,
            stage="bd_logic",
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            flow_type="BD Agent",
        )
    except Exception as e:
        state["error"] = str(e)
        logger.error(f"LLM Error: {e}")
    
    return state

def validate_node(state: LogicState) -> LogicState:
    """Parse JSON and validate Japanese content."""
    raw = state.get("raw_response", "")
    if not raw:
        state["error"] = "Empty response from LLM"
        return state
    
    try:
        # Simple cleanup if markdown fences are present
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        
        data = json.loads(raw.strip())
        
        # Fallback if field name is different
        event_content = data.get("event_content")
        if event_content is None:
            event_content = data.get("summary") or data.get("notes") or data.get("behavior") or ""
            
        def _flatten(obj):
            if isinstance(obj, str):
                return obj
            elif isinstance(obj, list):
                return " ".join([_flatten(x) for x in obj if x])
            elif isinstance(obj, dict):
                return " ".join([_flatten(v) for v in obj.values() if v])
            return str(obj)
            
        event_content = _flatten(event_content).strip()
        action_type = _flatten(data.get("action_type", "")).strip()
        notes = _flatten(data.get("notes", "")).strip()
        
        state["analysis_result"] = {
            "module_id": state["module_id"],
            "event_content": event_content,
            "action_type": action_type,
            "notes": notes
        }
        state["error"] = None
    except Exception as e:
        state["error"] = f"JSON Parse Error: {e}"
        logger.warning(f"Validation failed: {e}")
    
    return state

# --- Edge Logic ---

def retry_node(state: LogicState) -> LogicState:
    """Increment retry counter as a proper graph node (mutations in edge functions don't persist in LangGraph)."""
    new_count = state["retry_count"] + 1
    logger.info(f"Retrying analysis for {state['module_id']} (Attempt {new_count})")
    return {**state, "retry_count": new_count}

def should_retry(state: LogicState) -> str:
    """Pure routing function — reads state only, NEVER mutates it."""
    if state["error"] and state["retry_count"] < 2:
        return "retry"
    return END

# --- Graph Creation ---

workflow = StateGraph(LogicState)

workflow.add_node("preprocess", preprocess_node)
workflow.add_node("analyze", analyze_node)
workflow.add_node("validate", validate_node)
workflow.add_node("retry", retry_node)

workflow.set_entry_point("preprocess")
workflow.add_edge("preprocess", "analyze")
workflow.add_edge("analyze", "validate")
workflow.add_edge("retry", "analyze")

workflow.add_conditional_edges(
    "validate",
    should_retry,
    {
        "retry": "retry",
        END: END
    }
)

app = workflow.compile()

# --- Batch Prompt ---
def _get_batch_system_prompt() -> str:
    lang = "English" if TARGET_LANGUAGE.lower() in ("en", "english") else "Japanese"
    return f"""\
You are an expert {lang} technical documentation writer specializing in Microsoft Access VBA and SQL.

Your task: Given a list of VBA procedures and their related SQL queries, write a very brief one-sentence summary in {lang} for EACH procedure from a business/operations perspective.

OUTPUT FORMAT (strict JSONL - one JSON object per line):
{{"module_id": "...", "event_content": "...", "action_type": "...", "notes": "..."}}

RULES:
- Return the results in JSONL format (JSON Lines).
- Each line MUST be a complete valid JSON object.
- Keep event_content extremely brief (max 1 sentence).
- ALWAYS describe what the code does from a BUSINESS/USER perspective.
- STRICTLY FORBIDDEN: raw VBA code, variable names, or technical jargon. Translate them into natural business actions.
- action_type MUST be one of: READ, CREATE, UPDATE, DELETE, NAV, UI, VALID, FILE, SYS, ETC.
- Output ONLY the JSONL lines. Do not include markdown fences.
"""



# --- Public API ---

class BDLogicGraph:
    def run_logic(self, logic_item: dict, model_id: str = None) -> dict:
        from config import AVAILABLE_MODELS, DEV_MODEL
        model_cfg = AVAILABLE_MODELS.get(model_id, DEV_MODEL) if model_id else DEV_MODEL
        
        initial_state: LogicState = {
            "module_id": logic_item.get("module_id", "unknown"),
            "title": logic_item.get("title", ""),
            "code": logic_item.get("code", ""),
            "queries": logic_item.get("queries", []),
            "model_cfg": model_cfg,
            "analysis_result": None,
            "error": None,
            "retry_count": 0,
            "raw_response": None
        }
        
        final_state = app.invoke(initial_state, config={"recursion_limit": 25})
        
        if final_state["analysis_result"]:
            return final_state["analysis_result"]

        # Graceful fallback — derive description from title/module_id instead of writing ERROR into doc
        title = logic_item.get("title", "") or logic_item.get("module_id", "")
        fallback_content = f"{title}の処理を実行する" if title else "処理を実行する"
        logger.warning(
            f"LLM failed for '{initial_state['module_id']}' after retries "
            f"({final_state['error']}). Using fallback description."
        )
        return {
            "module_id": initial_state["module_id"],
            "event_content": fallback_content,
            "action_type": "ETC",
            "notes": f"[自動生成] LLM分析失敗のためタイトルから生成。エラー: {final_state['error']}"
        }

    def run_logic_batch(self, logic_items: list[dict], model_id: str = None) -> list[dict]:
        """Process multiple logic items in a single LLM call for efficiency."""
        from config import AVAILABLE_MODELS, DEV_MODEL
        model_cfg = AVAILABLE_MODELS.get(model_id, DEV_MODEL) if model_id else DEV_MODEL
        
        # Build combined user prompt in JSONL format
        items_block = []
        for item in logic_items:
            q_list = [{"query_name": q.get('query_name', ''), "sql": str(q.get('sql', ''))[:500]} for q in item.get("queries", [])]
            compact_item = {
                "module_id": item.get("module_id"),
                "title": item.get("title"),
                "code": item.get("code", "")[:2000],
                "queries": q_list
            }
            items_block.append(json.dumps(compact_item, ensure_ascii=False))

        user_content = "\n".join(items_block) + "\n\n上記すべての項目の分析結果をJSONL形式で出力してください。"

        try:
            client = LLMClient()
            raw, usage = client.chat_with_usage(model_cfg, _get_batch_system_prompt(), user_content)
            
            # Token tracking for batch
            batch_label = ",".join(i.get("module_id", "?") for i in logic_items)
            tracker = get_tracker()
            tracker.record(
                item_name=f"batch[{batch_label[:60]}]",
                model_id=model_cfg.model_id,
                stage="bd_logic_batch",
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                flow_type="BD Agent",
            )
            # Parse JSONL
            results = []
            for line in raw.splitlines():
                line = line.strip()
                if not line: continue
                try:
                    # Remove potential markdown garbage if LLM ignored "ONLY" rule
                    if line.startswith("```"): continue
                    if line.endswith("```"): continue
                    
                    results.append(json.loads(line))
                except Exception as e:
                    logger.warning(f"Failed to parse JSONL line: {line}. Error: {e}")
                    continue
            
            if not results:
                raise ValueError("No valid JSONL results parsed")
            return results
        except Exception as e:
            logger.error(f"Batch Analysis Error: {e}")
            # Fallback to one-by-one if batch failed
            logger.info("Falling back to one-by-one processing for this batch.")
            return [self.run_logic(item, model_id) for item in logic_items]


# --- Screen Summary API ---

def _get_summary_system_prompt() -> str:
    lang = "English" if TARGET_LANGUAGE.lower() in ("en", "english") else "Japanese"
    timing_eg = (
        "when the user logs in"
        if TARGET_LANGUAGE.lower() in ("en", "english")
        else "ユーザーがシステムにログインする時"
    )
    return f"""\
You are an expert {lang} technical documentation writer specializing in Microsoft Access VBA and SQL.

Your task: Given the name of a screen (form) and the logic descriptions of its events, generate a high-level overview of the screen.

OUTPUT FORMAT (strict JSON):
{{
  "description": "<1-2 sentences describing the main purpose of this screen>",
  "timing": "<When is this screen used? e.g., {timing_eg}>",
  "constraints": "<Any preconditions or constraints? If none, leave empty string>",
  "process_overview": [
    {{"summary_line": "<step 1 of the main business flow>"}},
    {{"summary_line": "<step 2 of the main business flow>"}}
  ]
}}

RULES:
- The output MUST be in {lang}.
- ALWAYS describe the screen and process from a BUSINESS/USER perspective.
- STRICTLY FORBIDDEN: raw VBA code, variable names, or technical jargon. Translate them into natural business actions.
- Output ONLY the JSON object. Do not wrap in ```json or markdown.
"""


class BDScreenSummaryGraph:
    def run_summary(self, screen_name: str, logic_results: list, model_id: str = None, mapped_data: dict = None, ui_formulas_translated: list = None) -> dict:
        from config import AVAILABLE_MODELS, DEV_MODEL
        from pathlib import Path
        
        proj_root = Path(__file__).resolve().parent.parent
        s3_dir = proj_root / "output" / "bd_flow" / "s3_bd_logic"
        s3_dir.mkdir(parents=True, exist_ok=True)
        
        model_cfg = AVAILABLE_MODELS.get(model_id, DEV_MODEL) if model_id else DEV_MODEL
        
        # (Using LLMClient instead of direct build)

        # Format events into compact text
        events_text = "\n".join([f"- {item.get('module_id')}: {item.get('event_content')}" for item in logic_results if item.get('event_content')])
        
        # Build a lookup: item_no (str) -> translated_description from ui_formulas_translated
        formula_lookup: dict[str, str] = {}
        if ui_formulas_translated:
            for f in ui_formulas_translated:
                item_no = str(f.get("item_no", ""))
                desc = f.get("translated_description", "")
                if item_no and desc:
                    formula_lookup[item_no] = desc

        ui_elements_text = "なし"
        if mapped_data:
            items = []
            seen_nos = set()
            raw_items = []
            
            def recurse_items(node):
                if isinstance(node, dict):
                    no = str(node.get('no', node.get('item_no', '')))
                    name = node.get('logical_name', '') or node.get('output_field_name', '')
                    if name and no not in seen_nos:
                        seen_nos.add(no)
                        src_tbl = node.get('source_table', '')
                        src = node.get('source_field_or_fixed_value', '')
                        cond = formula_lookup.get(no) or node.get('condition_and_format', '')
                        
                        raw_items.append({
                            "no": no,
                            "output_field_name": name,
                            "source_table": src_tbl,
                            "source_field_or_fixed_value": src,
                            "condition_and_format": cond
                        })
                    
                    for k, v in node.items():
                        recurse_items(v)
                elif isinstance(node, list):
                    for v in node:
                        recurse_items(v)
                        
            recurse_items(mapped_data)
            
            if raw_items:
                # Group by source_table for the LLM prompt
                table_groups = {}
                for r_item in raw_items:
                    tbl = r_item["source_table"].strip() if r_item.get("source_table") else "Unspecified Table"
                    tbl = tbl.replace("\n", ", ")
                    if tbl not in table_groups:
                        table_groups[tbl] = []
                    table_groups[tbl].append(r_item)
                
                grouped_texts = []
                for tbl, tbl_items in table_groups.items():
                    grouped_texts.append(f"Source Table: {tbl}")
                    for item in tbl_items:
                        name = item["output_field_name"]
                        src = item["source_field_or_fixed_value"]
                        cond = item["condition_and_format"]
                        
                        text = f"  - {name}"
                        if src: 
                            clean_src = src.replace('\n', ', ')
                            text += f" → {clean_src}"
                        if cond: 
                            text += f" ({cond})"
                        grouped_texts.append(text)
                        
                ui_elements_text = "\n".join(grouped_texts[:150])
                
                # Sort raw_items by source_table for the user's JSONL file
                raw_items.sort(key=lambda x: x.get("source_table", ""))
                
            # Dump raw_items grouped by source_table to JSONL in s3_bd_logic to save tokens for the user
            try:
                jsonl_path = s3_dir / f"ui_items_{screen_name}.jsonl"
                with open(jsonl_path, "w", encoding="utf-8") as f:
                    for tbl, tbl_items in table_groups.items():
                        grouped_items = []
                        for item in tbl_items:
                            cleaned_item = {
                                "no": item["no"],
                                "output_field_name": item["output_field_name"]
                            }
                            if item.get("source_field_or_fixed_value"):
                                cleaned_item["source_field_or_fixed_value"] = item["source_field_or_fixed_value"]
                            if item.get("condition_and_format"):
                                cleaned_item["condition_and_format"] = item["condition_and_format"]
                            grouped_items.append(cleaned_item)
                            
                        grouped_record = {
                            "source_table": tbl,
                            "items": grouped_items
                        }
                        f.write(json.dumps(grouped_record, ensure_ascii=False) + "\n")
            except Exception as e:
                logger.warning(f"Failed to write ui_items JSONL file: {e}")
        
        user_content = (
            f"Screen Name: {screen_name}\n\n"
            f"=== Event Logic Summaries ===\n"
            f"{events_text or 'なし'}\n\n"
            f"=== UI Elements (Captions) ===\n"
            f"{ui_elements_text}\n\n"
            "画面全体の仕様概要をJSONで出力してください。Eventがない場合は、画面名とUI要素（Captions）から推測して画面の目的を記述してください。"
        )

        try:
            client = LLMClient()
            raw, usage = client.chat_with_usage(model_cfg, _get_summary_system_prompt(), user_content)
            raw = raw.strip()
            
            # Token tracking for screen summary
            tracker = get_tracker()
            tracker.record(
                item_name=screen_name,
                model_id=model_cfg.model_id,
                stage="bd_screen_summary",
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                flow_type="BD Agent",
            )
            # Simple cleanup if markdown fences are present
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()
                
            parsed_result = json.loads(raw)
            
            # Dump parsed_result to JSONL in s3_bd_logic
            try:
                result_jsonl_path = s3_dir / f"ui_items_{screen_name}_result.jsonl"
                with open(result_jsonl_path, "w", encoding="utf-8") as f:
                    f.write(json.dumps(parsed_result, ensure_ascii=False) + "\n")
            except Exception as e:
                logger.warning(f"Failed to write ui_items result JSONL file: {e}")
                
            return parsed_result
        except Exception as e:
            logger.error(f"Screen Summary Error: {e}")
            err_result = {
                "description": f"Error generating summary: {e}",
                "timing": "",
                "constraints": "",
                "process_overview": []
            }
            try:
                result_jsonl_path = s3_dir / f"ui_items_{screen_name}_result.jsonl"
                with open(result_jsonl_path, "w", encoding="utf-8") as f:
                    f.write(json.dumps(err_result, ensure_ascii=False) + "\n")
            except Exception:
                pass
            return err_result
