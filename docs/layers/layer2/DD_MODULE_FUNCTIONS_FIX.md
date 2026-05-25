# DD Module Functions Fix - Support D1 Skeleton `functions` Array

## Problem

DD Agent không gen được common module `AppWinCenter.json` - output rỗng:
- `d2_dd_mapping/AppWinCenter.json`: `sheet_2_detail: []` (có 8 entries nhưng tất cả rỗng)
- `d3_dd_logic/input_AppWinCenter.json`: `[]`
- `d4_dd_final/AppWinCenter.json`: `sheet_2_detail: []`

Log cho thấy: `[DD Service] [D3] Done — 0 modules processed.`

## Root Cause

D1 skeleton (`d1_dd_skeleton/AppWinCenter.json`) có cấu trúc:
```json
{
  "module": {
    "name": "AppWinCenter",
    "functions": [
      {
        "handler": "SystemParametersInfo Lib \"user32\" Alias \"SystemParametersInfoA\"",
        "type": "Declare Function",  // ← Windows API declaration, không có code
        "input": "...",
        "output": "Long"
      },
      {
        "handler": "GetWindowRect Lib \"user32\"",
        "type": "Declare Function"  // ← Windows API declaration
      },
      {
        "handler": "SetWindowPos Lib \"user32\"",
        "type": "Declare Function"  // ← Windows API declaration
      },
      {
        "handler": "AppWinCenter",
        "visibility": "public",
        "type": "Function",  // ← Real function with code
        "code": "Dim hWnd As Long\n Dim wRect As RECT, aRect As RECT\n..."
      }
    ]
  }
}
```

**Có 3 vấn đề:**

### Issue 1: `parse_dd_source()` không tìm `module.functions`

Code trong `fill_utils.py` chỉ tìm:
```python
functions = dd_source.get("procedures") or dd_source.get("vba_procedures")

# Check inside form/report blocks
if not functions:
    form_or_report = dd_source.get("form") or dd_source.get("report")
    if isinstance(form_or_report, dict):
        functions = form_or_report.get("vba_procedures") or form_or_report.get("procedures")
# ❌ Không tìm trong module.functions!
```

→ `functions` = `None` → `logic_items` = `[]`

**Note**: `parse_dd_source()` đã có logic skip Declare Functions (line 182):
```python
if proc.get("type", "").lower() == "declare function":
    continue
```

### Issue 2: `fill_dd_from_bd_json.py` không tìm `module.functions`

Code trong `fill_dd_from_bd_json.py` line ~586:
```python
if category == "common":
    module_data = d1_data.get("module", {})
    procedures = module_data.get("procedures", [])  # ❌ Không tìm "functions"!
```

→ `procedures` = `[]` → không add missing procedures

### Issue 3: `fill_dd_from_bd_json.py` không skip Declare Functions

Code trong `fill_dd_from_bd_json.py` line ~596:
```python
for proc in procedures:
    handler = proc.get("handler", "") or proc.get("name", "")
    if handler:
        d1_vba_map[handler] = proc  # ❌ Không skip Declare Functions!
```

→ Tất cả 4 functions (3 Declare + 1 real) đều được add vào `d1_vba_map`
→ D2 mapping tạo 8 sheets (duplicate với case-sensitive/insensitive)
→ Chỉ có 1 function thực sự (AppWinCenter) có code, 3 Declare Functions không có code

## Solution

### Fix 1: Update `fill_utils.py` - `parse_dd_source()`

```python
functions = dd_source.get("procedures") or dd_source.get("vba_procedures")

# Check inside form/report blocks
if not functions:
    form_or_report = dd_source.get("form") or dd_source.get("report")
    if isinstance(form_or_report, dict):
        functions = form_or_report.get("vba_procedures") or form_or_report.get("procedures")

# Check inside module block (for common modules)
if not functions:
    module_data = dd_source.get("module")
    if isinstance(module_data, dict):
        functions = module_data.get("procedures") or module_data.get("functions")
```

