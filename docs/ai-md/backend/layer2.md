# Backend - Layer 2 (LLM Engine & Basic/Detail Design)

## Purpose
Layer 2 is the heart of the AI engine. It acts as a FastAPI server that orchestrates the primary design extraction from the legacy code (BD & DD Agents).

## Key Responsibilities
1. **FastAPI HTTP Server:** Runs on port 8000. Provides endpoints for the Frontend (Next.js) to trigger agent workflows and view progress.
2. **BD Agent (Basic Design):**
   - Reads Access/VBA data from MongoDB (provided by Layer 1).
   - Generates structural outputs (`bd_form.json`) detailing layouts, UI properties, and high-level events.
3. **DD Agent (Detail Design):**
   - Takes BD Agent output as its input.
   - Generates functional step-by-step logic (`dd_form.json`), extracting SQL statements, macro steps, and conditional variable logic.
4. **LLM Client Orchestration:** Manages asynchronous calls to the LLM (e.g., Qwen) for intelligent parsing when deterministic logic is insufficient.

## Constraints
- **Data Source:** Layer 2 ONLY reads source data from MongoDB, never from the raw `database_json` files.
- **Output Destination:** All generated JSON specifications must be saved directly into `backend/layer2/output/`.
- **Localization:** Reads `TARGET_LANGUAGE` from `config.json` to generate schema prompts dynamically.
