# Frontend Architecture

## Overview
Next.js 16 (App Router) + React 19 + TypeScript web console in `src/frontend/`: one workspace page
per pipeline layer (`src/app/layer1` … `layer5`) plus graph explorers. Pages call the API routes
under `src/app/api/`; the routes talk to the gRPC gateway, read MongoDB/files, or spawn the
Layer 1 / Layer 5 Python scripts.

## Key constraints & technologies
- **Package manager:** Yarn 1.x. NEVER `npm`.
- **Styling:** Tailwind CSS v4 + CSS custom-property tokens in `src/app/globals.css` (light +
  dark). Never hard-code a color.
- **Dev server:** `yarn dev` binds `127.0.0.1` (`next dev -H 127.0.0.1`).

## Shared server-side modules (`src/lib/`)
| Module | Purpose |
| --- | --- |
| `paths.ts` | Every backend path in one place; `VBA_BRAIN_ROOT` overrides the repo root, otherwise it is found by walking up to `src/backend/protos` |
| `python.ts` | Interpreter for spawned scripts: `PYTHON_BIN`, then `python3`, then `python` |
| `pathSafety.ts` | `isSafeName` / `isSafeCliValue` — names that become path segments or CLI arguments |
| `originCheck.ts` | Same-origin check used by `src/proxy.ts` |
| `grpcAuth.ts` | Client interceptor adding `authorization: Bearer <GRPC_AUTH_TOKEN>` |
| `contentDisposition.ts`, `downloadUrl.ts` | RFC 5987 file names (Japanese file names), encoded download URLs |
| `sse.ts` | Shared Server-Sent-Events reader (buffers partial events, UTF-8 safe) |
| `logicSummary.ts`, `tokenReport.ts` | Layer 5 run summary and token report readers |

`src/app/api/grpcClient.ts` loads `workflow.proto` lazily and caches one client per service. The
proto names are swapped: `layer3Client` = `Layer4Service` (SQL migration, UI layer 3),
`layer4Client` = `Layer3Service` (Excel, UI layer 4).

## Security rules
- `src/proxy.ts` (Next 16's replacement for `middleware.ts`) rejects state-changing requests to
  `/api/**` that are not same-origin (`Sec-Fetch-Site`, else Origin vs Host). Requests with
  neither header come from non-browser clients and are allowed.
- Never build a shell command: spawn with argument arrays (`spawn` / `execFile`). Validate every
  name with `isSafeName` before it reaches a path or a CLI.
- `/api/v1/layer1/extract` is POST-only. `scope: "full"` runs `run_all.py --skip layer3`;
  `scope: "ast"` runs `--skip layer2,layer3`. The PostgreSQL migration is never started from the
  browser.

## Layer pages ↔ routes (main ones)
| Page | Routes |
| --- | --- |
| `/layer1` | `POST /api/v1/layer1/extract` (SSE), `/api/v1/layer1/db-query` |
| `/layer2` | `/api/v1/layer2/{config,models/health,bd-flow-full,dd-flow-full,bd-status/[screenName],download-token-report}`, `/api/items` |
| `/layer3` | `/api/v1/layer3/{queries,queries/[name],convert,convert_and_test,test_query,tables,tables/convert,migration_errors}` — `test_query` is a static check (`staticSqlCheck.ts`), nothing is executed |
| `/layer4` | `/api/v1/layer4/{items,list-outputs,gen-bd,gen-dd,download/...}` |
| `/layer5` | `/api/v1/layer5/{run-agent,run-logic,files,token-stats,download-token-report}`, `/api/graph-wpf/*` |

## Tests
`src/frontend/tests/*.test.ts`, run with `yarn test` (`node --test`, TypeScript via Node's type
stripping — no extra dependency). Keep tested helpers free of Next.js imports so Node can load
them directly.
