import json
from typing import TypedDict, Any
from langgraph.graph import StateGraph, END

from utils.logger import get_logger
from utils.llm_client import LLMClient
from config import ModelConfig, DEV_MODEL

logger = get_logger(__name__)

class UIFormulaBatchState(TypedDict):
    batch: list[dict]
    model_cfg: ModelConfig
    translated_batch: list[dict] | None
    raw_response: str | None
    error: str | None
    retry_count: int

def _clean_formula(formula: str) -> str:
    """Normalize over-escaped Access formula strings before sending to LLM.
    
    S2 JSON stores formulas with double/triple-escaped backslashes like:
        =Format([受付日],\\\"yyyy\\\\年m\\\\月d\\\\日\\\")
    After Python JSON-parsing, still contains:  =Format([受付日],\"yyyy\\年m\\月d\\日\")
    This cleans it to:  =Format([受付日],"yyyy年m月d日")
    """
    import re
    # Replace \" with " (unescape escaped quotes)
    cleaned = formula.replace('\\"', '"')
    # Replace \\ with empty (remove extra backslashes used as escape in format strings)
    cleaned = cleaned.replace('\\', '')
    return cleaned.strip()

def preprocess_batch_node(state: UIFormulaBatchState):
    return state

def analyze_batch_node(state: UIFormulaBatchState):
    if state["retry_count"] > 0:
        logger.warning(f"UI Batch Analyze: retry #{state['retry_count']}")
        
    client = LLMClient()
    
    # Prepare input as JSONL with minimal context (only item_no and formula)
    lines = []
    for item in state["batch"]:
        payload = {
            "item_no": str(item.get("item_no", "")),
            "formula": _clean_formula(str(item.get("formula", "")))
        }
        lines.append(json.dumps(payload, ensure_ascii=False))
        
    user_content = "\n".join(lines)
    
    try:
        response_text = client.chat(
            model_cfg=state["model_cfg"],
            system=_UI_BATCH_SYSTEM_PROMPT,
            user=f"Formulas to translate:\n{user_content}"
        )
        state["raw_response"] = response_text
    except Exception as e:
        state["error"] = f"LLM Error: {e}"
        logger.error(f"UI Batch LLM Error: {e}")
        
    return state

_UI_BATCH_SYSTEM_PROMPT = """\
You are a Japanese technical documentation writer specializing in Microsoft Access.

Your task: Given a JSONL list of UI items containing 'item_no' and their Access 'formula' (e.g., =Date(), =InStr(...)), translate the formulas into natural Japanese business descriptions.
DO NOT OUTPUT THE ORIGINAL FORMULA. YOU MUST TRANSLATE IT TO NATURAL LANGUAGE.

OUTPUT FORMAT: Strict JSONL (JSON Lines). Each line must be a valid JSON object.
Example Output:
{"item_no": "1", "translated_description": "現在の日付を表示する"}
{"item_no": "6", "translated_description": "条件に応じて〇か×を表示する"}

RULES:
- The description MUST be in Japanese.
- Return ONLY JSONL format. No markdown fences, no extra text.
- Keep the description extremely brief (max 1 sentence).
- ALWAYS describe what the formula does from a BUSINESS/USER perspective (業務目線・ユーザー視点).
- STRICTLY FORBIDDEN: raw VBA code, Access functions, variable names, or technical jargon (e.g., InStr, DateDiff, IIf, Nz, Format, &, +, []). Translate them into natural business actions.
- IF THE FORMULA IS JUST A FIELD NAME (e.g. =[Field]), translate it to "「Field」を表示する".
- WHEN the description mentions a field name (from inside [] in the formula), ALWAYS wrap it in 「」 brackets (e.g. 「受付日」、「訪問先都道府県」).
- NEVER return the original formula as the translation.

TRANSLATION EXAMPLES (Input JSONL → Expected Output JSONL):
Input:  {"item_no": "1", "formula": "=Format([受付日],\\"yyyy年m月d日\\") & Format([ＡＭ受付時刻],\\"h時n分\\")"}
Output: {"item_no": "1", "translated_description": "「受付日」と「ＡＭ受付時刻」を結合してyyyy年m月d日h時n分形式で表示する"}

Input:  {"item_no": "59", "formula": "=Format([作業日],\\"yyyy年m月d日\\")"}
Output: {"item_no": "59", "translated_description": "「作業日」をyyyy年m月d日形式で表示する"}

Input:  {"item_no": "6", "formula": "=Nz([訪問先都道府県],\\"\\")+Nz([訪問先市町村],\\"\\")+Nz([訪問先町名番地],\\"\\")+Nz([訪問先建物名],\\"\\")"}
Output: {"item_no": "6", "translated_description": "「訪問先都道府県」「訪問先市町村」「訪問先町名番地」「訪問先建物名」を結合して訪問先の完全住所を表示する"}
"""

