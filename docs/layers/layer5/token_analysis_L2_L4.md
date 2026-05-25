# 📊 Phân tích Token & Chi phí LLM (Layer 2 - Layer 4)

Tài liệu này ước tính lượng tài nguyên LLM tiêu tốn cho flow từ Phân tích màn hình (BD) đến sinh Query (SQL) cho 5 màn hình tiêu chuẩn.

---

## 1. Ước tính lượng Token theo Layer

| Layer | Công việc chính | Input Token (Avg) | Output Token (Avg) | Tổng Token / 1 Màn |
| :--- | :--- | :--- | :--- | :--- |
| **Layer 2 (S3 BD)** | Parse VBA/XML -> Layout JSON | 30,000 | 6,000 | 36,000 |
| **Layer 3 (D3 DD)** | Logic VBA -> Spec JSON | 40,000 | 10,000 | 50,000 |
| **Layer 4 (SQL)** | Logic Spec -> SQL Query | 10,000 | 2,000 | 12,000 |
| **TỔNG CỘNG** | | **80,000** | **18,000** | **98,000** |

---

## 2. Ước tính cho 5 Màn hình

*   **Tổng Input Tokens:** 400,000 tokens
*   **Tổng Output Tokens:** 90,000 tokens
*   **Tổng Token tiêu dụng:** ~490,000 tokens

---

## 3. So sánh chi phí API (Claude 3.5 Sonnet)

Claude 3.5 Sonnet hiện là model tối ưu nhất cho coding (tỷ lệ $3/1M Input và $15/1M Output).

| Hạng mục | Số lượng | Đơn giá ($/1M) | Thành tiền ($) |
| :--- | :--- | :--- | :--- |
| **Input Tokens** | 400,000 | $3.00 | $1.20 |
| **Output Tokens** | 90,000 | $15.00 | $1.35 |
| **TỔNG CỘNG** | | | **$2.55** |

> **Ước tính VND:** ~64,000 VNĐ cho toàn bộ 5 màn hình (L2 -> L4).

---

## 4. Đánh giá chất lượng Model

1. **Model "Xịn" (Claude 3.5 Sonnet / GPT-4o):**
   - **Ưu điểm:** Khả năng hiểu logic VBA phức tạp (vòng lặp, điều kiện lồng nhau) ở Layer 3 cực tốt. Giảm thiểu lỗi sai type dữ liệu khi sinh SQL ở Layer 4.
   - **Tỷ lệ sai sót:** Ước tính < 5%.

2. **Model "Free/Open Source" (Qwen 2.5 72B / Llama 3):**
   - **Ưu điểm:** Tốc độ nhanh, không tốn phí nếu chạy local/self-host.
   - **Nhược điểm:** Đôi khi cấu trúc JSON đầu ra không chuẩn hoặc bỏ sót các case logic biên (edge cases).
   - **Chênh lệch chất lượng:** Model xịn cho kết quả chính xác hơn khoảng **15-20%** đối với các màn hình có nghiệp vụ kế toán/tài chính phức tạp.

---
*Ghi chú: Số liệu trên mang tính chất tương đối, phụ thuộc vào độ dài thực tế của mã nguồn VBA và số lượng sự kiện trên mỗi màn hình.*
