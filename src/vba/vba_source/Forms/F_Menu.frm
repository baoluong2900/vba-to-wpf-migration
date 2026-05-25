Version=0x0113
VersionRequired=0x0113
Begin Form
    Name ="F_Menu"
    Caption ="Hệ thống quản lý kho - Menu chính"
    OnOpen ="Form_Open"
    Begin Section
        Begin CommandButton
            Name ="btnProductList"
            Caption ="Danh sách sản phẩm"
            OnClick ="[Event Procedure]"
        End
        Begin CommandButton
            Name ="btnOrderEntry"
            Caption ="Nhập đơn hàng"
            OnClick ="[Event Procedure]"
        End
        Begin CommandButton
            Name ="btnExit"
            Caption ="Thoát hệ thống"
            OnClick ="Macro.M_CloseSystem"
        End
    End
End
CodeBehindForm
Option Compare Database
Option Explicit

Private Sub Form_Open(Cancel As Integer)
    MsgBox "Chào mừng đến với Hệ thống quản lý kho!", vbInformation
End Sub

Private Sub btnProductList_Click()
    DoCmd.OpenForm "F_ProductList", acNormal
End Sub

Private Sub btnOrderEntry_Click()
    DoCmd.OpenForm "F_OrderEntry", acNormal
End Sub
