# -*- coding: utf-8 -*-
"""
dd_agent/dd_prompt.py — Prompt builder for DD stage (D3 LLM step)

Given one logic_item (module_id + VBA code + SQL queries)
+ the BD event entry (event_content, notes),
ask LLM to fill in the detail spec steps for sheet_3_detail_specs.
"""
from __future__ import annotations

import json
from typing import Any
import config

# ── System Prompt ──────────────────────────────────────────────────────────────
SYSTEM_PROMPT = (
    "You are an expert Detail Design specification writer for Microsoft Access VBA systems. "
    f"Your task is to write detail specifications in {config.TARGET_LANGUAGE} that serve as a bridge for migrating logic to modern platforms like C#. "
    "STRICT RULE: Do NOT use raw VBA commands, properties, or technical jargon in the 'detail' descriptions. "
    "Translate VBA-specific actions into generic logical intents (e.g., instead of 'DoCmd.OpenForm', use 'Open the target screen'). "
    "STRICT RULE: All steps MUST follow a multi-level hierarchical numbering format (1.1, 1.1.1, 2.1, 2.1.1, etc.) for clarity. "
    "Follow the dd_form.json schema strictly. Output ONLY a compact JSON object (no pretty-printing/indentation) to save tokens."
)

def build_dd_prompt(
    logic_item: dict[str, Any],
    bd_event: dict[str, Any],
    dd_schema_template: str,
    category: str = "screen",
    retry_context: dict | None = None,
) -> str:
    """
    Build user prompt for D3: LLM generates detail steps for one module.
    category: 'screen', 'macro', 'common' (module)
    """
    if category == "screen":
        return _build_screen_prompt(logic_item, bd_event, retry_context)
    elif category == "macro":
        return _build_macro_prompt(logic_item, retry_context)
    else:
        return _build_module_prompt(logic_item, retry_context)

