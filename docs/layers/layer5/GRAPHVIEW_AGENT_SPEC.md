# Layer 5 — GraphView Agent Operational Specification

This document details the inputs, outputs, commands, and rules for the **GraphView Agent** in Layer 5, which performs comparative dependency validation on migrated forms.

---

## 1. Execution Role
The GraphView Agent does not generate C# or XAML source code. Instead, it acts as a **verification and quality assurance gate** to ensure that no operational data flows, queries, or macros were lost during the modernization of a legacy Access form.

---

## 2. Directory & Mapped Files

```text
src/backend/workflow/layer5/agents/graphview/
├── agent_graphview.py         # Main execution entry script
├── dependency_builder.py      # Deterministic C# static analysis parser
├── inputs/
│   ├── mapping_{Form}.json       # Source dependency map generated from Access/VBA
│   └── dependency_{Form}.json    # Mapped actual C# dependency graph generated from C# source
└── outputs/
    └── review_{Form}.json        # Discrepancy analysis report
```

### Review Output Structure (`review_{Form}.json`):
- `nodeStatus` / `edgeStatus`: Logs missing or mismatched dependencies.
- `source` / `target`: Call relationship bindings.
- `expected`: Mapped element in legacy Access.
- `actual`: Mapped element in migrated C#.
- `status`: `ok`, `missing`, `mismatch`, or `extra`.

---

## 3. Execution Commands

Execute validation for a target form using the following command:
```bash
python agents/graphview/agent_graphview.py --form F_Login
```

Options:
- `--inputs-dir`: Default is `agents/graphview/inputs`
- `--outputs-dir`: Default is `agents/graphview/outputs`

---

## 4. Phase 1 Dependency Rules
- **Source Authority:** The legacy Access/VBA call graph is treated as the highest authority (source of truth).
- **Macro Mapping:** Macro triggers must map to C# Navigation actions, i.e., `Handler -> NavigationService`.
- **Query Flow:** Query operations must strictly adhere to the layered execution flow: `UI Event Handler -> Service -> Repository -> SQL`.
- **Layer Violations:** If a View accesses the Repository directly (bypassing the Service layer) or does not match query parameters, it is flagged as a **FAIL / Layer Violation**.
