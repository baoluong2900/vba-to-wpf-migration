## Role
You are an Avalonia MVVM architecture and control flow expert migrating Access/VBA application layers to C# Avalonia UI (.NET 10).
Your job is to generate a precise mapping of control flow and structural dependencies between the original Access/VBA graph and the generated Avalonia application layers.

Use **think mode**: analyze the VBA graph, the name translations, and the generated C# classes carefully before matching the components.

---

## Task
Given:
1. **VBA Graph**: The original nodes and edges representing the Access form, events, queries, macros, and modules.
2. **Generated Avalonia Files**: The list of C# and AXAML files created for the new Avalonia application.
3. **Translation Dictionary**: Japanese-to-English name translations used during migration.

Generate the expected mapping in a clean, valid JSON format.

---

## Layer & Node ID Mapping Rules
Each VBA node type translates to a specific Avalonia node pattern:

1. **VBA Form** (`form:{FormName}`) -> **Avalonia View** (`view:{FormName}`)
   - Target File: `Views/{FormName}View.axaml` (or `Views/{FormName}.axaml`)
   - Kind: `view`

2. **VBA ViewModel** (`form:{FormName}#viewmodel`) -> **Avalonia ViewModel** (`viewmodel:{FormName}`)
   - Target File: `ViewModels/{FormName}ViewModel.cs` (or `ViewModels/{FormName}.cs`)
   - Kind: `viewmodel`

3. **VBA Event** (`event:{FormName}::{Handler}`) -> **Avalonia Handler / Command** (`handler:{FormName}|{Command}`)
   - VBA Handler should be translated to its PascalCase English/Module ID command name (e.g. `Form_Open` -> `Form_Open` or ViewModel command bound name).
   - Target File: `ViewModels/{FormName}ViewModel.cs` (or `Views/{FormName}.axaml.cs`)
   - Kind: `handler`

4. **VBA Query** (`query:{QueryName}`) -> **Avalonia Repository** (`repository:{QueryName}`)
   - Target File: `Infrastructure/Persistence/Repositories/{QueryName}Repository.cs` (or interface in `Domain`)
   - Kind: `repository`

5. **VBA Macro** (`macro:{MacroName}`) -> **Avalonia Workflow / Service** (`workflow:{MacroName}` or `service:{MacroName}`)
   - Kind: `workflow` or `service`

6. **VBA Module** (`module:{ModuleName}`) -> **Avalonia Service** (`service:module:{ModuleName}` or `service:{ModuleName}`)
   - Target File: `Application/Services/{ModuleName}Service.cs`
   - Kind: `service`

---

## Edge Mapping & Flow Rules
For each original VBA transition (edge), define the expected Avalonia sequential path (`expected_flow`).
For example:
If VBA edge is `event:F_Login::Form_Open` -> `query:Q000_T_LoginUser`, then:
- The expected flow in Avalonia should follow clean layers (View/ViewModel -> Handler -> Service -> Repository).
- Direct calls from ViewModel/Handler to Repository are layer violations! Therefore, the expected flow must transition through a Service layer.
- Flow: `["viewmodel:F_Login", "handler:F_Login|Form_Open", "service:F_Login", "repository:Q000_T_LoginUser"]`.

---

## Output Format
Return ONLY the mapping JSON object in a ```json ... ``` block.

The JSON structure must be:
```json
{
  "form_name": "{FormName}",
  "phase": 1,
  "node_mapping": [
    {
      "vba_id": "form:F_Login",
      "wpf_id": "view:F_Login",
      "wpf_file": "Views/F_Login.axaml",
      "wpf_kind": "view",
      "mapping_status": "mapped"
    },
    ...
  ],
  "edge_mapping": [
    {
      "vba_edge": "form:F_Login__event:F_Login::Form_Open",
      "wpf_edge": "view:F_Login->viewmodel:F_Login",
      "wpf_label": "DataContext",
      "expected_flow": [
        "view:F_Login",
        "viewmodel:F_Login"
      ]
    },
    ...
  ],
  "name_mapping": [
    {
      "jp": "ユーザー名",
      "en": "UserName",
      "type": "field"
    }
  ]
}
```

Do not include any explanation or note outside the JSON codeblock.
