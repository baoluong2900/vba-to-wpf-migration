# vba_brain System Architecture Specification — VBA Migration to C# WPF & Oracle

This document outlines the standard architecture, mapping rules, and design choices for the modernized system migrated from legacy Microsoft Access VBA to C# WPF on Oracle Database.

---

## 1. Source to Target Mapping Overview

| Access/VBA Component | Count | Modern C# WPF Equivalent |
|---|---|---|
| `Forms/*.frm` (UI Forms) | 174 | `Views/*.xaml` + `ViewModels/*.cs` |
| `Forms/*.frm` (Report-as-Form) | 78 | `Views/Reports/*.xaml` (RDLC/Crystal Reports) |
| `Reports/*.frm` (Access Reports) | 19 | `Views/Reports/*.rdlc` (ReportViewer) |
| `Macros/*.mac` (Macro Workflows) | 68 | `Services/NavigationService.cs` + WPF Commands |
| `Modules/*.bas` (Common Modules) | 16 | `Application/Services/` + `Infrastructure/Helpers/` |
| `Queries/*.sql` (Access Queries) | 515 | `Infrastructure/Repositories/` (Dapper-based SQL) |
| Access Tables | ~50 | Oracle DB Schema (Entities/Migrations) |

---

## 2. Layered Architecture (Clean Architecture)

The modernized system strictly adheres to **Clean Architecture** principles to separate concerns, ensure testability, and decouple the application logic from external dependencies (UI, Databases, Frameworks).

```text
┌──────────────────────────────────────────────────────────┐
│              Presentation Layer (WPF)                     │
│   Views (XAML) ↔ ViewModels (MVVM) ↔ NavigationService  │
├──────────────────────────────────────────────────────────┤
│              Application Layer (Use Cases)                │
│   Services / DTOs / Validators / Mappers                  │
├──────────────────────────────────────────────────────────┤
│              Domain Layer (Core Business)                 │
│   Entities / Interfaces / Domain Exceptions               │
├──────────────────────────────────────────────────────────┤
│              Infrastructure Layer (External Details)       │
│   Dapper Repositories / OracleContext / Helpers / Logging │
│                    ↓                                      │
│              Oracle Database                              │
└──────────────────────────────────────────────────────────┘
```

---

## 3. C# WPF Solution Folder Structure

The project structure is organized into a single Visual Studio solution (`vba_brain.sln`) containing four distinct layers:

