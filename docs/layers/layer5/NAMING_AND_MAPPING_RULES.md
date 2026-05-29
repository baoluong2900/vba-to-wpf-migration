# Layer 5 — WPF MVVM Naming & Translation Rules Specification

This document details the naming conventions, Japanese-to-English replacements, and automated identifier formatting logic used when modernizing legacy MS Access forms, queries, and macros into C# WPF MVVM classes.

---

## 1. Automated Identifier Translation Pipeline

The Python script `export_forms_layer1.py` executes the following sequential transformation pipeline to convert legacy Japanese/Unicode names into clean C# PascalCase identifiers:

```text
┌──────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Legacy Name  │ ──>│  NFKC Unicode   │ ──>│ Object Specific │ ──>│ PascalCase Split│
│ (Access/VBA) │    │  Normalization  │    │ JP-to-EN Table  │    │  & Strip Extra  │
└──────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 1.1. Unicode Normalization
- The script applies `unicodedata.normalize("NFKC", ...)` to clean raw character bytes.
- NFKC automatically expands Roman numerals like `Ⅱ` (U+2161) into Latin character pairs `II`. The pipeline handles this behavior by restoring `II` back into the system-standard `Ⅱ` character format when positioned adjacent to word boundaries.

### 1.2. JP-to-EN Translations Table
The loader maps Japanese words to English prefixes and suffixes:
- **Common Replacements:** Lays out global mappings, e.g., `照会` → `Inquiry`, `編集` → `Edit`, `登録` → `Registration`, `一覧` → `List`.
- **String Precedence:** Long phrases are prioritized ahead of shorter substrings to avoid corrupted fragments (e.g., matching the multi-word block `作業依頼書` (Work Request) before splitting individual words).
- **Suffix Deduplication:** If duplicate names occur during batch runs, sequential identifiers are appended (e.g., `LoginView` → `Login2View`).

---

## 2. WPF MVVM Naming Guidelines

All generated C# code must conform to the following target formatting specifications:

| Architectural Component | Target Format Style | Example |
|---|---|---|
| XAML View | PascalCase + suffix `View` | `F004AfterEstimate2InquiryView` |
| MVVM ViewModel | C# PascalCase + suffix `ViewModel` | `F004AfterEstimate2InquiryViewModel` |
| Nested SubForm | C# PascalCase + suffix `SubFormView` | `AfterPaymentSubFormView` |
| Report Page / Preview | C# PascalCase + suffix `PrintView` | `QuoteInvoicePrintView` |
| Business Service | PascalCase, prefix `I` for interface | `IAuthService.cs` / `AuthService.cs` |
| Dapper Repository | PascalCase, prefix `I` for interface | `IAfterMainRepository.cs` |

*Prefix Rules:* Legacy codes (such as `F004`, `C000`) are explicitly retained at the start of names to facilitate cross-referencing and trace calls from `DoCmd.OpenForm` instructions.

---

## 3. Database & Exporter Output References

Run the automated mapping exporter script inside `backend/layer5/` to regenerate mapping catalogs:
```bash
python -X utf8 backend/layer5/agents/graphview/inputs/export_forms_layer1.py
```

### Generated Catalog Files:

| File Target | Content Description |
|---|---|
| `forms/listFormJp.json` | Catalog of all processed Form keys with metadata. |
| `forms/listFormJpToEn.json` | Suggested C# XAML View and ViewModel mappings. |
| `queries/listQueryJpToEn.json` | Access SQL query keys mapped to target Dapper repositories. |
| `macros/listMacroJpToEn.json`| Macro XML keys mapped to `NavigationService` workflows. |
| `events/listEventJpToEn.json` | Access UI control triggers mapped to target WPF async event handlers. |
