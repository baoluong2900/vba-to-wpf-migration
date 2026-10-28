# Rule: Investigation Done Summary

## Khi nào áp dụng
Sau khi hoàn thành bất kỳ tác vụ điều tra nào (bug hunt, code review, scan lỗi, phân tích hệ thống), **bắt buộc** kết thúc bằng một Done Summary theo format chuẩn dưới đây.

---

## Format Done Summary

```
## ✅ Done Summary

### Đã điều tra
- <danh sách file/module đã scan>

### Bugs tìm thấy & đã fix: <N>
| # | File | Dòng | Loại bug | Mô tả ngắn | Trạng thái |
|---|------|------|----------|------------|------------|
| 1 | path/to/file.py | 42 | DeadCode | ... | ✅ Fixed |
| 2 | path/to/file.ts | 10 | UnguardedParse | ... | ✅ Fixed |

### Không phải bug (đã xác nhận)
- `file.py:line` — lý do tại sao không phải bug

### Còn lại / Cần theo dõi
- <nếu có vấn đề chưa fix hoặc cần thêm context>
```

---

## Quy tắc bắt buộc

1. **Luôn chạy `py_compile` và `yarn typecheck`** trước khi báo fixed — không báo fixed nếu chưa verify compile.
2. **Phân biệt rõ** "bug đã fix", "không phải bug", "cần theo dõi" — không gộp chung.
3. **Ghi rõ file + dòng** cho mỗi bug — không mô tả chung chung.
4. **Không báo cáo false positive** — phải đọc context đủ trước khi kết luận là bug.
5. **Nếu không tìm thấy bug** → vẫn phải có Done Summary với mục "Bugs tìm thấy: 0" và liệt kê những gì đã scan.