def _build_screen_prompt(logic_item: dict[str, Any], bd_event: dict[str, Any], retry_context: dict | None) -> str:
    module_id = logic_item.get("module_id", "")
    title = logic_item.get("title", "") or logic_item.get("module_name", "") or module_id
    code = logic_item.get("code", "")
    queries = logic_item.get("queries", []) or []

    if len(code) > 3000:
        code = code[:3000] + "\n...(VBA code truncated)"

    # Build RELATED SQL: merge queries + vba_queries (deduplicated by name)
    seen_q_names: set[str] = set()
    query_lines: list[str] = []
    all_q_sources = list(queries) + list(logic_item.get("vba_queries", []))
    for q in all_q_sources:
        q_name = q.get("name") or q.get("query_name", "")
        if not q_name or q_name in seen_q_names:
            continue
        seen_q_names.add(q_name)
        sql_raw = q.get("sql_logic") or q.get("raw_sql") or q.get("sql", "")
        if len(str(sql_raw)) > 600:
            sql_raw = str(sql_raw)[:600] + "...(SQL truncated)"
        query_lines.append(f"[{q_name}]\n{sql_raw}" if sql_raw else f"[{q_name}]")
    query_block = "\n\n".join(query_lines) if query_lines else "なし"


    # Prefer event info embedded in logic_item (new BD-event-driven flow), fallback to bd_event
    event_content = logic_item.get("event_content", "") or bd_event.get("event_content", "")
    event_trigger = logic_item.get("event_trigger", "") or bd_event.get("event_trigger", "")
    action_type   = logic_item.get("action_type", "")   or bd_event.get("action_type", "")
    bd_notes      = bd_event.get("notes", "")

    retry_block = _build_retry_block(retry_context)

    # Build REFERENCES section (called modules, macros, tables, commands)
    references = logic_item.get("references", {})
    ref_lines: list[str] = []
    for ref_type, ref_list in references.items():
        if ref_list:
            if isinstance(ref_list, list):
                ref_lines.append(f"- {ref_type}: {', '.join(str(r) for r in ref_list)}")
            else:
                ref_lines.append(f"- {ref_type}: {ref_list}")
    references_block = "\n".join(ref_lines) if ref_lines else ""

    # Initialization hint
    hint = logic_item.get("_hint", "")

    # No-VBA path: use controls/screen_edit context instead
    form_controls     = logic_item.get("form_controls", [])
    screen_edit_items = logic_item.get("screen_edit_items", [])
    record_sources    = logic_item.get("record_sources", [])
    is_virtual = not code or not code.strip() or code.strip().startswith("' Virtual module")
    if is_virtual and (form_controls or screen_edit_items):
        # Merge form_controls + screen_edit_items into one list for the prompt
        merged_controls = form_controls or screen_edit_items
        query_block2 = "\n\n".join(query_lines) if query_lines else "なし"
        if record_sources:
            rs_names = ", ".join(r.get("query_name", "") for r in record_sources if r.get("query_name"))
            query_block2 = f"[RecordSource]\n{rs_names}\n\n" + query_block2
        return _build_screen_controls_prompt(
            module_id=module_id,
            title=title,
            form_controls=merged_controls,
            query_block=query_block2,
            event_content=event_content,
            bd_notes=bd_notes,
            retry_block=retry_block,
        )

    instruction_base = f"""
### TASK
詳細仕様書 (Detail Design Spec) を作成してください。
出力は以下のJSON形式を厳守してください。

{{
  "module_id": "{module_id}",
  "steps": [
    {{"step": "1. 初期処理", "detail": "技術的な詳細説明、または処理がない場合は「なし」"}},
    {{"step": "2. 主処理",   "detail": "技術的な詳細説明（主処理は必須）"}},
    {{"step": "3. 終了処理", "detail": "技術的な詳細説明、または処理がない場合は「なし」"}}
  ],
  "event_detail": "このイベントの動作内容の要約（{config.TARGET_LANGUAGE}）"
}}

### 【最重要】階層番号付けルール
- "detail" フィールド内では、必ず階層番号（2.1. 2.2. 2.3. など）を使用してください
- 各動作は独立した番号を持つ必要があります（一つの番号に複数の動作を詰め込まない）
- 長い段落形式の記述は禁止です

### 正しい例（GOOD）:
"detail": "2.1. フォームのラベル400のキャプションから、バージョン情報の一部（'/'以降の5文字）を抽出する\\n2.2. クエリAccess配信日を実行して、最新バージョン情報を取得する\\n[F001_SelQuery01]\\n2.3. 取得したバージョン情報と抽出した文字列を比較する\\n2.4. 比較結果に基づいて、メッセージを表示する"

### 誤った例（BAD - 長い段落）:
"detail": "フォームのラベル400のキャプションから、バージョン情報の一部（'/'以降の5文字）を抽出する\\n\\n次に、クエリAccess配信日を実行して、最新バージョン情報を取得し、取得したバージョン情報と抽出した文字列を比較して、比較結果に基づいてメッセージを表示する"

ルール:
- 全ての "detail" は{config.TARGET_LANGUAGE}で記述してください。
- "steps" は必ず「1. 初期処理」「2. 主処理」「3. 終了処理」の3段階で構成してください。
- 処理内容を記述する際は、内容の有無に関わらず、必ず親ステップの番号（「1. 初期処理」「2. 主処理」「3. 終了処理」）に紐づく多段階の階層番号（例：「1.1. 」「2.1. 」「2.1.1. 」「2.1.1.1. 」など、最大4階層まで）を使用して構造化してください。
- 【最重要ルール】一つの番号（例：「2.1. 」）に複数の異なる動作を詰め込まないでください。動作ごとに「2.1. 」「2.2. 」「2.3. 」と番号を分けて記述してください。箇条書きの「・」や番号のない単なる文章のみの記述、単純な「1.」は一切禁止です。
- 画面起動時（F000等）の処理であっても、例外なくこの番号体系（1.1. 1.2. 等）を適用してください。
- 論理構造（条件分岐のIF/ELSE等）を表現する際は、必ず各処理項目（例：「2.1.1. 」など）の直前に改行（\n）を挿入して区切ってください。ただし、字下げ用の余分な空白スペース（インデント）は一切出力しないでください（トークン削減およびExcelへの貼り付けやすさのため）。

- 処理内容を記述する際は、関連するオブジェクト名（Forms、Macros、Tables等の名称）を省略せずに文章中に必ず明記してください。（例：単に「スプラッシュ画面を表示する」ではなく、「マクロ『M300_Splash(M)を開く』を実行してスプラッシュ画面を表示する」と記述すること）。
- 将来の C# への移行を念頭に、論理構造（条件分岐、ループ、エラーハンドリング）やデータの流れを明確に記述してください。
- 【重要】VBA特有の語彙（DoCmd, MsgBox, Application.Version, acQuitSaveAll 等）は使用禁止です。
  - NG: 「DoCmd.Quit acQuitSaveAll を実行する」
  - OK: 「すべての変更を保存し、現在のアプリケーションを正常終了させる」
- 【重要】VBAコード内のコメント行（' で始まる行）や、技術的な補足（URL等）は無視し、ロジックの説明に含めないでください。
- 他のモジュール、マクロ、またはフォームを呼び出す際は、必ず文章の末尾に ` [refer: 名称]` の形式を付与してください（例：「マクロ『M300_Splash』を実行してスプラッシュ画面を表示する [refer: M300_Splash]」）。【最重要：参照形式 of統一】
- [refer: xxx] タグはコード内に明示的に「Call xxx」「RunMacro "xxx"」「OpenForm "xxx"」として他プロシージャを呼び出している場合にのみ記述してください。
  コード内に存在しない参照を自分で造語・推測して追加することは禁止です。
- クエリの呼び出し（DoCmd.OpenQueryやDLookup等によるデータ取得・更新）を記述する際は、必ず `\n[SheetName]\n` の形式を文中に含めてください（例：「最新バージョンを確認するため、クエリを実行する\n[F000_SelQuery01]\n」）。【最重要ルール】元のクエリ名（Q000...等）は絶対に文章中に含めないでください。必ず [SheetName] 形式に完全に置き換えてください。
- 画面起動時（F000等）のRecordSourceや初期データ取得、および初期表示に必要なクエリ実行は、必ず「1. 初期処理」のステップ内に、対応するクエリID（[F000_SelQuery01]等）を明記して記述してください。
- 出力するJSON全体は改行や字下げのない「1行のコンパクトなJSON形式」を厳守してください。ただし、各処理項目（例：「2.1. 」「2.1.1. 」など）を区切るために、"detail" 文字列の内部には改行文字（\n）を必ず含めてください。

- JSONオブジェクトのみを出力してください（Markdown不可）。
�、例外なくこの番号体系（1.1. 1.2. 等）を適用してください。
- 論理構造（条件分岐のIF/ELSE等）を表現する際は、必ず各処理項目（例：「2.1.1. 」など）の直前に改行（\\n）を挿入して区切ってください。ただし、字下げ用の余分な空白スペース（インデント）は一切出力しないでください（トークン削減およびExcelへの貼り付けやすさのため）。


- 処理内容を記述する際は、関連するオブジェクト名（Forms、Macros、Tables等の名称）を省略せずに文章中に必ず明記してください。（例：単に「スプラッシュ画面を表示する」ではなく、「マクロ『M300_Splash(M)を開く』を実行してスプラッシュ画面を表示する」と記述すること）。
- 将来の C# への移行を念頭に、論理構造（条件分岐、ループ、エラーハンドリング）やデータの流れを明確に記述してください。
- 【重要】VBA特有の語彙（DoCmd, MsgBox, Application.Version, acQuitSaveAll 等）は使用禁止です。
  - NG: 「DoCmd.Quit acQuitSaveAll を実行する」
  - OK: 「すべての変更を保存し、現在のアプリケーションを正常終了させる」
- 【重要】VBAコード内のコメント行（' で始まる行）や、技術的な補足（URL等）は無視し、ロジックの説明に含めないでください。
- 他のモジュール、マクロ、またはフォームを呼び出す際は、必ず文章の末尾に ` [refer: 名称]` の形式を付与してください（例：「マクロ『M300_Splash』を実行してスプラッシュ画面を表示する [refer: M300_Splash]」）。【最重要：参照形式の統一】
- [refer: xxx] タグはコード内に明示的に「Call xxx」「RunMacro "xxx"」「OpenForm "xxx"」として他プロシージャを呼び出している場合にのみ記述してください。
  コード内に存在しない参照を自分で造語・推測して追加することは禁止です。
- クエリの呼び出し（DoCmd.OpenQueryやDLookup等によるデータ取得・更新）を記述する際は、必ず `\\n[SheetName]\\n` の形式を文中に含めてください（例：「最新バージョンを確認するため、クエリを実行する\\n[F000_SelQuery01]\\n」）。【最重要ルール】元のクエリ名（Q000...等）は絶対に文章中に含めないでください。必ず [SheetName] 形式に完全に置き換えてください。
- 画面起動時（F000等）のRecordSourceや初期データ取得、および初期表示に必要なクエリ実行は、必ず「1. 初期処理」のステップ内に、対応するクエリID（[F000_SelQuery01]等）を明記して記述してください。
- 出力するJSON全体は改行や字下げのない「1行のコンパクトなJSON形式」を厳守してください。ただし、各処理項目（例：「2.1. 」「2.1.1. 」など）を区切るために、"detail" 文字列の内部には改行文字（\\n）を必ず含めてください。

- JSONオブジェクトのみを出力してください（Markdown不可）。
"""

    # Build output_data_area block (sub-reports / file spec items) for reports
    output_data_area = logic_item.get("output_data_area", [])
    if output_data_area:
        oda_lines = []
        for item in output_data_area:
            no = item.get("no", "")
            name = item.get("output_field_name", "")
            src  = item.get("source_table", "")
            note = item.get("notes", "")
            parts = [f"No.{no}" if no else "", name, f"[{src}]" if src else "", note]
            oda_lines.append("  " + " ".join(p for p in parts if p))
        output_data_block = "\n".join(oda_lines)
    else:
        output_data_block = ""

    output_section = f"\n### OUTPUT FIELDS / SUB-REPORTS\n{output_data_block}\n" if output_data_block else ""

    query_mapping_section = ""
    query_mapping_rule = ""
    query_mappings = logic_item.get("query_mappings", [])
    if query_mappings:
        q_hints = []
        for q in query_mappings:
            name = q.get('logic_query_name') or q.get('query_name', 'Unknown')
            sheet = q.get('sheet_name') or q.get('mapping', 'Unknown')
            if sheet.startswith('[') and sheet.endswith(']'):
                q_hints.append(f"- {name} -> {sheet}")
            else:
                q_hints.append(f"- {name} -> [{sheet}]")
        query_mapping_section = "\n### QUERY TO SHEET MAPPING\n" + "\n".join(q_hints) + "\n"
        query_mapping_rule = "- 【最重要ルール】クエリ実行を記述する際は、上記のマッピングに従い、元のクエリ名（Q_...等）を絶対に文章中に含めず、完全に「\\\\n[シート名]\\\\n」の形式に置き換えて記述してください（例：データを取得する\\\\n[F000_SelQuery01]\\\\n）。元のクエリ名を残したまま付記するのは禁止です。\n"

    references_section = f"\n### CALLED MODULES / COMMANDS\n{references_block}\n" if references_block else ""
    hint_section = f"\n⚠️ HINT: {hint}\n" if hint else ""

    return f"""あなたは画面・帳票のイベントロジック設計者です。
フォーム/レポート上のイベント(VBA)の動作を、詳細設計レベルで記述してください。

### SCREEN INFO
- Screen Name: {title}
- Event Module: {module_id}
- Trigger: {event_trigger}
- Action Type: {action_type}

### BD CONTEXT (基本設計)
{event_content}
Notes: {bd_notes}

### VBA CODE / LOGIC
```vba
{code}
```

### RELATED SQL (クエリ定義)
{query_block}
{query_mapping_section}{references_section}{output_section}{hint_section}
{retry_block}
{instruction_base}{query_mapping_rule}
"""

