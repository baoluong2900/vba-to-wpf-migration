# Coding Standards & Global Rules

## 1. System & Execution
- **Python Execution:** Always run Python scripts with `python -X utf8` to mitigate Windows/macOS encoding discrepancies.
- **Package Manager:** ALWAYS use `yarn`. NEVER use `npm`.

## 2. Configuration & Secrets
- **API Keys:** DO NOT hardcode API keys anywhere in the codebase. Always read from `config.json` via the config module.
- **Config Management:** Any configuration changes (e.g. `TARGET_LANGUAGE`) must strictly occur in `config.json`. Do not hardcode configurations inside source files.

## 3. Data & Outputs
- **Output Directories:** Place all generated outputs exclusively in `backend/layer2/output/`. Do not create temporary or final output files in arbitrary directories.
- **JSON Formats:** BD (Basic Design) and DD (Detail Design) outputs must always be properly formatted JSON, strictly conforming to the JSON schemas defined in `backend/layer2/schema/template/`.

## 4. Frontend Styling
- **CSS:** Use Vanilla CSS only. Do not incorporate Tailwind CSS.

## 5. Architectural Communication
- Layer 1 -> Layer 2 communication is done STRICTLY via MongoDB. No direct API calls.
- Frontend -> Backend communication is done STRICTLY via HTTP requests to the FastAPI server on Port 8000.
