# Coding Standards & Global Rules

## 1. System & execution
- **Python:** 3.10+. Run scripts with `python -X utf8` to avoid Windows console encoding issues.
- **Package manager:** ALWAYS `yarn` for the frontend. NEVER `npm`.
- **Dependencies:** backend runtime packages live in `src/backend/requirements.txt` with a floor
  and a next-major ceiling; tooling in `src/backend/requirements-dev.txt`.

## 2. Configuration & secrets
- Never hard-code API keys, hosts, ports or model ids. Resolve settings through
  `src/backend/common/config.py` (`get_setting`: env → `config.json` → default).
- New settings get a placeholder in `config.example.json` and/or `.env.example`.
- Never log a credential: use `common.config.redact_uri` for connection strings.

## 3. Untrusted input
- Item names, file names and doc kinds that arrive in a request become path components:
  reject `/`, `\`, NUL, `.`/`..` and drive prefixes (the gateway's `_bad_name`), and confine
  every resolved path to its base directory.
- Never build a shell command from request data. Spawn processes with an argument list
  (`spawn`/`execFile` in Node, `subprocess.run([...])` in Python).
- Treat LLM output as untrusted: parse defensively and never record a failed parse as success.

## 4. Data & outputs
- Layer 2 writes under `src/backend/workflow/layer2/output/` (git-ignored); Layer 4 under
  `src/excel_outputs/`. Generated artifacts are not committed — the exceptions are the Layer 5
  name maps (`agents/graphview/outputs/*/list*JpToEn.json`), the Mapping agent's C#, and the
  sample outputs under `agents/ui/{inputs,outputs}/` and `agents/logic/{inputs,outputs}/`. Repo and
  service contracts are git-ignored, and the CI hygiene job fails if they are tracked.
- BD/DD JSON follows the templates in `src/backend/workflow/layer2/schema/template/`.

## 5. Frontend styling
- Tailwind CSS v4 plus the CSS custom-property tokens in `src/app/globals.css`. Never hard-code
  a color — both themes must stay in sync.

## 6. Architectural communication
- Layer 1 → Layer 2 → … communicate only through MongoDB and documented files (Layer 4 reads
  Layer 2's output JSON before MongoDB; Layer 5 reads `layer4/inputs/` and its own agents'
  outputs), never by calling each other.
- Frontend → backend: Next.js API routes under `src/frontend/src/app/api/` call the gRPC gateway
  (`:50051`, `src/backend/protos/workflow.proto`). Layer 5 has no gRPC service: its routes start
  the agent scripts with an argument list (`execFile` / `spawn`). Components never talk gRPC
  directly.

## 7. Quality gates
`ruff check` + `pytest` (backend), `yarn lint` + `yarn typecheck` + `yarn test` + `yarn build`
(frontend), `dotnet build src/wpf/vba_brain.slnx` (target app). CI runs all of them.
