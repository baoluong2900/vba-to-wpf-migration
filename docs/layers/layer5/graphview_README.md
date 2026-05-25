# Agent GraphView

Phase 1 review theo form.

## Input

Dat 2 file vao `inputs/`:

```txt
inputs/mapping_{form}.json
inputs/dependency_{form}.json
```

Vi du:

```txt
inputs/mapping_F_Login.json
inputs/dependency_F_Login.json
```

`mapping_{form}.json` la mapping contract sinh tu VBA Graph API.

`dependency_{form}.json` la actual WPF dependency graph parse tu source WPF that.

## Output

Agent sinh:

```txt
outputs/review_{form}.json
```

Review JSON co:

```txt
nodeStatus
edgeStatus
source
target
expected
actual
status: ok | missing | mismatch | extra
```

UI GraphView dung file nay de to mau node/edge.

## Run

```bash
python agents/graphview/agent_graphview.py --form F_Login
```

Mac dinh:

```txt
inputs-dir  = agents/graphview/inputs
outputs-dir = agents/graphview/outputs
```

## Rule Phase 1

- Agent GraphView khong sinh code WPF.
- VBA graph goc la chuan cao nhat.
- Macro dung `handler:macro:*`.
- Navigation chi show `Handler -> NavigationService`.
- Query theo flow `Handler -> Service -> Repository`.
- Flow sai layer thi `FAIL`.
