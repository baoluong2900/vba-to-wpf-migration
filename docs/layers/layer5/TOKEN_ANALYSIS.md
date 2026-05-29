# LLM Token & API Cost Analysis (Layer 2 – Layer 4)

This document provides a comprehensive resource estimation and cost analysis of LLM processing for the Screen Analysis (BD), Logic Modeling (DD), and Query Migration phases (Layers 2 to 4).

---

## 1. Average Token Consumption per Screen

| Pipeline Phase | Primary Execution | Avg. Input Tokens | Avg. Output Tokens | Total Tokens / Form |
|---|---|---|---|---|
| **Layer 2 (S3 BD)** | VBA to Layout JSON | 30,000 | 6,000 | 36,000 |
| **Layer 3 (D3 DD)** | VBA to Logic JSON Specs | 40,000 | 10,000 | 50,000 |
| **Layer 4 (SQL)** | Logic Spec to Oracle SQL | 10,000 | 2,000 | 12,000 |
| **TOTAL ESTIMATION**| | **80,000** | **18,000** | **98,000** |

---

## 2. API Financial Projection (5 Baseline Forms)

The API costs are evaluated using current commercial parameters for advanced programming models (e.g., **Claude 3.5 Sonnet**, priced at $3.00 per 1M Input tokens and $15.00 per 1M Output tokens):

- **Total Projection (5 Forms):**
  - Input Volume: 400,000 tokens
  - Output Volume: 90,000 tokens
  - Aggregate Volume: 490,000 tokens

### Cost Breakdown:

| Token Category | Volume | Rate ($ / 1M) | Total Cost (USD) |
|---|---|---|---|
| Input Tokens | 400,000 | $3.00 | $1.20 |
| Output Tokens | 90,000 | $15.00 | $1.35 |
| **AGGREGATED TOTAL** | | | **$2.55** |

> *VND Exchange Reference:* Approximately 64,000 VNĐ in total processing costs to migrate 5 standard Access forms completely from Layer 2 to Layer 4.

---

## 3. Comparative LLM Performance Evaluation

### 3.1. Premium Commercial Models (Claude 3.5 Sonnet / GPT-4o)
- **Strengths:** Exceptional logical comprehension of deeply nested legacy VBA syntax (loops, conditional clauses) inside Layer 3. Negligible error rates when translating types to Oracle SQL parameters inside Layer 4.
- **Estimated Error Margin:** < 5%.

### 3.2. Open Source / Self-Hosted Models (Qwen 2.5 72B / Llama 3)
- **Strengths:** High execution speed with zero per-token execution costs when deployed on local infrastructure.
- **Weaknesses:** Occasional structural formatting issues or minor omissions of edge-case conditions in complex accounting structures.
- **Quality Variance:** Commercial models provide a **15% to 20%** accuracy improvement for highly complex transaction operations.
