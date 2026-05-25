Version=0x0113
VersionRequired=0x0113
Begin Form
    Name ="F_TestForm"
    OnOpen ="Form_Open"
    Begin Section
        Begin TextBox
            Name ="txtUserName"
            ControlSource ="UserName"
            AfterUpdate ="[Event Procedure]"
        End
        Begin CommandButton
            Name ="btnSubmit"
            OnClick ="[Event Procedure]"
        End
    End
End
CodeBehindForm
' VBA Code Behind Form
Option Compare Database
Option Explicit

Private Sub Form_Open(Cancel As Integer)
    Me.txtUserName = "DefaultUser"
End Sub

Private Sub btnSubmit_Click()
    DoCmd.OpenForm "F_Success"
End Sub
