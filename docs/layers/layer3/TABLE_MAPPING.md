# Layer 3 — Database Table Classification Mapping

This document categorizes the database tables from the legacy MS Access application based on their structural role and operational classification in the modernized target schema.

---

## 1. Core Transaction Tables (Main Tables)

These tables store primary transactional records and form the core domain entities:

| Access Table Name | Modernized Entity Class | Description |
|---|---|---|
| `T_ID_PASS` | `IdPassEntity.cs` | User authorization credentials |
| `WSTEM_TBLビルＡＭ受付` | `AmReceiptEntity.cs` | Building AM receipt registry |
| `WSTEM_TBLビルＡＭ報告` | `AmReportEntity.cs` | Building AM reporting transactions |
| `WSTEM_TBLビルＡＭ報告処置`| `AmTreatmentEntity.cs` | Building AM report treatment status |
| `WSTEM_TBLビルＡＭ報告点検`| `AmInspectionEntity.cs` | Building AM inspection details |
| `WSTEM_TBLビルＡＭ報告不具合`| `AmDefectEntity.cs` | Building AM defect register |
| `WSTEM_TBLビルアフター回収` | `AfterCollectionEntity.cs`| Building After-service collection ledger |
| `WSTEM_TBLビルサブ明細` | `SubDetailEntity.cs` | Sub-detail ledger records |

---

## 2. Temporary & Processing Tables (Operational Objects)

These tables are utilized during analytical runs, file generation pipelines, or temporary data aggregation steps:

| Access Table Name | Operational Scope | Modernized Handling |
|---|---|---|
| `C000_MAINⅡ 宛先テーブル` | Document recipient list | Handled via in-memory DTO collections |
| `C000_MAINⅡ 差出人テーブル` | Document sender list | Handled via in-memory DTO collections |
| `T000_MAINⅡ ONOF-1選択抽出_テーブル作成` | Invoice date checking buffer | Refactored into a temporary DB view |
| `T000_MAINⅡ ONOF-1選択抽出_請求書提出日チェック` | Billing target validation | Refactored into a temporary DB view |
| `T000_MAINⅡ ONOF-1選択抽出_請求先チェック` | Billing target validation | Refactored into a temporary DB view |
| `T000_MAINⅡ 登録番号抽出 テーブル` | Registration number filter | Built as a dynamic SQL query |

---

## 3. Local Tables (Client-Side Backups)

These tables store local device parameters or temporary client-side data backups:

*   `T_ID_PASS_local`: Local offline credential repository.
*   `WSTEM_TBLビルアフター回収_localbak`: Client-side backup ledger for after-service collections.

---

## 4. Analytical Data Store & UI State Buffers

These tables act as session state buffers, cache repositories, or intermediate aggregation sheets:

*   `T022_03地方 - update`: Regional parameter updater.
*   `T022_05地方 - update`: Regional parameter updater.
*   `T022_都道府県抽出用`: Prefecture-level file export buffer.
*   `T024_登録状況設定`: Target CRUD registration settings.
*   `T024_登録状況設定_元`: Static master database source backup.
*   `T026_未登録表示設定`: Registry state configurations.
*   `T027_入金情報一括入力テーブル`: Batch payment input transaction buffer.
*   `T031_登録状況_表示設定`: Registration visibility configuration.
*   `T_LoginUser`: Active user session identity mapping.
*   `T_インストール日`: Application installation timestamp cache.
*   `T911_MAINⅡ_集計_額先月` to `Ｔ912_MAINⅡ_集計_額累計_担当者`: Financial analytical data structures for monthly, cumulative, and representative aggregates.

---

## 5. Master Configurations & Rules (Master/Config)

These tables store static parameters, codes, drop-down menu items, and business rule configurations:

*   `JM_001_実績見出用`: Operational header configurations.
*   `JM_002_MONOS年月M`: Fiscal year/month period master.
*   `JM_003_営業所⇒母店`: Sales office to main branch mapping.
*   `M_回収管理リスト`: Collection management master catalog.
*   `M_請求` & `M_請求区分詳細`: Billing type classifications and definitions.
*   `M_単位`: Standard measurement unit list.
*   `M_担当者コード`: Representative operator assignment keys.
*   `M_提出元`: Submission channel references.
*   `M_店所` & `M_入金` & `M_流れ`: Branch offices, payment schemes, and workflow sequences.
*   `S01_集計マスター`: Global aggregation configurations.
*   `T011_期` & `T011_期設定`: Fiscal period timeline settings.
*   `T023_地区CD設定`: District postal and code configurations.
*   `TM_拠点`: Operational base location list.