**Note**: Đã có logic skip Declare Functions, không cần fix thêm.

### Fix 2: Update `fill_dd_from_bd_json.py` - Support `module.functions`

```python
if category == "common":
    module_data = d1_data.get("module", {})
    # Try both 'procedures' and 'functions' (D1 skeleton uses 'functions')
    procedures = module_data.get("procedures", []) or module_data.get("functions", [])
```

### Fix 3: Update `fill_dd_from_bd_json.py` - Skip Declare Functions **NEW**

```python
for proc in procedures:
    # Skip Declare Functions (Windows API declarations)
    if proc.get("type", "").lower() == "declare function":
        continue
        
    handler = proc.get("handler", "") or proc.get("name", "")
    if handler:
        d1_vba_map[handler] = proc
```

## Files Modified

- ✅ `dd_agent/fill_utils.py` - Line ~165 (parse_dd_source) - Added `module.functions` support
- ✅ `dd_agent/fill_dd_from_bd_json.py` - Line ~586 - Support `module.functions`
- ✅ `dd_agent/fill_dd_from_bd_json.py` - Line ~596 - **Skip Declare Functions** (NEW)

## Testing

### Before Fix
```bash
# Run DD flow for AppWinCenter
python -m dd_agent.dd_service --screen AppWinCenter --category common

# Result:
# d2_dd_mapping/AppWinCenter.json: sheet_2_detail: [] (hoặc 8 entries rỗng)
# d3_dd_logic/input_AppWinCenter.json: []
# d4_dd_final/AppWinCenter.json: sheet_2_detail: []
```

### After Fix
```bash
# Run DD flow for AppWinCenter
python -m dd_agent.dd_service --screen AppWinCenter --category common

# Expected result:
# d2_dd_mapping/AppWinCenter.json: sheet_2_detail: [{ module_id: "AppWinCenter", code: "..." }]
#   → Chỉ 1 entry cho function thực sự, không có Declare Functions
# d3_dd_logic/input_AppWinCenter.json: [{ module_id: "AppWinCenter", code: "..." }]
# d4_dd_final/AppWinCenter.json: sheet_2_detail: [{ module_id: "AppWinCenter", steps: [...] }]
```

### Verify D1 Skeleton Structure
```python
import json
from pathlib import Path

d1_path = Path("output/dd_flow/common/d1_dd_skeleton/AppWinCenter.json")
with open(d1_path, encoding="utf-8") as f:
    d1_data = json.load(f)

module_data = d1_data.get("module", {})
procedures = module_data.get("procedures", [])
functions = module_data.get("functions", [])

print(f"procedures: {len(procedures)}")  # Before: 0
print(f"functions: {len(functions)}")    # Before: 4 (Declare + 1 Function)

# After fix, code will use functions array
```

## Impact

### Before Fix
- ❌ Common modules with `functions` array không được parse
- ❌ DD output rỗng cho các modules như AppWinCenter, SetEnabledState, etc.
- ❌ LLM không gen được detail specs

### After Fix
- ✅ Support cả `procedures` và `functions` arrays
- ✅ DD output đầy đủ cho tất cả common modules
- ✅ LLM gen được detail specs cho functions

## Related Issues

Các common modules khác có thể bị ảnh hưởng:
- `AppWinCenter` - Center application window
- `SetEnabledState` - Enable/disable controls
- `SetWindowTop` - Set window z-order
- `EmptyClipboard` - Clear clipboard
- `CloseClipboard` - Close clipboard
- Và các modules khác có `functions` array trong D1 skeleton

## Next Steps

1. ✅ Fix code để support `functions` array
2. [ ] Regenerate DD flow cho tất cả common modules
3. [ ] Verify output có đầy đủ procedures
4. [ ] Test LLM generation quality

## Related Documentation
- `FIX_SUMMARY.md` - Tổng hợp tất cả fixes
- `DD_MODULE_MACRO_FIX.md` - VBA extraction for Module/Macro