```text
vba_brain.sln
├── vba_brain.Domain/                          # Core Domain Layer (No external dependencies)
│   ├── Entities/
│   │   ├── AfterMainEntity.cs             ← Maps to C000_MAINⅡ table
│   │   ├── AfterRegistrationEntity.cs     ← Maps to C001 table
│   │   ├── PaymentEntity.cs               ← Maps to Payment table (入金)
│   │   ├── PrintDocumentEntity.cs         ← Maps to F004 print records
│   │   └── AnalyticsEntity.cs             ← Maps to F9xx data structure
│   ├── Interfaces/
│   │   ├── IAfterMainRepository.cs
│   │   ├── IPaymentRepository.cs
│   │   ├── IPrintRepository.cs
│   │   └── IAnalyticsRepository.cs
│   ├── Common/
│   │   ├── BaseEntity.cs
│   │   └── Enumerations/
│   │       ├── ServiceType.cs             ← Paid/Free/Warranty (有償/無償/瑕疵)
│   │       ├── PaymentFlag.cs             ← Payment status flag (入金フラグ)
│   │       └── RegistrationStatus.cs      ← Registration status (登録状況)
│   └── Exceptions/
│       └── DomainException.cs
│
├── vba_brain.Application/                     # Application Layer (Use Cases & Orchestration)
│   ├── DTOs/
│   │   ├── AfterMainDto.cs
│   │   ├── PaymentDto.cs
│   │   └── PrintRequestDto.cs
│   ├── Services/
│   │   ├── AfterMainService.cs            ← Main record retrieval & filtering
│   │   ├── AfterRegistrationService.cs    ← CRUD operations for C001
│   │   ├── AfterEditService.cs            ← CRUD operations for C003
│   │   ├── PaymentService.cs              ← Payment transactions
│   │   ├── PrintService.cs                ← Document printing orchestration
│   │   └── AnalyticsService.cs            ← F9xx statistical calculation
│   ├── Validators/
│   │   ├── AfterRegistrationValidator.cs
│   │   └── PaymentValidator.cs
│   └── Mappers/
│       └── vba_brainMappingProfile.cs
│
├── vba_brain.Infrastructure/                  # Infrastructure Layer (Database, Logging, File System)
│   ├── Persistence/
│   │   ├── OracleContext.cs               ← Database connection context (Oracle)
│   │   ├── Repositories/
│   │   │   ├── AfterMainRepository.cs     ← Implements Dapper SQL commands
│   │   │   ├── PaymentRepository.cs
│   │   │   ├── PrintRepository.cs
│   │   │   └── AnalyticsRepository.cs
│   │   └── UnitOfWork/
│   │       └── UnitOfWork.cs
│   ├── Queries/                           ← Ported SQL files from legacy Access
│   │   ├── MainQueries/                   ← C000_MAINⅡ SQL (50 files)
│   │   ├── PrintQueries/                  ← F004 SQL (~100 files)
│   │   └── AnalyticsQueries/              ← F9xx SQL (~50 files)
│   ├── Helpers/                           ← Ported utility functions from modules (.bas)
│   │   ├── CommonHelper.cs                ← Common.bas
│   │   ├── WindowHelper.cs                ← AppWinCenter.bas + SetWindowPos.bas
│   │   ├── GuidHelper.cs                  ← SetGUID.bas
│   │   ├── PhoneHelper.cs                 ← mdlSplitTelNum.bas
│   │   └── ClipboardHelper.cs             ← setEmtpyClipBoard.bas
│   ├── Logging/
│   │   └── SerilogConfiguration.cs
│   └── Migrations/                        ← Database schema migration scripts (DbUp for Oracle)
│       └── Scripts/
│           ├── V001__InitialSchema.sql
│           └── V002__SeedMasterData.sql
│
└── vba_brain.UI.WPF/                          # Presentation Layer (WPF Desktop App)
    ├── Views/
    │   ├── Auth/
    │   │   ├── LoginWindow.xaml           ← F_Login.frm
    │   │   └── LoginAAWindow.xaml         ← F_Login_AA.frm
    │   ├── Main/
    │   │   ├── MainWindow.xaml            ← C000_MAINⅡ.frm
    │   │   ├── MainPaymentView.xaml       ← C000_MAINⅡ_入金.frm
    │   │   └── MainUnpaidView.xaml        ← C000_MAINⅡ_未入金.frm
    │   ├── CRUD/
    │   │   ├── RegistrationWindow.xaml    ← C001_アフター登録Ⅱ.frm
    │   │   ├── InquiryWindow.xaml         ← C002_アフター照会Ⅱ.frm
    │   │   ├── EditWindow.xaml            ← C003_アフターMAINto編集Ⅱ.frm
    │   │   └── DuplicateWindow.xaml       ← C003_アフターMAINto複製Ⅱ.frm
    │   ├── Print/
    │   │   ├── PrintSettingsWindow.xaml   ← C004_印刷設定Ⅱ_MAIN.frm
    │   │   └── Reports/                   ← Report-as-Form views
    │   │       ├── QuoteReport.rdlc       ← Quote document layout
    │   │       ├── InvoiceReport.rdlc     ← Invoice document layout
    │   │       ├── DeliveryReport.rdlc    ← Delivery note layout
    │   │       └── BatchPrintView.xaml    ← Batch print interface
    │   ├── Analytics/
    │   │   ├── AdminHomeWindow.xaml       ← F000_管理ホーム.frm
    │   │   ├── CollectionStatsWindow.xaml ← F900_回収額実績.frm
    │   │   └── AggregateWindow.xaml       ← F911/F912/F921_集計.frm
    │   └── Shared/
    │       ├── SplashScreen.xaml          ← M300_Splash
    │       └── NavigationButtons.xaml     ← F021_NavigationButtons.frm
    ├── ViewModels/
    │   ├── Auth/
    │   │   └── LoginViewModel.cs
    │   ├── Main/
    │   │   ├── MainViewModel.cs
    │   │   ├── MainPaymentViewModel.cs
    │   │   └── MainUnpaidViewModel.cs
    │   ├── CRUD/
    │   │   ├── RegistrationViewModel.cs
    │   │   ├── InquiryViewModel.cs
    │   │   └── EditViewModel.cs
    │   ├── Print/
    │   │   └── PrintSettingsViewModel.cs
    │   └── Analytics/
    │       └── AnalyticsViewModel.cs
    ├── Services/
    │   ├── NavigationService.cs           ← Handles all page transitions (replacing *.mac)
    │   ├── DialogService.cs
    │   ├── PrintOrchestrationService.cs   ← Orchestrates RDLC report loading
    │   └── StartupService.cs              ← Performs startup tasks (replacing AutoExec.mac)
    ├── Converters/
    │   ├── BoolToVisibilityConverter.cs
    │   └── ServiceTypeColorConverter.cs
    ├── Resources/
    │   ├── Styles/
    │   │   └── AppStyles.xaml
    │   └── Themes/
    │       └── vba_brainTheme.xaml
    ├── App.xaml
    └── DependencyInjection.cs             ← Registers and binds components (Composition Root)
```

