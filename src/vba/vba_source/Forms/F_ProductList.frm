Version=0x0113
VersionRequired=0x0113
Begin Form
    Name ="F_ProductList"
    Caption ="Danh sách sản phẩm"
    RecordSource ="Q_GetActiveProducts"
    Begin Section
        Begin TextBox
            Name ="txtSearch"
            AfterUpdate ="[Event Procedure]"
        End
        Begin ListBox
            Name ="lstCategory"
            RowSourceType ="Table/Query"
            RowSource ="SELECT ID, CategoryName FROM T_Category ORDER BY CategoryName;"
            AfterUpdate ="[Event Procedure]"
        End
        Begin Subform
            Name ="subProductGrid"
            SourceObject ="Table.TBL_Products"
        End
        Begin CommandButton
            Name ="btnOpenDetail"
            OnClick ="[Event Procedure]"
        End
    End
End
CodeBehindForm
Option Compare Database
Option Explicit

Private Sub txtSearch_AfterUpdate()
    Me.subProductGrid.Requery
End Sub

Private Sub lstCategory_AfterUpdate()
    Me.subProductGrid.Form.Filter = "CategoryID = " & Me.lstCategory
    Me.subProductGrid.Form.FilterOn = True
End Sub

Private Sub btnOpenDetail_Click()
    If IsNull(Me.subProductGrid.Form!ProductID) Then
        MsgBox "Hãy chọn một sản phẩm!", vbExclamation
        Exit Sub
    End If
    DoCmd.OpenForm "F_ProductDetail", acNormal, , "ProductID = " & Me.subProductGrid.Form!ProductID
End Sub
