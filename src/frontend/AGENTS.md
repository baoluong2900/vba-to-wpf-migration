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
└── src/
    ├── frontend/         ← Next.js app (yarn dev)
    │   └── src/
    │       ├── app/      ← Pages (layer1–5) + API routes → gRPC gateway
    │       ├── components/  ← Header, Footer, GraphView, nodes/
    │       └── lib/         ← Shared helpers (logging.ts)
    └── backend/          ← Python: gRPC gateway + layer1–5 pipeline
        └── api_gateway/grpc_server.py  ← entry point, port 50051
```

## Key Technical Decisions
1. **Package Manager**: Luôn dùng `yarn`. **KHÔNG BAO GIỜ** dùng `npm`.
2. **Frontend**: Next.js 16 (App Router), React 19, React Flow, Tailwind CSS v4, TypeScript.
3. **Backend**: gRPC gateway (port 50051); FE gọi qua API routes trong `src/frontend/src/app/api/`.
4. **API Pathing**: Từ `src/frontend/`, relative path tới backend là `../backend/`.
5. **Python**: Luôn chạy với `python -X utf8` để tránh lỗi encoding trên Windows.

## Config System (QUAN TRỌNG)
- **KHÔNG hardcode** API keys hay URLs vào source code.
- Tất cả config (API keys, MongoDB URI, model list, ports) nằm ở `workflow/config.json`.
- Backend đọc key từ `config.json` (xem `src/backend/common/config.py`); FE nhận model list an toàn qua gRPC (`Layer2Service.GetConfig`), không expose key.
- Khi thêm provider LLM mới, **chỉ sửa `config.json`** — không cần sửa source code.

## Common Commands
```bash
# Khởi động toàn bộ hệ thống (FE :3000 + gRPC :50051)
python start.py

# Chỉ chạy Frontend
python start.py --fe-only
# hoặc: cd src/frontend && yarn dev

# Chỉ chạy Backend gRPC gateway
python start.py --be-only

# Build production
cd src/frontend && yarn build
```

## Aesthetic Standards
- Premium, state-of-the-art UI — KHÔNG design tối giản/generic.
- Dùng design tokens trong `globals.css` (light + dark), smooth animations, glassmorphism.
- KHÔNG hardcode màu — luôn dùng CSS variable tokens để đồng bộ 2 theme.
- Tái sử dụng shared helpers trong `src/lib/logging.ts` cho log console.
