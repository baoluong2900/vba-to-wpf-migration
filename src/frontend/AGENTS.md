# Agent Instructions for vba_brain

You are an AI coding assistant working on the vba_brain (Automated Framework for UI Technical Analysis) project.

## Context
vba_brain extracts technical design documentation (BD/DD) from source code using LLMs and automated AST analysis.

## Directory Structure
```
workflow/
├── start.py              ← Launcher: chạy FE + BE bằng 1 lệnh Python
├── config.json           ← API keys & settings (KHÔNG commit lên git)
├── config.example.json   ← Template config để commit lên git
├── .gitignore            ← Bỏ qua config.json, .env, logs
├── frontend/             ← Next.js app (yarn dev)
│   └── src/app/api/      ← API routes gọi backend Python
└── backend/
    └── layer2/           ← Python scripts, MongoDB logic
```

## Key Technical Decisions
1. **Package Manager**: Luôn dùng `yarn`. **KHÔNG BAO GIỜ** dùng `npm`.
2. **Frontend**: Next.js (App Router), React Flow, Vanilla CSS, TypeScript.
3. **Backend**: Python scripts chạy qua `child_process.exec` từ Next.js API routes.
4. **API Pathing**: Từ `frontend/`, relative path tới backend là `../backend/`.
5. **Python**: Luôn chạy với `python -X utf8` để tránh lỗi encoding trên Windows.

## Config System (QUAN TRỌNG)
- **KHÔNG hardcode** API keys hay URLs vào source code.
- Tất cả config (API keys, MongoDB URI, model list, ports) nằm ở `workflow/config.json`.
- Frontend đọc config qua endpoint **`GET /api/config`** (trả về model list an toàn, không expose key).
- Backend API route `bd-agent/route.ts` đọc key từ `config.json` qua hàm `resolveProviderConfig()`.
- Khi thêm provider LLM mới, **chỉ sửa `config.json`** — không cần sửa source code.

## Common Commands
```bash
# Khởi động toàn bộ hệ thống
python start.py

# Chỉ chạy Frontend
python start.py --fe-only
# hoặc: cd frontend && yarn dev

# Chỉ chạy Backend API server (nếu có server.py)
python start.py --be-only

# Build production
cd frontend && yarn build
```

## Aesthetic Standards
- Premium, state-of-the-art UI — KHÔNG design tối giản/generic.
- Dùng curated color palettes, smooth animations, glassmorphism.
- Mỗi page cần `<h1>` mô tả rõ và meta tags đầy đủ.
