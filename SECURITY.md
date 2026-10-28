# Security Policy

## Project status

`vba_brain` is a **working prototype for local and internal use.** It is not hardened for
internet exposure. The items below are known, tracked, and deliberately documented rather than
hidden — read them before you run this anywhere but `localhost`.

---

## Known weaknesses

| ID | Issue | Evidence | Severity |
| --- | --- | --- | --- |
| S1 | TLS and authentication on the gRPC gateway are opt-in. It binds `localhost` by default; with `GRPC_HOST=0.0.0.0` and no `GRPC_AUTH_TOKEN`, anything that reaches the port can drive the pipeline, including LLM spend, and without `GRPC_TLS_CERT` / `GRPC_TLS_KEY` the token travels in clear text | `src/backend/api_gateway/grpc_server.py::serve`, `auth.py` | 🟡 Medium |
| S2 | Mongo Express ships with `admin` / `admin123` from `infa/.env.example` | `infa/.env.example` | 🔴 High if reachable |
| S3 | Default database credentials (`vba_brain` / `vba_brain2024`) are committed as example values | `infa/.env.example` | 🟡 Medium |
| S4 | `postgres_migrator.py` drops and recreates every table it migrates. The DDL is deterministic (no LLM) and `--dry-run` exists, but nothing forces you to use it | `layer3/sql_migration/postgres_migrator.py` | 🟢 Low |
| S5 | Python dependencies are range-pinned (floor + next-major ceiling) but there is no lockfile, so two installs can differ in minor versions | `src/backend/requirements.txt` | 🟢 Low |
| S6 | The web console has no user authentication; it relies on binding `127.0.0.1` and on rejecting cross-site requests | `src/frontend/src/proxy.ts`, `package.json` (`next dev -H 127.0.0.1`) | 🟡 Medium |
| S7 | LLM-generated C# is deployed into `src/wpf` and built; treat it as untrusted code until reviewed | `layer5/pipeline/` | 🟡 Medium |

Remediation for each is tracked in [`docs/UPGRADE_PLAN.md`](docs/UPGRADE_PLAN.md) Phase 1–2.

### Fixed in the 2026-10 review

Details and reproduction notes are in [`docs/REVIEW_REPORT.md`](docs/REVIEW_REPORT.md).

- **Remote code execution** through `/api/v1/layer5/run-agent`: `phase` and `test_agents` from
  the request body were interpolated into a shell command.
- **Arbitrary file write** through gRPC item names (`screen_name="../../config"` overwrote any
  `*.json`; Layer 4 wrote `.xlsx`/`.docx` the same way).
- **Cross-site triggering:** any web page could POST to the console (and a plain `GET` of
  `/api/v1/layer1/extract` ran the whole pipeline, LLM calls and `DROP TABLE` included).
- **Credential exposure:** the Mongo URI with its password was streamed to the browser; the
  generated login service returned every user's plaintext password row to the view model.
- **Network exposure:** the gateway listened on all interfaces with no authentication.
- **Vulnerable dependency:** `System.Security.Cryptography.Pkcs` 9.0.x (high + moderate).
- **Hard-coded root account** in `infa/mongo-init/01_init_user.js`.

---

## What is already in place

- **The gRPC gateway listens on `localhost` only** unless `GRPC_HOST` says otherwise, and with
  `GRPC_AUTH_TOKEN` set every RPC needs `authorization: Bearer <token>` (compared in constant
  time). `start.py` passes the token to the console's API routes. With `GRPC_TLS_CERT` and
  `GRPC_TLS_KEY` set it serves TLS only, and it refuses to start when just one of them is set.
