# vba_brain Studio — Frontend (Web Console)

Next.js 16 (App Router) web console for the **vba_brain** 5-layer VBA/Access → .NET migration pipeline. It drives the backend gRPC gateway through Next.js API routes and visualizes each layer as an interactive workspace.

## Tech Stack

| Concern | Choice |
|---|---|
| Framework | Next.js 16 (App Router) + React 19 |
| Language | TypeScript |
| Styling | Tailwind CSS v4 + CSS custom-property design tokens (`src/app/globals.css`) |
| Graph canvas | `@xyflow/react` (React Flow) + Cytoscape |
| Icons / Motion | lucide-react · framer-motion |
| Backend bridge | `@grpc/grpc-js` + `@grpc/proto-loader` via API routes |
| Package manager | **yarn** (do not use npm) |

## Getting Started

```bash
yarn install
yarn dev          # http://localhost:3000 (bound to 127.0.0.1)
```

> The gRPC gateway must be running on `:50051`. From the repo root you can start FE + BE together with `python start.py`.

## Scripts

| Command | Description |
|---|---|
| `yarn dev` | Start dev server (port 3000, `127.0.0.1` only) |
| `yarn build` | Production build (includes the TypeScript check) |
| `yarn start` | Serve production build (`127.0.0.1` only) |
| `yarn lint` | Run ESLint |
| `yarn test` | Unit tests in `tests/*.test.ts` (`node --test`; Node ≥ 22.18 runs the TypeScript directly) |

Environment the API routes read: `GRPC_SERVER_ADDRESS` (default `localhost:50051`),
`GRPC_AUTH_TOKEN` (sent as a bearer token when set), `GRPC_TLS_CA` (PEM file to trust) or
`GRPC_TLS=1` (system roots) for a TLS gateway, `PYTHON_BIN` (interpreter for spawned scripts),
`VBA_BRAIN_ROOT` (repo root, when the server is not started from `src/frontend`).
`python start.py` sets `GRPC_SERVER_ADDRESS`, plus `GRPC_AUTH_TOKEN` / `GRPC_TLS_CA` when a token /
TLS is configured. Routes that read MongoDB directly use `config.json` → `mongodb.uri` /
`mongodb.db`; the `MONGO_URI` / `MONGO_DB` that `start.py` also sets only reach the spawned Python
scripts.

## Structure

```
src/
├── app/
│   ├── layout.js          # Root layout + pre-paint theme script (no FOUC)
│   ├── globals.css        # Design tokens, shared workspace classes, utilities
│   ├── page.tsx           # Redirects → /layer1
│   ├── layer1..layer5/    # One workspace page per pipeline layer
│   └── api/               # Route handlers bridging to the gRPC gateway
├── proxy.ts               # Rejects cross-origin browser requests to /api/** (GET too)
├── components/
│   ├── Header.tsx         # Top nav: per-layer accent tabs + theme toggle
│   ├── Footer.tsx         # Status bar with live clock
│   ├── GraphView.tsx      # Cytoscape dependency / Avalonia mapping graph
│   └── nodes/             # React Flow custom nodes (Agent, DdAgent, L5Agent, …)
└── lib/
    ├── logging.ts         # Shared LogEntry / LogLevel / getLogColor / formatLogTime
    ├── paths.ts           # All backend paths (VBA_BRAIN_ROOT override)
    ├── python.ts          # Interpreter for spawned scripts (PYTHON_BIN → python3 → python)
    ├── pathSafety.ts      # isSafeName / isSafeCliValue for request-supplied names
    ├── originCheck.ts     # Same-origin rule used by proxy.ts
    ├── grpcAuth.ts        # Bearer-token client interceptor
    └── sse.ts …           # SSE reader, download names, Layer 5 summaries
tests/                     # node --test unit tests for src/lib and route helpers
```

## Design System

All visuals derive from CSS custom properties defined in `src/app/globals.css` under `:root` (light) and `.dark`. Prefer tokens over hardcoded colors so both themes stay in sync:

- Surfaces: `--bg-dark`, `--bg-panel`, `--bg-code`, `--bg-tab-bar`
- Brand: `--brand-gradient`, `--accent`, `--accent-subtle`, `--accent-ring`
- Status: `--success`, `--danger`, `--warning`, `--info`
- Elevation: `--shadow-sm/md/lg/glow`

Reusable classes: `.ws-card`, `.ws-badge-*`, `.ws-gradient-text`, `.ws-tab`, `.action-btn`, `.task-sidebar`, `.terminal-sidebar`.

Theme is persisted to `localStorage.theme` and applied before first paint by the inline script in `layout.js`.

## Conventions

- **Never hardcode** API keys or hostnames in source — config lives in the repo-root `config.json`.
- **Never build shell commands** from request data — spawn with argument arrays and validate names
  with `isSafeName` first.
- Reuse the shared helpers in `src/lib/logging.ts` for any pipeline log console.
- Keep page logic intact when restyling; visual changes should flow through tokens/shared classes.
