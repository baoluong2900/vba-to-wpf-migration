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
yarn dev          # http://localhost:3000
```

> The gRPC gateway must be running on `:50051`. From the repo root you can start FE + BE together with `python start.py`.

## Scripts

| Command | Description |
|---|---|
| `yarn dev` | Start dev server (port 3000) |
| `yarn build` | Production build |
| `yarn start` | Serve production build |
| `yarn lint` | Run ESLint |

## Structure

```
src/
├── app/
│   ├── layout.js          # Root layout + pre-paint theme script (no FOUC)
│   ├── globals.css        # Design tokens, shared workspace classes, utilities
│   ├── page.tsx           # Redirects → /layer1
│   ├── layer1..layer5/    # One workspace page per pipeline layer
│   └── api/               # Route handlers bridging to the gRPC gateway
├── components/
│   ├── Header.tsx         # Top nav: per-layer accent tabs + theme toggle
│   ├── Footer.tsx         # Status bar with live clock
│   ├── GraphView.tsx      # Cytoscape dependency / Avalonia mapping graph
│   └── nodes/             # React Flow custom nodes (Agent, DdAgent, L5Agent, …)
└── lib/
    └── logging.ts         # Shared LogEntry / LogLevel / getLogColor / formatLogTime
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
- Reuse the shared helpers in `src/lib/logging.ts` for any pipeline log console.
- Keep page logic intact when restyling; visual changes should flow through tokens/shared classes.