def validate_batch_node(state: UIFormulaBatchState):
    if state["error"]:
        return state
        
    raw = state.get("raw_response", "")
    try:
        results = []
        
        # 1. Try parsing as a standard JSON array first
        clean_raw = raw.strip()
        if "```json" in clean_raw:
            clean_raw = clean_raw.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_raw:
            clean_raw = clean_raw.split("```")[1].split("```")[0].strip()
            
        try:
            parsed = json.loads(clean_raw)
            if isinstance(parsed, list):
                results = parsed
            elif isinstance(parsed, dict) and "results" in parsed:
                results = parsed["results"]
        except Exception:
            pass

        # 2. If it failed, try parsing as JSONL
        if not results:
            for line in raw.strip().split("\n"):
                line = line.strip()
                if not line or line.startswith("```") or line == "[" or line == "]":
                    continue
                
                if line.endswith(","):
                    line = line[:-1].strip()
                    
                if line.startswith("{") and line.endswith("}"):
                    try:
                        data = json.loads(line)
                        results.append(data)
                    except Exception:
                        pass
        
        cleaned_results = []
        for item in results:
            if "item_no" in item and "translated_description" in item:
                cleaned_results.append({
                    "item_no": str(item.get("item_no", "")),
                    "translated_description": str(item.get("translated_description", "")).strip()
                })
            
        state["translated_batch"] = cleaned_results
        
        # If we couldn't parse anything but there was raw input, it's an error
        if not cleaned_results and raw.strip():
            state["error"] = "Failed to parse LLM output as JSON or JSONL."
        else:
            state["error"] = None
            
    except Exception as e:
        state["error"] = f"JSON Parse Error: {e}"
        logger.warning(f"UI Batch Validation failed: {e}")
        
    return state

def should_retry_batch(state: UIFormulaBatchState):
    if state["error"] and state["retry_count"] < 2:
        state["retry_count"] += 1
        return "analyze"
    return END

workflow = StateGraph(UIFormulaBatchState)
workflow.add_node("preprocess", preprocess_batch_node)
workflow.add_node("analyze", analyze_batch_node)
workflow.add_node("validate", validate_batch_node)

workflow.set_entry_point("preprocess")
workflow.add_edge("preprocess", "analyze")
workflow.add_edge("analyze", "validate")

workflow.add_conditional_edges(
    "validate",
    should_retry_batch,
    {
        "analyze": "analyze",
        END: END
    }
)

app = workflow.compile()

class BDUIFormulaGraph:
    def run_ui_batch(self, batch: list[dict], model_id: str = None) -> list[dict]:
        if not batch:
            return []
            
        from config import AVAILABLE_MODELS
        model_cfg = AVAILABLE_MODELS.get(model_id, DEV_MODEL) if model_id else DEV_MODEL
        
        initial_state: UIFormulaBatchState = {
            "batch": batch,
            "model_cfg": model_cfg,
            "translated_batch": None,
            "raw_response": None,
            "error": None,
            "retry_count": 0
        }
        
        final_state = app.invoke(initial_state)
        
        # Check if translated_batch is explicitly not None (empty list is fine if input was empty)
        if final_state.get("translated_batch") is not None:
            # Map back using item_no
            translated_dict = {item["item_no"]: item["translated_description"] for item in final_state["translated_batch"] if item.get("item_no")}
            
            merged_results = []
            for item in batch:
                item_no = str(item.get("item_no", ""))
                # If translation is missing or empty, keep the original formula to avoid blank outputs
                translated_desc = translated_dict.get(item_no)
                if not translated_desc:
                    translated_desc = item.get("formula", "")
                
                merged_results.append({
                    **item,
                    "translated_description": translated_desc
                })
            return merged_results
        else:
            logger.error(f"Batch Analysis Error: {final_state.get('error')}")
            return [{**item, "translated_description": item.get("formula", "")} for item in batch]
