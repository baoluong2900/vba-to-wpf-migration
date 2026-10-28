# Backend — Layer 4 (Excel / Word specification export)

## Purpose
Layer 4 renders the Layer 2 BD/DD JSON into specification workbooks (`.xlsx`) and Word documents
(`.docx`) from Japanese templates, translating the template labels to English when
`TARGET_LANGUAGE=en`. It is exposed over gRPC as **`Layer3Service`** (historical naming swap) and
driven from the console page `/layer4`.

## Modules (`src/backend/workflow/layer4/`)
| Module | Responsibility |
| --- | --- |
| `server.py` | `gen_bd`, `gen_dd`, `gen_all`, `list_items`, `list_outputs`, `download_file` |
| `scripts/fill_bd_excel.py`, `fill_bd_report_excel.py` | BD screen / report workbooks |
| `scripts/fill_dd_excel_{frm,report,macro,module}.py` | Thin DD entry points (template + profile) |
| `scripts/dd_common.py` | Everything the four DD fillers share: SQL sheets, detail sheets, change history, sheet naming/ordering |
| `scripts/excel_translator.py` | JP → EN label translation, sheet renaming with formula-reference rewrite, sheet-name restore |
| `scripts/fill_docx.py` | Word renditions of the same BD/DD content |
| `template/` | Six **Japanese** templates (BD_Screen, BD_Report, DD_Screen ×3, DD_Report) — never re-save them with openpyxl |

## Data
- **Input:** `layer2/output/bd_flow/bd4_bd_final/<name>.json`, `layer2/output/dd_flow/<cat>/dd4_dd_final/<name>.json`,
  else the `bds` / `dds` MongoDB documents. If neither exists the call fails with
  "… not generated yet …" — Layer 4 never renders raw Layer 1 data.
- **Output:** `src/excel_outputs/{BD,DD}/<type>/<name>.xlsx` (+ `.docx`). `download_url` values
  are already percent-encoded.

## Rules that matter
- **Templates are Japanese; locators are bilingual.** Every label/sheet lookup tries the Japanese
  text first, then its English rendering, so an English template cannot silently break filling.
- **Only template labels are translated.** Label cells are recorded before filling and only they
  are translated; values from the BD/DD JSON and formula cells are never touched (substring
  translation used to mangle both). Consequence: Japanese text inside the JSON stays Japanese.
- **No fabricated content.** Mock change history is off by default (`--mock-change-history` opts
  in on the CLI); sample values in templates (project name, author, table names) are cleared.
- **Profiles:** DD screen/report use `detail_profile="form"` (one detail sheet per spec),
  macro/module use `"module_macro"`.
- **Paths from requests are confined:** every path built from `screen_name` must be a direct
  child of its folder (`_child`), downloads stay inside `src/excel_outputs`.
- `server.py` never drives Excel COM (`draw_layout_shapes=False`).

## CLI
Each `fill_*.py` script also runs standalone over `layer4/inputs/{BD_json,DD_json}/…`; see
`--help`. Missing input folders fail with a clear message.

## Tests
`tests/backend/test_layer4_*.py` — translator, DD SQL rendering, cell helpers, server (fillers and
MongoDB faked).