- **Request names are validated** before they become paths: the gateway rejects `/`, `\`, NUL,
  `..` and drive prefixes, Layer 2/4/5 confine every resolved path to its output directory, and
  the console's routes do the same for their own file access.
- **No request data reaches a shell.** The console spawns Python and `dotnet` with argument
  arrays (`spawn`/`execFile`), never `exec` with a command string.
- **Cross-site requests are refused:** state-changing calls to `/api/**` must come from the
  console's own origin, and the dev server binds `127.0.0.1`.
- **Credentials are never logged:** connection strings go through `redact_uri()` first.
- **CI gates:** no secret-bearing file tracked, no vulnerable NuGet package
  (`dotnet list package --vulnerable`), gRPC stubs in sync with the `.proto`.
- **All Docker ports bind to `127.0.0.1`** (`infa/docker-compose.yml`) — MongoDB `27017`,
  Mongo Express `8082`, and PostgreSQL `5432` are not reachable from the network.
- **MongoDB requires authentication** — root credentials are supplied via environment variables
  and clients must pass `authSource=admin`.
- **Secrets are never committed.** `.gitignore` excludes `config.json`, `.env`, `.env.*`,
  `**/.env`, `appsettings.json`, and the entire `data/` tree, while allowing `.env.example` and
  `**/appsettings.example.json` templates through.
- **No API key ever reaches the browser.** The web console receives the *model list* through
  `Layer2Service.GetConfig`; keys are resolved server-side by `src/backend/common/config.py`.
- **Raw database exports stay local.** `data/` (Access exports, MongoDB and PostgreSQL volumes)
  is git-ignored at the top level.
- **Configuration is centralized.** A single resolver (`get_setting`: env → `config.json` →
  default) means there is one place to audit for credential handling.

---

## Hardening checklist before any shared or production deployment

- [ ] **Change every default credential** in `infa/.env` — MongoDB, PostgreSQL, and Mongo Express.
- [ ] **Do not run Mongo Express.** Comment the service out of `infa/docker-compose.yml`.
- [ ] **Set `GRPC_AUTH_TOKEN`** (long random string) before `GRPC_HOST` leaves `localhost`, and
      turn on TLS (`GRPC_TLS_CERT` / `GRPC_TLS_KEY`, or a TLS-terminating proxy) so the token
      never crosses the network in clear text.
- [ ] **Keep container ports on `127.0.0.1`.** If a remote client genuinely needs access, front it
      with a reverse proxy that terminates TLS and authenticates, rather than widening the bind.
- [ ] **Restrict the PostgreSQL migration role.** Layer 3 executes generated DDL; give it rights
      to the target schema only, never superuser.
- [ ] **Review generated SQL before executing it.** Treat LLM output as untrusted input.
- [ ] **Rotate LLM API keys on a schedule** and set a budget cap in the provider console — an
      unauthenticated gateway is also an unauthenticated way to spend money.
- [ ] **Lock dependencies** for production builds (`pip-compile` / `pip freeze` into a lockfile on the target Python version); `requirements.txt` only bounds the ranges.
- [ ] **Scan git history for leaked keys** before making a repository public (last scan
      2026-10-28: clean — no `config.json`/`.env` ever committed, no key patterns):
      ```bash
      git log --all -S "sk-" --oneline
      git log --all -p -- config.json
      ```
      If anything surfaces: rotate the key first, then rewrite history with `git-filter-repo`.

---

## Handling of sensitive data

This pipeline processes real business applications. Assume that parsed output is as sensitive as
the source database:

- **Access exports** in `data/` may contain production schemas, embedded SQL, and business rules.
- **BD/DD documents** and **Excel workbooks** restate that logic in readable prose.
- **LLM calls transmit source code and schema fragments to a third-party provider.** Confirm this
  is acceptable under your data-handling policy before running against production artifacts, and
  prefer a provider agreement that excludes your traffic from training.
- **Token/cost reports** record item names, which can leak internal naming conventions.

None of these paths are tracked by git, but they do sit inside the working tree — take care with
backups, screen shares, and archive uploads.

---

## Reporting a vulnerability

Please **do not open a public issue** for a security problem.

Report privately through GitHub Security Advisories:
<https://github.com/baoluong2900/vba-to-wpf-migration/security/advisories/new>

Include the affected file and line, how to reproduce it, and the impact you see. A short proof of
concept helps a lot. This is a personal project, so expect a best-effort acknowledgement within
about a week rather than a commercial SLA.

If the finding is already listed under [Known weaknesses](#known-weaknesses), an issue referencing
the ID is fine — no advisory needed.
