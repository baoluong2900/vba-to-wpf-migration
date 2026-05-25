# Backend - Layer 5 (C# Code Generation)

## Purpose
Layer 5 is responsible for the final translation phase: converting the standardized JSON specifications (from Layer 2) into modern C# WPF source code.

## Key Sub-Agents
1. **Agent Repo (`agent_repo.py`):**
   - Reads DD SQL specs and table schemas.
   - Generates Entities, DTOs, and Repositories with Dapper.
   - Almost entirely deterministic (0 LLM tokens) except for translating unknown Japanese names via a `TODO` batch LLM phase.
2. **Agent Logic (`agent_logic.py`):**
   - Generates C# MVVM ViewModels.
   - Reads DD step-by-step logic and translates VBA events into RelayCommands, Properties, and Service DI injections.
   - Breaks complex events into chunks and merges them via AST to save LLM context window limits.
3. **Agent UI:**
   - Translates BD layout outputs into XAML files (Windows and UserControls).
4. **Agent Service:**
   - Generates Business Logic Services bridging ViewModels and Repositories.
5. **Agent GraphView (`agent_graphview.py`):**
   - Builds a deterministic dependency graph of the generated C# code.
   - Compares the WPF graph against the original VBA graph to detect missing implementations (MISSING) or new features (EXTRA).

## Constraints
- **Localization:** Reads `TARGET_LANGUAGE` to determine the language for XML document comments (e.g. `/// <summary>`) and code notes.
