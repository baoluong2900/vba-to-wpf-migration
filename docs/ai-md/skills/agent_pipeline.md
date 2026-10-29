# AI Agent Migration Pipeline

The primary skill of the agents in this repository is translating legacy Access/VBA systems into modern C# Avalonia (MVVM, .NET 10) architectures. The pipeline is split into distinct sequential agents.

## 1. BD Agent (Basic Design)
- Extracts UI layouts, events, and control metadata from MongoDB (parsed from raw Access files).
- Outputs structural mapping JSON files conforming to `bd_form.json` templates.
- **Output path:** `output/bd_flow/`

## 2. DD Agent (Detail Design)
- Reads the BD JSON outputs and extracts step-by-step logic and SQL queries.
- Outputs detailed functional JSON specifications mapping variables, SQL sets, and conditional logic conforming to `dd_form.json`.
- **Output path:** `output/dd_flow/`

## 3. C# Generation Agents (Layer 5)
Layer 5 consists of highly specialized, deterministic, and LLM-driven agents that ingest BD/DD files to construct the Avalonia application:
- **Agent Repo:** Tool-driven generation (0 tokens) of Entities, DTOs, and Repositories with Dapper. Only uses LLMs (Phase 2) to translate table/field identifiers still marked `"TODO"` in `name_config.json`, whatever `TARGET_LANGUAGE` is.
- **Agent Logic:** Generates ViewModel method bodies. Reads DD steps and uses LLMs to translate event flows into C#, patched into the ViewModel skeleton Agent UI built (commands, properties and the `I<Feature>Service` injection come from that skeleton).
- **Agent UI:** Translates Access form controls into Avalonia AXAML Windows/UserControls.
- **Agent Service:** Generates business logic services bridging ViewModels and Repositories.
- **Agent GraphView:** Validates the migration by building a deterministic dependency graph of the generated C# code and comparing it against the original VBA dependency tree to ensure no logic was lost (ok / missing / extra / mismatch items, overall PASS/FAIL reports).

