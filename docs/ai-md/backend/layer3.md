# Backend — Layer 3 (SQL migration → PostgreSQL)

## Purpose
Layer 3 turns the Access query and table definitions that Layer 1 stored in MongoDB into
PostgreSQL: deterministic `CREATE TABLE` DDL for tables, and LLM-assisted, human-reviewed
conversion for queries. It is exposed over gRPC as **`Layer4Service`** (historical naming swap —
see the README) and driven from the console page `/layer3`.

## Modules (`src/backend/workflow/layer3/sql_migration/`)
| Module | Responsibility |
| --- | --- |
| `table_converter.py` | Pure function `convert_table_to_ddl(table, target_db)`. Table-driven Access→dialect type map (PostgreSQL target; SQL Server / MySQL / ANSI for comparison), identifiers quoted only when required, optional `PRIMARY KEY` from columns flagged `primary_key`. |
| `query_utils.py` | Pure helpers: rebuild SQL from Layer 1's structured query (SELECT / UPDATE / DELETE / INSERT / TRANSFORM), `query_type_of`, `target_table_of`, `extract_bind_variables` (ignores `::casts`, time values and string literals). |
| `seed_queries_v2.py` | Sync Layer 1 `queries` → `queries_v2`: inserts new queries with review fields reset, refreshes source fields of existing ones, never touches review work. |
| `router.py` | Operations behind `Layer4Service`: list/get/update/convert queries, stats, list tables, convert table schema. Every function returns `{"success": bool, ...}`. |
| `postgres_migrator.py` | CLI: create the PostgreSQL tables via `psql` (`--dry-run`, `--table`, `--output`). |

## Data
- **Input:** `queries` and `tables` (Layer 1). Query documents carry the original Access SQL as
  top-level `sql` (written by `layer1/parser/query_parser.py`).
- **Working collection:** `queries_v2` — one document per query: `sql`/`raw_sql` (source),
  `query`, `query_type`, `tables`, `target_table`, `parameters` (source fields, refreshed on
  re-seed) and `target_sql`, `target_query_json`, `conversion_status`
  (`pending` | `converted` | `error`), `reviewer`, `notes`, `description`, `bind_variables`
  (review fields). Layer 2 also reads `queries_v2` for query context, so the batch pipeline seeds
  it (`run_all.py` step `seed-queries`) before BD/DD generation.

## Rules that matter
- **Reviewed SQL is never lost.** A failed or unparseable LLM conversion marks the query
  `error` and keeps the stored `target_sql`. A save only overwrites fields the client actually
  sent (proto3 cannot tell "unset" from `""`), except `target_sql`, which is always written.
- **Identifier quoting preserves case folding.** Plain names stay unquoted so PostgreSQL folds
  them to lower case exactly as before — generated Dapper repositories reference tables without
  quotes. Only names with spaces/punctuation, a leading digit or a reserved word are quoted.
- **DDL execution is explicit.** `postgres_migrator.py` drops and recreates each table in one
  `psql -c` transaction; use `--dry-run` (optionally `--output schema.sql`) to review first.
  The web console's pipeline run skips this step (`run_all.py --skip layer3`).
- **Query testing in the console is a static check** (`src/frontend/src/app/api/v1/layer3/
  staticSqlCheck.ts`): leftover Access functions/syntax, quoting and parentheses, reported with
  PostgreSQL SQLSTATE codes. Nothing is executed against a database.
- Settings come from `src/backend/common/config.py` (env → `config.json` → default):
  `MONGO_URI`/`MONGO_DB`, `POSTGRES_*`, `LAYER3_MIGRATION_MODEL`.

## CLI
```bash
cd src/backend/workflow/layer3/sql_migration
python seed_queries_v2.py                              # queries → queries_v2
python postgres_migrator.py --dry-run --output schema.sql
python postgres_migrator.py --table TBL_Users          # one table
python postgres_migrator.py                            # all tables (exit 1 if any failed)
```

## Tests
`tests/backend/test_layer3_*.py` — converter type map and quoting, query helpers, seeding,
and the review workflow (`router.py`) against an in-memory collection with a fake LLM.
