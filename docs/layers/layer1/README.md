# Layer 1 — Access Parser & Aggregator Specification

This folder contains all parser and aggregator scripts used to extract, normalize, enrich, and seed raw MS Access assets (VBA code, SQL queries, Macro XML schemas, UI layouts) from `database_json/` into MongoDB and local reference structures.

---

## 1. Key Ingestion & Parser Scripts

| Script File | Core Responsibility |
|---|---|
| [`frm_parser.py`](file:///Users/baoluong0209/GitTool/vba_mirgation/workflow/backend/layer1/frm_parser.py) | Parses Form and Report structures, extracting UI controls, event mappings, and raw VBA code. |
| [`query_parser.py`](file:///Users/baoluong0209/GitTool/vba_mirgation/workflow/backend/layer1/query_parser.py) | Parses SQL queries (SELECT, UPDATE, INSERT, crosstab) into structured JSON blocks. |
| [`macro_parser.py`](file:///Users/baoluong0209/GitTool/vba_mirgation/workflow/backend/layer1/macro_parser.py) | Parses Macro XML schemas, actions, and conditional validation statements. |
| [`table_parser.py`](file:///Users/baoluong0209/GitTool/vba_mirgation/workflow/backend/layer1/table_parser.py) | Parses database table schemas, data types, lengths, and primary key constraints. |
| [`aggregator.py`](file:///Users/baoluong0209/GitTool/vba_mirgation/workflow/backend/layer1/aggregator.py) | **Orchestrator**: Executes individual parsers, analyzes cross-references, and generates static maps. |
| [`seed_db.py`](file:///Users/baoluong0209/GitTool/vba_mirgation/workflow/backend/layer1/seed_db.py) | Seed utility to load parsed structures from local outputs into MongoDB collections. |

---

## 2. Ingestion Operations Manual

### Step 1: Extract References & Build Maps (Aggregator)
Execute `aggregator.py` to ingest raw JSON dumps under `database_json/` and build a static cross-reference map of UI forms, reports, macros, and tables:

```bash
python3 -X utf8 backend/layer1/aggregator.py
```

- **Output Assets:** Populates enriched JSON maps inside `output/forms_report_json_refs/` (subdivided into `forms_json`, `macro_json`, etc.).
- **Static Map Target:** Automatically constructs the comprehensive cross-reference map file at:
  `output/forms_report_json_refs/reference_map.json`

### Step 2: Seed Ingested Assets into MongoDB
Execute `seed_db.py` to seed normalized JSON assets into MongoDB collections, providing the essential data baseline for Layer 2 and Layer 5 agents:

```bash
python3 backend/layer1/seed_db.py
```

---

## 3. Reference Map Structure (`reference_map.json`)

The cross-reference file `reference_map.json` outlines component dependencies using the following contract:

```json
{
    "forms": {
        "Form_Name": {
            "forms": ["List of referenced forms"],
            "reports": ["List of referenced reports"],
            "queries": ["List of referenced queries"],
            "macros": ["List of executed macros"],
            "modules": ["List of invoked modules"],
            "tables": ["List of utilized tables"]
        }
    },
    "reports": { ... },
    "macros": { ... },
    "modules": { ... },
    "queries": { ... },
    "tables": { ... }
}
```
