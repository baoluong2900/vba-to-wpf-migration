## What & why

<!-- What does this change, and what problem does it solve? Link an issue if one exists. -->

Closes #

## Scope

<!-- Tick every area this PR touches. -->

- [ ] Layer 1 — AST extraction
- [ ] Layer 2 — BD/DD generation
- [ ] Layer 3 — SQL migration
- [ ] Layer 4 — Excel export
- [ ] Layer 5 — Code generation
- [ ] gRPC gateway / `.proto`
- [ ] Web console (frontend)
- [ ] Avalonia app (`src/wpf`)
- [ ] Infrastructure / CI
- [ ] Docs

## Quality gates

<!-- Paste the real result. "Should pass" is not a result. -->

- [ ] `ruff check src/backend tests start.py start_wpf.py clean_generated_files.py infa/scripts`
- [ ] `pytest && pytest tests/layer5`
- [ ] `cd src/frontend && yarn lint && npx tsc --noEmit -p tsconfig.json && yarn test && yarn build`
- [ ] `dotnet build src/wpf/vba_brain.slnx` (if `src/wpf` or Layer 5 changed)
- [ ] Ran the affected pipeline layer end to end (say which item / command)

<details>
<summary>Output</summary>

```
paste here
```

</details>

## Hard rules

<!-- These are enforced. See CONTRIBUTING.md §3. -->

- [ ] No secrets added to tracked files (`config.json`, `.env`, `appsettings.json` stay ignored)
- [ ] No hard-coded API keys, hosts, ports, or model IDs — everything goes through
      `common/config.py` / `config.json`
- [ ] Used `yarn`, not `npm` (`yarn.lock` unchanged unless dependencies were intentionally touched)
- [ ] No generated artifacts committed (`src/excel_outputs/`, `layer*/output/`, `data/`, `.next/`,
      `bin/`, `obj/`)
- [ ] Docker port bindings still on `127.0.0.1`
- [ ] `.proto` changes include regenerated stubs in the same commit
- [ ] Request data never reaches a shell or an unchecked filesystem path (argv arrays; names
      validated and paths confined to their base directory)

## Docs

- [ ] README / `docs/` updated for any behaviour change
- [ ] `CHANGELOG.md` updated under **Unreleased**
- [ ] `docs/UPGRADE_PLAN.md` items ticked if this PR completes them

## Notes for the reviewer

<!-- Anything deliberately left out, risky areas, or follow-up work. -->