def _build_macro_prompt(logic_item: dict[str, Any], retry_context: dict | None) -> str:
    module_id = logic_item.get("module_id", "")
    raw_xml = logic_item.get("raw_xml", "")
    references = logic_item.get("references", {})
    
    if len(raw_xml) > 6000:
        raw_xml = raw_xml[:6000] + "\n...(XML truncated)"

    retry_block = _build_retry_block(retry_context)

    instruction_macro = f"""
### TASK
詳細仕様書 (Detail Design Spec) を作成してください。
出力は以下のJSON形式を厳守してください。

{{
  "module_id": "{module_id}",
  "steps": [
    {{"step": "1. 初期処理", "detail": "技術的な詳細説明、または処理がない場合は「なし」"}},
    {{"step": "2. 主処理",   "detail": "技術的な詳細説明（主処理は必須）"}},
    {{"step": "3. 終了処理", "detail": "技術的な詳細説明、または処理がない場合は「なし」"}}
  ],
  "event_detail": "このマクロの動作内容の要約（{config.TARGET_LANGUAGE}）"
}}

### 【最重要】階層番号付けルール
- "detail" フィールド内では、必ず階層番号（2.1. 2.2. 2.3. など）を使用してください
- 各動作は独立した番号を持つ必要があります（一つの番号に複数の動作を詰め込まない）
- 長い段落形式の記述は禁止です

### 正しい例（GOOD）:
"detail": "2.1. 画面更新を停止する\\n2.2. 警告メッセージを無効化する\\n2.3. クエリを実行してデータを更新する\\n[M001_UpdQuery01]\\n2.4. 対象フォームを開く [refer: F_Target]\\n2.5. 画面更新を再開する"

### 誤った例（BAD - 長い段落）:
"detail": "画面更新を停止し、警告メッセージを無効化する\\n\\n次に、クエリを実行してデータを更新し、対象フォームを開いて、画面更新を再開する"

ルール:
- 全ての "detail" は{config.TARGET_LANGUAGE}で記述してください。
- "steps" は必ず「初期処理」「主処理」「終了処理」の3段階で構成し、以下のように役割を明確に分類してください。
  - 「1. 初期処理」: 画面更新の停止、警告メッセージ（SetWarnings）の無効化、エラーハンドリングの初期化（OnError）など、主処理の実行前に必要な環境設定や初期化動作.
  - 「2. 主処理」: 条件分岐（If/Else）、データ更新、クエリ（SQL）の実行、メッセージボックスの表示、画面遷移など、業務要件として核となるロジックおよび主要アクション処理。
  - 「3. 終了処理」: 警告メッセージ（SetWarnings）の再有効化、画面更新の再開、オブジェクトの破棄など、処理の終了に伴う後始末動作。

- 該当する明確な処理がない場合（例：初期化処理や終了処理がコード内に存在しない場合）、"detail" には「なし」と記述してください。不要な説明を創作・記述しないでください。
- 【最重要ルール】処理内容を記述する際は、親ステップの番号（「1. 初期処理」「2. 主処理」「3. 終了処理」）に合わせて、多段階の階層番号（例：「1.1. 」「2.1. 」「2.1.1. 」「2.1.1.1. 」など、最大4階層まで）を使用して構造化してください。一つの番号に複数の異なる動作を詰め込まないでください。動作ごとに「2.1. 」「2.2. 」「2.3. 」と番号を分けて記述してください。箇条書きの「・」や単純な「1.」は使用禁止です。
- 論理構造（条件分岐のIF/ELSE等）を表現する際は、必ず各処理項目（例：「2.1.1. 」など）の直前に改行（\\n）を挿入して区切ってください。ただし、字下げ用の余分な空白スペース（インデント）は一切出力しないでください（トークン削減およびExcelへの貼り付けやすさのため）。


- 処理内容を記述する際は、関連するオブジェクト名（Forms、Macros、Tables等の名称）を省略せずに文章中に必ず明記してください。（例：単に「スプラッシュ画面を表示する」ではなく、「マクロ『M300_Splash(M)を開く』を実行してスプラッシュ画面を表示する」と記述すること）。
- 他のモジュール、マクロ、またはフォームを呼び出す際は、必ず文章の末尾に ` [refer: 名称]` の形式を付与してください（例：「マクロ『M300_Splash』を実行してスプラッシュ画面を表示する [refer: M300_Splash]」）。【最重要：参照形式の統一】
- 将来の C# への移行を念頭に、論理構造（条件分岐、ループ、エラーハンドリング）やデータの流れを明確に記述してください。
- 【重要】VBA特有の語彙（DoCmd, MsgBox, Application.Version, acQuitSaveAll 等）は使用禁止です。
  - NG: 「DoCmd.Quit acQuitSaveAll を実行する」
  - OK: 「すべての変更を保存し、現在のアプリケーションを正常終了させる」
- 出力するJSON全体は改行や字下げのない「1行のコンパクトなJSON形式」を厳守してください。ただし、各処理項目（例：「2.1. 」「2.1.1. 」など）を区切るために、"detail" 文字列の内部には改行文字（\\n）を必ず含めてください。

- JSONオブジェクトのみを出力してください（Markdown不可）。
"""

    query_mapping_section = ""
    query_mapping_rule = ""
    query_mappings = logic_item.get("query_mappings", [])
    if query_mappings:
        q_hints = []
        for q in query_mappings:
            name = q.get('logic_query_name') or q.get('query_name', 'Unknown')
            sheet = q.get('sheet_name') or q.get('mapping', 'Unknown')
            if sheet.startswith('[') and sheet.endswith(']'):
                q_hints.append(f"- {name} -> {sheet}")
            else:
                q_hints.append(f"- {name} -> [{sheet}]")
        query_mapping_section = "\n### QUERY TO SHEET MAPPING\n" + "\n".join(q_hints) + "\n"
        query_mapping_rule = "- 【最重要ルール】クエリ実行を記述する際は、上記のマッピングに従い、元のクエリ名（Q_...等）を絶対に文章中に含めず、完全に「\\\\n[シート名]\\\\n」の形式に置き換えて記述してください（例：データを取得する\\\\n[F000_SelQuery01]\\\\n）。元のクエリ名を残したまま付記するのは禁止です。\n"

    return f"""あなたはMacro（マクロ）設計者です。
Access Macroの元のXML定義を解析し、その動作を詳細設計レベルで記述してください。
このマクロは独立したロジックとして動作します。

### MACRO INFO
- Macro Name: {module_id}

### RELATED REFERENCES (Forms, Macros, Tables used)
```json
{json.dumps(references, ensure_ascii=False, indent=2)}
```

### MACRO DEFINITION (XML AST)
```xml
{raw_xml}
```

{query_mapping_section}
{retry_block}
{instruction_macro}{query_mapping_rule}
マクロのアクションを単に羅列するのではなく、「どの画面を開くか」「何のデータを抽出するか」など、業務フローとしての動きを正確に記述してください。
"""

