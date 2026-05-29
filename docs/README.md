# vba_brain Documentation Directory Index

Welcome to the unified documentation catalog for **vba_brain** — the automated pipeline designed to modernize legacy Microsoft Access VBA systems into modern C# WPF MVVM applications on Oracle Databases.

---

## 🗺️ Documentation Directory Map

```text
docs/
├── README.md                          # ← You are here (Unified Index)
├── ARCHITECTURE_SPEC.md               # Architecture mapping (VBA to Clean C# WPF)
│
├── design/                            # Core System Specifications & Mappings
│   ├── STANDARD_SPEC.md               # Spreadsheet layout rules & banners (BD & DD)
│   ├── REQUIREMENTS.md                # Quality requirements & review checklist
│   └── EXCEL_MAPPING_SPEC.md          # Property mappings from pipeline JSON to Excel
│
├── layers/                            # Detailed Layered Ingestion Mappings
│   ├── layer1/
│   │   └── README.md                  # Access parser mechanisms & seeding guides
│   ├── layer2/
│   │   └── DD_AGENT_FIXES.md          # Detailed DD Agent fixes & optimizations
│   ├── layer3/
│   │   └── TABLE_MAPPING.md           # Database tables classification index
│   └── layer5/
│       ├── L5_AGENTS_SPEC.md          # Specs for all 8 code generation sub-agents
│       ├── AI_AGENT_WORKFLOW_SPEC.md  # Multi-agent pipelines, caching, and fix loop
│       ├── SERVICE_AGENT_SPEC.md      # Service agent loader models & schemas
│       ├── GRAPHVIEW_AGENT_SPEC.md    # Call graph static analyzer & verification
│       ├── NAMING_AND_MAPPING_RULES.md# PascalCase identifier formatters & regex rules
│       └── TOKEN_ANALYSIS.md          # LLM average token size & API cost analysis
│
└── ai-md/                             # AI-Agent Operational Knowledge Base
    ├── rules/                         # Coding standards & architectural guidelines
    ├── skills/                        # Ingestion skills & pipeline models
    ├── frontend/                      # Presentation layer guides (WPF)
    └── backend/                       # Layer 1 to Layer 5 operational prompts
```

---

## 🎯 Primary Documentation References

- **System Architecture Design:** For a detailed breakdown of Clean Architecture mappings, MVVM MVVM namespaces, and physical class patterns, refer to [ARCHITECTURE_SPEC.md](file:///Users/baoluong0209/GitTool/vba_mirgation/workflow/docs/ARCHITECTURE_SPEC.md).
- **Spreadsheet Design Standards:** For Excel layout templates, file nomenclature, version control protocols, and header variables, read [STANDARD_SPEC.md](file:///Users/baoluong0209/GitTool/vba_mirgation/workflow/docs/design/STANDARD_SPEC.md).
- **Compliance Checklist:** Before releasing modernized sheets, review the compliance standards in [REQUIREMENTS.md](file:///Users/baoluong0209/GitTool/vba_mirgation/workflow/docs/design/REQUIREMENTS.md).
- **Pipeline Data Contract:** To inspect exactly how JSON properties are mapped dynamically to Excel targets, read [EXCEL_MAPPING_SPEC.md](file:///Users/baoluong0209/GitTool/vba_mirgation/workflow/docs/design/EXCEL_MAPPING_SPEC.md).
- **Specialized Code Generation Agents:** To understand the execution scope, LLM selections, inputs, and outputs of the 8 Layer 5 sub-agents, refer to [L5_AGENTS_SPEC.md](file:///Users/baoluong0209/GitTool/vba_mirgation/workflow/docs/layers/layer5/L5_AGENTS_SPEC.md).
- **Codegen Orchestration & Directories:** To learn about conflict-free file structures, few-shot vector database lookups, and compiler self-healing loops, read [AI_AGENT_WORKFLOW_SPEC.md](file:///Users/baoluong0209/GitTool/vba_mirgation/workflow/docs/layers/layer5/AI_AGENT_WORKFLOW_SPEC.md).
