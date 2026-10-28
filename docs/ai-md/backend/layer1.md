# Backend — Layer 1 (Parsing & seeding)

## Purpose
Layer 1 ingests the Access export (default `src/vba/vba_source/`: `Forms/*.frm`,
`Queries/*.sql.sql`, `Macros/*.mac`, `Modules/*.bas`, `Tables/AllColumns.csv`), turns every
object into JSON under `data/`, cross-references them, and seeds MongoDB. It is 100%
deterministic — no LLM calls.

## Steps (`src/backend/workflow/layer1/`)
| Script | Output |
| --- | --- |
| `parser/table_parser.py` | `data/tables/<table>.json` — `columns[]` with `logical_name` (CSV `LogicalName`, the field name queries use), `physical_name`, `data_type`, `length`, `required` |
| `parser/query_parser.py` | `data/queries/<query>.json` — `query_name`, `tables`, `parameters`, structured `query`, and the original Access text as `sql` |
| `parser/frm_parser.py` | `data/forms/`, `data/reports/` — controls (`items`), events, VBA `functions` |
| `parser/macro_parser.py` | `data/macros/` — `steps`, `references` |
| `parser/modules_parser.py` | `data/modules/` — `functions`, `constants`, `variables` |
| `aggregator.py` | Enriches the JSON with resolved references, writes `data/reference_map.json` and `data/graphs/<item>.json` (Cytoscape elements) |
| `seed_db.py` | Upserts every `data/<folder>` into the collection of the same name, `reference_map.json` into `reference_map`, and one `dependency_graph` document per item |

`dependency_graph` documents (`name`, `type`, `opens_forms`, `opens_reports`, `uses_queries`,
`calls_modules`, `direct_macros`, `uses_tables`, `opened_by`) are what Layer 2
(`db/layer1_repo._get_graph_context`) reads for BD/DD context.

## Batch runner
`run_all.py` runs the parsers, aggregation, seeding, `queries_v2` seeding (Layer 3), Layer 2
generation and the PostgreSQL migration in order. Step keys:
`tables, queries, forms, macros, modules, aggregate, seed, seed-queries, layer2, layer3`.

```bash
python run_all.py --list                 # show steps
python run_all.py --only tables,queries  # subset
python run_all.py --from seed            # resume
python run_all.py --skip layer3          # what the web console runs
python run_all.py --dry-run              # print the plan
python run_all.py --keep-going           # don't stop at the first failure
```
The step descriptions are matched by the console's progress view
(`src/frontend/src/app/api/v1/layer1/extract/route.ts`) — keep them stable.

## Constraints
- **One-way data flow:** Layer 1 only writes files and MongoDB; it never calls other layers.
- An export without some object type (no macros, no reports) is fine: parsers exit 0 on an
  empty folder and the seeder skips missing folders.
- Seeder output is streamed to the browser, so connection strings are logged redacted
  (`common.config.redact_uri`).

## Tests
`tests/backend/test_layer1_parsers.py` runs every parser on the fixture export into a temp dir;
`tests/backend/test_layer1_dependency_graph.py` covers the `dependency_graph` flattening.