def _build_module_prompt(logic_item: dict[str, Any], retry_context: dict | None) -> str:
    module_id = logic_item.get("module_id", "")
    code = logic_item.get("code", "")
    queries = logic_item.get("queries", []) or []

    if len(code) > 3000:
        code = code[:3000] + "\n...(VBA code truncated)"

    query_lines: list[str] = []
    for q in queries:
        q_name = q.get("query_name", "")
        sql_raw = q.get("sql", "")
        if len(str(sql_raw)) > 600:
            sql_raw = str(sql_raw)[:600] + "...(SQL truncated)"
        query_lines.append(f"[{q_name}]\n{sql_raw}")
    query_block = "\n\n".join(query_lines) if query_lines else "なし"

    retry_block = _build_retry_block(retry_context)

    instruction_base = f"""
### TASK
詳細仕様書 (Detail Design Spec) を作成してください。
出力は以下のJSON形式を厳守してください。

{{
  "module_id": "{module_id}",
  "input_data_area": [
    {{"no": "1", "name": "変数名/項目名", "symbol": "シンボル", "io": "I", "type": "型", "description": "用途・役割の説明"}}
  ],
  "steps": [
    {{"step": "1. 初期処理", "detail": "技術的な詳細説明、または処理がない場合は「なし」"}},
    {{"step": "2. 主処理",   "detail": "技術的な詳細説明（主処理は必須）"}},
    {{"step": "3. 終了処理", "detail": "技術的な詳細説明、または処理がない場合は「なし」"}}
  ],
  "output_data_area": [
    {{"output_name": "出力内容", "result_check": "✓"}}
  ]
}}

### 【最重要】階層番号付けルール
- "detail" フィールド内では、必ず階層番号（2.1. 2.2. 2.3. など）を使用してください
- 各動作は独立した番号を持つ必要があります（一つの番号に複数の動作を詰め込まない）
- 長い段落形式の記述は禁止です

### 正しい例（GOOD）:
"detail": "2.1. 入力パラメータの妥当性を検証する\\n2.2. データベースから対象レコードを取得する\\n[M001_SelQuery01]\\n2.3. 取得したデータを加工する\\n2.4. 計算結果を返す"

### 誤った例（BAD - 長い段落）:
"detail": "入力パラメータの妥当性を検証する\\n\\n次に、データベースから対象レコードを取得し、取得したデータを加工して、計算結果を返す"

ルール:
- 全ての "detail" は{config.TARGET_LANGUAGE}で記述してください。
- "steps" は必ず「初期処理」「主処理」「終了処理」の3段階で構成し、以下のように役割を明確に分類してください。
  - 「1. 初期処理」: 画面更新の停止、警告メッセージ（SetWarnings）の無効化、エラーハンドリングの初期化（OnError）など、主処理の実行前に必要な環境設定や初期化動作。
  - 「2. 主処理」: 条件分岐（If/Else）、データ更新、クエリ（SQL）の実行、メッセージボックスの表示、画面遷移など、業務要件として核となるロジックおよび主要アクション処理。
  - 「3. 終了処理」: 警告メッセージ（SetWarnings）の再有効化、画面更新の再開、オブジェクトの破棄など、処理の終了に伴う後始末動作。

- 【最重要ルール】処理内容を記述する際は、親ステップの番号（「1. 初期処理」「2. 主処理」「3. 終了処理」）に合わせて、多段階の階層番号（例：「1.1. 」「2.1. 」「2.1.1. 」「2.1.1.1. 」など、最大4階層まで）を使用して構造化してください。一つの番号に複数の異なる動作を詰め込まないでください。動作ごとに「2.1. 」「2.2. 」「2.3. 」と番号を分けて記述してください。箇条書きの「・」や単純な「1.」は使用禁止です。
- 論理構造（条件分岐のIF/ELSE等）を表現する際は、必ず各処理項目（例：「2.1.1. 」など）の直前に改行（\\n）を挿入して区切ってください。ただし、字下げ用の余分な空白スペース（インデント）は一切出力しないでください（トークン削減およびExcelへの貼り付けやすさのため）。


- 処理内容を記述する際は、関連するオブジェクト名（Forms、Macros、Tables等の名称）を省略せずに文章中に必ず明記してください。（例：単に「スプラッシュ画面を表示する」ではなく、「マクロ『M300_Splash(M)を開く』を実行してスプラッシュ画面を表示する」と記述すること）。
- 他のモジュール、マクロ、またはフォームを呼び出す際は、必ず文章の末尾に ` [refer: 名称]` の形式を付与してください（例：「マクロ『M300_Splash』を実行してスプラッシュ画面を表示する [refer: M300_Splash]」）。【最重要：参照形式の統一】
- 将来の C# への移行を念頭に、論理構造（条件分岐、ループ、エラーハンドリング）やデータの流れを明確に記述してください。

- 【重要】VBA特有の語彙（DoCmd, MsgBox, Application.Version, acQuitSaveAll 等）は使用禁止です。
  - NG: 「DoCmd.Quit acQuitSaveAll を実行する」
  - OK: 「すべての変更を保存し、現在のアプリケーションを正常終了させる」
- [refer: xxx] タグはコード内に明示的に「Call xxx」「RunMacro "xxx"」「OpenForm "xxx"」として他プロシージャを呼び出している場合にのみ記述してください。
  コード内に存在しない参照を自分で造語・推測して追加することは禁止です。
- 出力するJSON全体は改行や字下げのない「1行のコンパクトなJSON形式」を厳守してください。ただし、各処理項目（例：「2.1. 」「2.1.1. 」など）を区切るために、"detail" 文字列の内部には改行文字（\\n）を必ず含めてください。

- JSONオブジェクトのみを出力してください（Markdown不可）。
"""

    query_mapping_section = ""
    query_mapping_rule = ""
    query_mappings = logic_item.get("query_mappings", [])
    if query_mappings:
        q_hints = []
        for q in query_mappings:
            name = q.get('logic_query_name') or q.get('query_name', 'Unknown')
            sheet = q.get('sheet_name') or q.get('mapping', 'Unknown')
            if sheet.startswith('[') and sheet.endswith(']'):
                q_hints.append(f"- {name} -> {sheet}")
            else:
                q_hints.append(f"- {name} -> [{sheet}]")
        query_mapping_section = "\n### QUERY TO SHEET MAPPING\n" + "\n".join(q_hints) + "\n"
        query_mapping_rule = "- 【最重要ルール】クエリ実行を記述する際は、上記のマッピングに従い、元のクエリ名（Q_...等）を絶対に文章中に含めず、完全に「\\\\n[シート名]\\\\n」の形式に置き換えて記述してください（例：データを取得する\\\\n[F000_SelQuery01]\\\\n）。元のクエリ名を残したまま付記するのは禁止です。\n"

    return f"""あなたはVBAモジュール（共通関数/共通ロジック）設計者です。
再利用可能な関数やサブプロシージャの技術仕様を、詳細設計レベルで記述してください。

### MODULE INFO
- Module Name: {module_id}

### VBA SOURCE CODE
```vba
{code}
```

### RELATED SQL
{query_block}
{query_mapping_section}
{retry_block}
{instruction_base}{query_mapping_rule}
引数や戻り値の意味を「業務データ」の観点から説明し、ソースコードが実現している「アルゴリズムやロジックの意図」を、他言語（C#等）での再実装が容易になるように構造化して詳細に記述してください。
"""

