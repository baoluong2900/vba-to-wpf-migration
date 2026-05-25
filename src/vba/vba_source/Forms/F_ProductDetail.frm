Version=0x0113
VersionRequired=0x0113
Begin Form
    Name ="F_ProductDetail"
    Caption ="Chi tiết sản phẩm"
    RecordSource ="TBL_Products"
    BeforeUpdate ="Form_BeforeUpdate"
    Begin Section
        Begin TextBox
            Name ="txtProductID"
            ControlSource ="ProductID"
            Locked = True
        End
        Begin TextBox
            Name ="txtProductName"
            ControlSource ="ProductName"
            Required = True
        End
        Begin ComboBox
            Name ="cboSupplier"
            ControlSource ="SupplierID"
            RowSource ="SELECT SupplierID, SupplierName FROM TBL_Suppliers;"
            BoundColumn = 1
            ColumnCount = 2
        End
        Begin OptionGroup
            Name ="optStatus"
            ControlSource ="ProductStatus"
            Begin OptionButton
                Name ="optActive"
                OptionValue = 1
            End
            Begin OptionButton
                Name ="optInactive"
                OptionValue = 2
            End
        End
        Begin CheckBox
            Name ="chkDiscontinued"
            ControlSource ="Discontinued"
        End
        Begin CommandButton
            Name ="btnSave"
            OnClick ="[Event Procedure]"
        End
        Begin CommandButton
            Name ="btnDelete"
            OnClick ="[Event Procedure]"
        End
    End
End
CodeBehindForm
Option Compare Database
Option Explicit

Private Sub Form_BeforeUpdate(Cancel As Integer)
    If IsNull(Me.txtProductName) Or Me.txtProductName = "" Then
        MsgBox "Tên sản phẩm không được để trống!", vbCritical
        Cancel = True
    End If
End Sub

Private Sub btnSave_Click()
    DoCmd.RunCommand acCmdSaveRecord
    MsgBox "Lưu thành công!", vbInformation
    DoCmd.Close acForm, "F_ProductDetail"
End Sub

Private Sub btnDelete_Click()
    If MsgBox("Bạn có chắc chắn muốn xóa sản phẩm này?", vbYesNo + vbQuestion) = vbYes Then
        DoCmd.RunSQL "DELETE FROM TBL_Products WHERE ProductID = " & Me.txtProductID
        DoCmd.Close acForm, "F_ProductDetail"
    End If
End Sub
