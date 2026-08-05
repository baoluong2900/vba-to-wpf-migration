# Contributing to vba_brain

Thanks for working on this. This document is the short, enforceable version of how the repo
expects changes to arrive.

---

## 1. Environment

| Tool | Version | Notes |
| --- | --- | --- |
| Python | **3.10+** | Some modules use PEP 604 `X \| None` without `from __future__ import annotations`; 3.9 will `SyntaxError` |
| Node.js | **≥ 20.9** | Required by Next.js 16 (`engines.node`) |
| Yarn | 1.x | **Never use npm** — the lockfile is `yarn.lock` |
| Docker | latest | MongoDB 7 + PostgreSQL 16 via `infa/docker-compose.yml` |
| .NET SDK | 10 | Only needed for Layer 5 build-verify and the Avalonia app |

```bash
git clone https://github.com/baoluong2900/vba-to-wpf-migration.git
cd vba-to-wpf-migration

pip install -r src/backend/requirements.txt
(cd src/frontend && yarn install)

cp config.example.json config.json      # fill in your keys
cp infa/.env.example infa/.env          # change the default passwords
(cd infa && docker compose up -d)
```

---

## 2. Quality gates

Run all three before opening a pull request. CI (`.github/workflows/ci.yml`) runs the same
commands, so a local pass is the fastest way to a green PR.

```bash
# Backend — every Python file must compile
python -m compileall -q src/backend start.py start_wpf.py clean_generated_files.py

# Frontend — lint must be clean
cd src/frontend && yarn lint

# Frontend — production build must succeed
cd src/frontend && yarn build
```

If you add Python tests, put them under a `tests/` directory and make them runnable with a bare
`pytest` from the repo root. Layer 3's `table_converter.py` is a pure function and the best place
to start; see [`docs/UPGRADE_PLAN.md`](docs/UPGRADE_PLAN.md) §2.1.

---

## 3. Hard rules

These are not style preferences. A PR that breaks one of them will be rejected.

1. **No secrets in tracked files.** `config.json`, `.env`, `infa/.env`, and `appsettings.json`
   are git-ignored. Add new settings to `config.example.json` / `infa/.env.example` with
   placeholder values instead.
2. **No hard-coded API keys, hosts, ports, or model IDs in source.** Everything resolves through
   `src/backend/common/config.py` (`get_setting`: env → `config.json` → default). Adding an LLM
   provider should be a `config.json` change, not a code change.
3. **Never expose an API key to the frontend.** The browser receives the model *list* through
   `Layer2Service.GetConfig`; keys stay server-side.
4. **`yarn`, never `npm`.** Mixing lockfiles breaks reproducible installs.
5. **Do not commit generated artifacts.** `src/excel_outputs/`, `layer2/output/`,
   `layer5/output/`, `data/`, `bin/`, `obj/`, and `.next/` are all ignored on purpose.
6. **Do not commit raw database exports.** `data/` holds customer data and is ignored at the
   top level of `.gitignore` for that reason.
7. **Docker ports stay bound to `127.0.0.1`.** Do not revert `infa/docker-compose.yml` to
   `0.0.0.0`.
8. **Windows-safe Python.** Prefer `python -X utf8` in docs and scripts; do not assume a UTF-8
   console.

---

## 4. Conventions

### Python

- Type-annotate public functions. Add `from __future__ import annotations` to any new module
  using PEP 604 unions so the 3.9 floor stays a documentation matter, not a crash.
- Use the module-level `logger`, not `print`, in library code.
- Layer boundaries are one-directional: read from MongoDB, not from the previous layer's files.
- New MongoDB collection names belong in `layer2/config.py` or `layer5/core/config.py`, not
  inline string literals.

### Frontend

- Style through the CSS custom-property tokens in `src/app/globals.css` (`--bg-panel`,
  `--accent`, `--success`, …). **Never hard-code a color** — both themes must stay in sync.
- Reuse `src/lib/logging.ts` (`LogEntry`, `getLogColor`, `formatLogTime`) for any log console.
- API routes under `src/app/api/` are the only place that talks gRPC; components never do.

### Protobuf

Editing `src/backend/protos/workflow.proto` requires regenerating the stubs in the same commit:

```bash
python -m grpc_tools.protoc \
  -I src/backend/protos \
  --python_out=src/backend/api_gateway \
  --grpc_python_out=src/backend/api_gateway \
  src/backend/protos/workflow.proto
```

Note the historical naming swap: `Layer3Service` = Excel export, `Layer4Service` = SQL
migration. Renaming them is a deliberate breaking change tracked in `docs/UPGRADE_PLAN.md` §3.3
— do not rename them incidentally.

---

## 5. Commits & pull requests

Commit messages follow Conventional Commits with a component scope:

```
<type>(<scope>): <imperative summary>

feat(layer5): add FluentValidation generator to the service agent
fix(layer3): keep raw_sql when re-seeding queries_v2
docs(readme): correct the gRPC service-name swap
refactor(frontend): split layer3/page.tsx into panel components
chore(infra): bind compose ports to 127.0.0.1
```

Types: `feat` · `fix` · `docs` · `refactor` · `perf` · `test` · `chore` · `style`
Scopes: `layer1`…`layer5` · `backend` · `frontend` · `wpf` · `infra` · `docs` · `readme`

A pull request should state:

- **What** changed and **why** (link an issue if one exists).
- Which quality gates you ran and their result.
- Any doc updated alongside the code — a behaviour change with a stale README is incomplete.
- Anything intentionally left out, so a reviewer does not have to guess.

Keep PRs scoped. The repo already has several 70KB+ files; a change that both refactors one of
them and adds a feature is very hard to review.

---

## 6. Where to start

`docs/UPGRADE_PLAN.md` is the live backlog with severity tags. Good first contributions:

| Task | Where | Plan ref |
| --- | --- | --- |
| Pin `requirements.txt` versions (`>=` → `==`) | `src/backend/requirements.txt` | §1.4 |
| Add `pytest.ini` + tests for `table_converter.py` | `layer3/sql_migration/` | §2.1 |
| Add a gRPC auth-token interceptor | `api_gateway/grpc_server.py` | §1.1 |
| Split `agent_ui.py` (124KB) by responsibility | `layer5/agents/ui/` | §3.4 |
| Add `--only-layer` / `--from-layer` to `run_all.py` | `layer1/run_all.py` | §4.3 |
| Delete the empty `vba_brain.UI.WPF/` folder | `src/wpf/` | §3.2 |