---

## 4. Navigation & Macro Modernization

VBA **Macros** in MS Access (which traditionally handle actions like `OpenForm`, `Close`, `Requery`, and `RunMacro`) are completely consolidated into the C# `NavigationService` and ViewModel `RelayCommand`s.

| Legacy VBA Macro (.mac) | WPF / C# Equivalent |
|---|---|
| `AutoExec.mac` (Form: F_Login) | `StartupService.Initialize()` → Navigates to `LoginWindow` |
| `ReturnToMain.mac` (C000_MAIN) | `NavigationService.NavigateTo<MainViewModel>()` |
| `Register.mac` (C001) | `RelayCommand: SaveAndReturnAsync()` in `RegistrationViewModel` |
| `EditSubmit.mac` (C003) | `RelayCommand: UpdateAndReturnAsync()` in `EditViewModel` |
| `OpenSplash.mac` (M300) | Native WPF `SplashScreen` integration |
| `ComboRequery.mac` (M5xx) | `ObservableCollection` data rebinding + async API call |
| `AllComboRequery.mac` (M511) | `MainViewModel.RefreshFiltersCommand` (WPF RelayCommand) |
| Connection String Config | `appsettings.json` → `ConnectionStrings:Oracle` mapping |

---

## 5. VBA Modules Modernization

Legacy `.bas` module files containing general application utilities, Windows API declarations, or string manipulation logic are refactored into deterministic C# helper classes.

| VBA Module (.bas) | WPF / C# Helper Class |
|---|---|
| `Common.bas` | `vba_brain.Infrastructure/Helpers/CommonHelper.cs` |
| `AppWinCenter.bas` | `WindowHelper.CenterWindow(Window window)` |
| `SetWindowPos.bas` | Native Windows interop inside `WindowHelper.cs` |
| `SetGUID.bas` | Native `System.Guid.NewGuid()` calls inside `GuidHelper.cs` |
| `mdlSplitTelNum.bas` | `PhoneHelper.SplitTelephoneNumber(string phone)` |
| `setEmptyClipBoard.bas` | `ClipboardHelper.ClearSystemClipboard()` |
