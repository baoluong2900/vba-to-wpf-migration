# Security Policy

## Project status

`vba_brain` is a **working prototype for local and internal use.** It is not hardened for
internet exposure. The items below are known, tracked, and deliberately documented rather than
hidden — read them before you run this anywhere but `localhost`.

---

## Known weaknesses

| ID | Issue | Evidence | Severity |
| --- | --- | --- | --- |
| S1 | The gRPC gateway is unauthenticated and unencrypted — any process that can reach the port can drive the whole pipeline, including LLM spend | `src/backend/api_gateway/grpc_server.py:595` — `server.add_insecure_port('[::]:50051')` | 🔴 High |
| S2 | Mongo Express ships with `admin` / `admin123` from `infa/.env.example` | `infa/.env.example` | 🔴 High if reachable |
| S3 | Default database credentials (`vba_brain` / `vba_brain2024`) are committed as example values | `infa/.env.example` | 🟡 Medium |
| S4 | Layer 3 executes LLM-generated DDL against PostgreSQL without a dry-run gate | `layer3/sql_migration/postgres_migrator.py` | 🟡 Medium |
| S5 | Python dependencies are floor-pinned (`>=`) with no lockfile, so builds are not reproducible | `src/backend/requirements.txt` | 🟡 Medium |
| S6 | Automated test coverage is thin, so regressions in security-relevant paths are not caught | repo-wide | 🟡 Medium |

Remediation for each is tracked in [`docs/UPGRADE_PLAN.md`](docs/UPGRADE_PLAN.md) Phase 1–2.

---

## What is already in place

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
- [ ] **Put authentication in front of gRPC.** Add a token/API-key interceptor and switch to
      `add_secure_port` with TLS certificates (`docs/UPGRADE_PLAN.md` §1.1).
- [ ] **Keep container ports on `127.0.0.1`.** If a remote client genuinely needs access, front it
      with a reverse proxy that terminates TLS and authenticates, rather than widening the bind.
- [ ] **Restrict the PostgreSQL migration role.** Layer 3 executes generated DDL; give it rights
      to the target schema only, never superuser.
- [ ] **Review generated SQL before executing it.** Treat LLM output as untrusted input.
- [ ] **Rotate LLM API keys on a schedule** and set a budget cap in the provider console — an
      unauthenticated gateway is also an unauthenticated way to spend money.
- [ ] **Pin dependencies** (`==` plus a lockfile) so an upstream compromise cannot arrive silently.
- [ ] **Scan git history for leaked keys** before making a repository public:
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