def _build_retry_block(retry_context: dict | None) -> str:
    if not retry_context:
        return ""
    errors = retry_context.get("previous_errors", [])
    attempt = retry_context.get("attempt", 2)
    return (
        f"\n⚠️ REVISION (Attempt {attempt}):\n"
        + "\n".join(f"  - {e}" for e in errors)
        + "\nCorrect these issues.\n"
    )


def _build_screen_controls_prompt(
    module_id: str,
    title: str,
    form_controls: list,
    query_block: str,
    event_content: str,
    bd_notes: str,
    retry_block: str,
) -> str:
    """Prompt for form/report screens that have NO VBA code but have field/control definitions."""
    ctrl_lines: list[str] = []
    for ctrl in form_controls:
        c_name = ctrl.get("name", "")
        c_type = ctrl.get("type", "")
        c_src  = (ctrl.get("properties") or {}).get("data", {}).get("controlsource", "")
        if c_name:
            ctrl_lines.append(f"- [{c_name}] ({c_type})" + (f": {c_src}" if c_src else ""))
    controls_block = "\n".join(ctrl_lines) if ctrl_lines else "なし"

    instruction = f"""
### TASK
このフォーム/帳票の詳細仕様書 (Detail Design Spec) を作成してください。
このフォームはVBAを持たず、フォームのコントロール定義（フィールドバインディング・計算式）のみで動作します。
出力は以下のJSON形式を厳守してください。

{{
  "module_id": "{module_id}",
  "steps": [
    {{"step": "1. 初期処理", "detail": "技術的な詳細説明、または処理がない場合は「なし」"}},
    {{"step": "2. 主処理",   "detail": "技術的な詳細説明（主処理は必須）"}},
    {{"step": "3. 終了処理", "detail": "技術的な詳細説明、または処理がない場合は「なし」"}}
  ],
  "event_detail": "このフォームの動作内容の要約（{config.TARGET_LANGUAGE}）"
}}

### 【最重要】階層番号付けルール
- "detail" フィールド内では、必ず階層番号（2.1. 2.2. 2.3. など）を使用してください
- 各動作は独立した番号を持つ必要があります（一つの番号に複数の動作を詰め込まない）
- 長い段落形式の記述は禁止です

### 正しい例（GOOD）:
"detail": "2.1. レコードソースからデータを読み込む\\n[F000_RecordSource]\\n2.2. テキストボックス[txt_Name]に顧客名をバインドする\\n2.3. 計算フィールド[txt_Total]で合計金額を算出する（単価×数量）\\n2.4. 条件付き書式で警告表示を制御する"

### 誤った例（BAD - 長い段落）:
"detail": "レコードソースからデータを読み込み、テキストボックスに顧客名をバインドする\\n\\n次に、計算フィールドで合計金額を算出し、条件付き書式で警告表示を制御する"

ルール:
- 全ての "detail" は{config.TARGET_LANGUAGE}で記述してください。
- このフォームにはVBAコードがないため、コントロールのプロパティ（バインドフィールド・計算式）に基づいて処理の流れを記述してください。
- "steps" は必ず「初期処理」「主処理」「終了処理」の3段階で構成してください。
  - 「1. 初期処理」: レコードソースのロード、親フォームからのパラメータ取得（参照フィールド）など、画面表示開始時の準備処理。
  - 「2. 主処理」: 各コントロールのデータバインディング、計算フィールドの算出ロジック（IIfやFormat等）、表示内容の業務的意味の説明。
  - 「3. 終了処理」: 通常は「なし」（VBAなしのため後始末処理は発生しない）。
- 【最重要ルール】処理内容を記述する際は、親ステップに合わせて多段階の階層番号（例：「1.1. 」「2.1. 」「2.1.1. 」「2.1.1.1. 」など, 最大4階層まで）を使用して構造化してください。一つの番号に複数の異なる動作を詰め込まないでください。動作ごとに「2.1. 」「2.2. 」「2.3. 」と番号を分けて記述してください。
- 論理構造（IIf等の条件式）を表現する際は、各処理項目の直前に改行（\\n）を挿入してください。
- コントロール名やフィールド名、参照フォーム名を省略せずに文章中に明記してください。
- 将来のC#移行を念頭に、データの流れと算出ロジックを明確に記述してください。
- 出力するJSON全体は改行や字下げのない「1行のコンパクトなJSON形式」を厳守してください（"detail" 内部の改行文字は許可）。
- JSONオブジェクトのみを出力してください（Markdown不可）。
"""

    return f"""あなたは画面・帳票の詳細設計者です。
VBAを持たないフォーム/帳票について、コントロール定義と参照データに基づいて詳細設計仕様を記述してください。

### SCREEN INFO
- Screen Name: {title}
- Module: {module_id}

### BD CONTEXT (基本設計)
{event_content}
Notes: {bd_notes}

### FORM CONTROLS (コントロール定義)
{controls_block}

### RELATED SQL / RECORD SOURCE
{query_block}

{retry_block}
{instruction}
"""


