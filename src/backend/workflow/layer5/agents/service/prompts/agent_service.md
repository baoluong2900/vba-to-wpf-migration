Agent Service — Overview Prompt
================================

This file is kept for backward compatibility. The agent now selects one of three
specialized prompts based on the event classification:

| Source signal in DD / VBA                       | Prompt used                  |
|--------------------------------------------------|------------------------------|
| `DLookup` / `DCount` / `DoCmd.RunSQL` / queries  | `agent_service_form.md`     |
| `DoCmd.RunMacro` / 参照マクロ / macro references  | `agent_service_macro.md`    |
| `Call <ModuleHandler>` / プロシージャ呼び出し      | `agent_service_module.md`   |

See `Agent_Service.md` (docs) for the full pipeline contract.
