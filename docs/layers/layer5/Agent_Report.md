# 📊 Agent Report — Gen Report / Print File

> **Mục đích:** Đọc BD layout + MongoDB form (印刷) → sinh WPF Print Preview hoặc PDF  
> **Status:** ⚠️ **OPEN CHALLENGE** — cần prototype trước  
> **Ref:** [AI_Agent_Workflow.md](./AI_Agent_Workflow.md) — Slide 10c

---

## Input / Output

| | Nguồn | Chi tiết |
|---|---|---|
| **Input 1** | BD JSON `sheet_3_screen_edit` | Control list: buttons, labels |
| **Input 2** | MongoDB `forms[]` (印刷 forms) | items[]: CommandButton, Label, section, properties |
| **Input 3** | DD JSON `sheet_3_detail_specs` | Event logic (PDF出力_Click, 印刷する_Click) |
| **Input 4** | DD JSON `sheet_4_sel_query_templates` | Data source query cho report |
| **Output 1** | `Views/Reports/{Name}PrintWindow.xaml` | Print preview UI |
| **Output 2** | `ViewModels/{Name}PrintViewModel.cs` | Print logic |

---

## Layer5 Folder / Files

```
backend/layer5/
├── agents/
│   └── agent_report.py               ← Main agent logic
├── core/
│   └── prompts/
│       └── agent_report.md           ← System prompt
└── codegen/
    └── templates/
        └── PrintWindow.xaml.j2       ← Print preview template
```

---

## Ví dụ Input JSON (AM依頼_印刷_PDF)

> Source: MongoDB `forms` collection → `AM依頼_印刷_PDF`  
> Source: BD JSON / DD JSON tương ứng

```json
{
  "form_name": "AM依頼_印刷_PDF",

  "form_properties": {
    "popup": true,
    "defaultview": 0,
    "width": 2985,
    "left": 5190, "top": 705
  },

  "items": [
    {
      "name": "詳細",
      "type": "section",
      "properties": { "height": 1065 }
    },
    {
      "name": "PDF出力",
      "type": "CommandButton",
      "properties": {
        "left": 90, "top": 480,
        "width": 1020, "height": 360,
        "caption": "PDF出力"
      },
      "event": { "onclick": "PDF出力_Click" }
    },
    {
      "name": "印刷する",
      "type": "CommandButton",
      "properties": {
        "left": 1290, "top": 480,
        "width": 705, "height": 397,
        "caption": "印刷"
      },
      "event": { "onclick": "印刷する_Click" }
    },
    {
      "name": "閉じる",
      "type": "CommandButton",
      "properties": {
        "left": 2145, "top": 480,
        "width": 795, "height": 397,
        "caption": "閉じる"
      },
      "event": { "onclick": "閉じる_Click" }
    },
    {
      "name": "ラベル15",
      "type": "Label",
      "properties": {
        "width": 1875, "height": 270,
        "caption": "【出力用メニュー】",
        "fontweight": 700
      }
    }
  ]
}
```

---

## Control Mapping (Access Report → WPF)

| Access Control | WPF Control | Binding |
|---|---|---|
| `CommandButton` (PDF出力) | `<Button>` | `Command="{Binding ExportPdfCommand}"` |
| `CommandButton` (印刷) | `<Button>` | `Command="{Binding PrintCommand}"` |
| `CommandButton` (閉じる) | `<Button>` | `Command="{Binding CloseCommand}"` |
| `Label` | `<Label>` | `Content="【出力用メニュー】"` |
| `Section` (詳細) | `<DocumentViewer>` | Print preview area |

---

## Ví dụ Output: AMIraiPrintWindow.xaml

```xml
<Window x:Class="vba_brain.Views.Reports.AMIraiPrintWindow"
        xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="AM依頼 印刷" Width="400" Height="300"
        WindowStyle="ToolWindow" ResizeMode="NoResize"
        WindowStartupLocation="CenterOwner">

  <Grid Margin="10">
    <Grid.RowDefinitions>
      <RowDefinition Height="Auto"/>
      <RowDefinition Height="*"/>
      <RowDefinition Height="Auto"/>
    </Grid.RowDefinitions>

    <!-- Header -->
    <Label Grid.Row="0" Content="【出力用メニュー】"
           FontWeight="Bold" FontSize="14"/>

    <!-- Preview Area -->
    <DocumentViewer Grid.Row="1" x:Name="docViewer"
                    Document="{Binding PrintDocument}"/>

    <!-- Buttons -->
    <StackPanel Grid.Row="2" Orientation="Horizontal"
                HorizontalAlignment="Center" Margin="0,10">
      <Button Content="PDF出力" Width="100" Margin="5"
              Command="{Binding ExportPdfCommand}"/>
      <Button Content="印刷" Width="80" Margin="5"
              Command="{Binding PrintCommand}"/>
      <Button Content="閉じる" Width="80" Margin="5"
              Command="{Binding CloseCommand}"/>
    </StackPanel>
  </Grid>
</Window>
```

---

## Hướng giải quyết (Output format)

| Hướng | Công nghệ | Note |
|:---:|---|---|
| A | RDLC Reports (.NET) | Microsoft native, cũ |
| **B** | **FlowDocument + DocumentViewer** | **Native WPF, recommended** |
| C | HTML → PDF (Puppeteer) | Modern, flexible |

> **Action:** Prototype 1 report (AM依頼_印刷_PDF) → FlowDocument approach → đánh giá → chốt solution.

---

## Verification

- [ ] Tất cả items từ MongoDB → control WPF tương ứng
- [ ] Events (PDF出力_Click, 印刷する_Click) → Commands
- [ ] Layout match: popup window, button positions
- [ ] Data source query → FlowDocument bindings