import re

def clean_step_detail(detail: str) -> str:
    """
    Clean up detail string to 'なし' if it represents a no-op placeholder.
    """
    if not detail or not isinstance(detail, str):
        return "なし"
    
    val = detail.strip()
    if val in ["なし", "特になし", "特に処理はありません。"]:
        return "なし"
        
    # Remove numbering prefix if exists (e.g., "1.1. ", "3.1. ")
    cleaned_val = re.sub(r'^\d+(\.\d+)*\.?\s*', '', val).strip()
    
    # Remove leading/trailing quotes or punctuation
    cleaned_val = cleaned_val.strip('"\'「」.。. ')
    
    if cleaned_val in ["なし", "特になし", "特に処理はありません", "特に対象となる処理はありません", "該当なし"]:
        return "なし"

    # Phrases/patterns indicating no-op
    no_op_phrases = [
        "初期化処理は不要",
        "初期処理は不要",
        "初期処理は実行されません",
        "初期処理は行われません",
        "終了処理は不要",
        "終了処理は実行されません",
        "終了処理は行われません",
        "後始末処理は発生しない",
        "後始末処理は行われません",
        "特に終了処理は実行されません",
        "特に終了処理は行われません",
        "特に初期処理は実行されません",
        "特に初期処理は行われません",
        "特に対象となる処理はありません",
        "特に対象となる処理は存在しません",
        "特に処理は行われません",
        "特に処理は実行されません",
        "処理は実行されません",
        "処理は行われません",
        "処理は不要",
        "処理不要",
        "不要です"
    ]
    
    for phrase in no_op_phrases:
        if phrase in cleaned_val:
            return "なし"
            
    # Regular expression checks for patterns like "本イベントは...起動するため、初期処理は不要です"
    if ("本イベントは" in cleaned_val or "このイベントは" in cleaned_val) and ("不要" in cleaned_val or "実行されません" in cleaned_val or "ありません" in cleaned_val or "発生しません" in cleaned_val):
        return "ignore" if "ignore" in detail else "なし"
        
    if not cleaned_val:
        return "なし"

    return val

