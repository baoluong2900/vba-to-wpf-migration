Version=0x0113
VersionRequired=0x0113
Begin Form
    Name ="F_Login"
    Caption ="Login"
    OnOpen ="Form_Open"
    OnLoad ="Form_Load"
    OnKeyDown ="Form_KeyDown"
    Begin Section
        Begin TextBox
            Name ="txtID"
            Locked =True
        End
        Begin Label
            Name ="lblLoginID"
            Caption ="Login ID:"
        End
        Begin TextBox
            Name ="txtPass"
            InputMask ="Password"
            AfterUpdate ="txtPass_AfterUpdate"
        End
        Begin Label
            Name ="lblPassword"
            Caption ="Password:"
        End
        Begin CommandButton
            Name ="cmdLogin"
            Caption ="Login"
            Visible =False
            OnClick ="cmdLogin_Click"
        End
        Begin CommandButton
            Name ="cmdClose"
            Caption ="Close"
            OnClick ="cmdClose_Click"
        End
        Begin Label
            Name ="lblStoreInfo"
            Caption ="New After Sales DB"
            OnDblClick ="lblStoreInfo_DblClick"
        End
        Begin Label
            Name ="lblMenuTrigger"
            Caption =" "
            OnClick ="macro.A_メニューバーを表示"
            OnDblClick ="macro.M300_Splash(M)を開く"
        End
        Begin Label
            Name ="lblAutoRetrieve"
            Caption ="*Auto-retrieved from PC"
        End
        Begin Label
            Name ="lblOpenPasswordTable"
            Caption =" "
            OnDblClick ="lblOpenPasswordTable_DblClick"
        End
        Begin Label
            Name ="lblEndProcess"
            Caption =" "
            OnDblClick ="lblEndProcess_DblClick"
        End
        Begin Label
            Name ="lblVersion"
            Caption ="Ver 2025/06/30"
        End
        Begin TextBox
            Name ="txtReleasedDate"
            ControlSource ="=DLookUp(\"コメント\",\"Access配信日\")"
        End
    End
End
CodeBehindForm
Option Compare Database
Option Explicit

Private Declare Sub Sleep Lib "kernel32" (ByVal ms As Long)

Private Sub Form_Load()
    Dim sLvlCmnt    As String
    Dim sCmnt       As String
    
    CloseWindow Application.hWndAccessApp
    
    Dim Ref As Reference
    For Each Ref In References
        If Ref.Name = "Excel" Then
            Application.References.Remove Ref
        End If
    Next Ref
    
    sLvlCmnt = Me.lblVersion.Caption
    sLvlCmnt = Mid(sLvlCmnt, InStr(sLvlCmnt, "/") + 1, 5)
    
    sCmnt = Replace(Replace(DLookup("コメント", "Access配信日"), "最新版は", ""), "ver", "")
    
    If sLvlCmnt <> sCmnt Then
        MsgBox "最新版ではありません！" & Chr(13) & "インストールします。", vbOKOnly + vbExclamation
        Call Judge_Inst
    End If
End Sub

Private Sub Form_Open(Cancel As Integer)
    SwitchShiftKey True
    Call SetEnabledState(False)
    DoCmd.SelectObject acForm, "", True
    DoCmd.RunCommand acCmdWindowHide
    DoCmd.ShowToolbar "Ribbon", acToolbarNo
    Application.CommandBars("Status Bar").Visible = False
    
    Dim i As Long
    For i = 1 To 3
    Next i
    
    On Error GoTo Err_Shori
    
    SetAccWinStyle
    MoveWindow Application.hWndAccessApp, 0, 0, 800, 400, True
    Call SetWindowTop(hWndAccessApp, True)
    DoCmd.RunCommand acCmdWindowHide
    Call SetWindowTop(hWndAccessApp, False)
    
    OpenClipboard (0&)
    EmptyClipboard
    CloseClipboard
    
    If OpenClipboard(ByVal 0&) Then
        Call EmptyClipboard
        Call CloseClipboard
    End If
    
    Dim WshNetworkObject As Object
    Set WshNetworkObject = CreateObject("WScript.Network")
    Dim limit As Date, cnt_d As Double
    
    With WshNetworkObject
        Dim UserName As String
        UserName = .UserName
        Me.txtID = UserName
        SendKeys "{TAB}"
        
        Dim myDO As DataObject
        Dim myStr As String
        myStr = Me.txtID
        Set myDO = New DataObject
        myDO.SetText myStr
        myDO.PutInClipboard
        
        If (.UserName = "00105687") Or _
           (.UserName = "00110772A") Or _
           (.UserName = "00109978A") Or _
           (.UserName = "00109212A") Or _
           (.UserName = "00106601A") Or _
           (.UserName = "00124937A") _
        Then
            SendKeys "^(v)"
            SendKeys "{ENTER}"
            SendKeys "^(v)"
            DoCmd.SetWarnings False
            DoCmd.OpenQuery "Q000_T_LoginUser", acViewNormal, acEdit
            SendKeys "{ENTER}"
            Exit Sub
        Else
            DoCmd.SetWarnings False
            DoCmd.OpenQuery "Q000_T_LoginUser", acViewNormal, acEdit
            SendKeys "{ENTER}"
            Exit Sub
        End If
    End With

Err_Shori:
    MsgBox "通信接続エラーです！！" & vbCrLf & vbCrLf & _
           "　　該当する【ログインID,PW】がありません！！" & vbCrLf & vbCrLf & _
           "　　設定が必要な為、本社施工管理担当者まで" & vbCrLf & vbCrLf & _
           "　　連絡してください！！　TEL 0766-20-2211", vbOKOnly + vbCritical
End Sub

Private Sub txtPass_AfterUpdate()
    Dim res
    Dim res1
    Dim isDevMode As Boolean
    On Error GoTo Err_Shori
    
    DoCmd.SelectObject acForm, , True
    DoCmd.Minimize
    
    ' Dev mode check
    isDevMode = IsLoginDevModeEnabled()
    
    If Not isDevMode Then
        If IsNull(Me.txtID) Then
            MsgBox "IDを入力してください"
            Me.txtID.SetFocus
            Exit Sub
        End If
        
        If IsNull(Me.txtPass) Then
            MsgBox "パスワードを入力してください"
            Me.txtPass.SetFocus
            Exit Sub
        End If
    End If
    
    DoCmd.SetWarnings False
    res1 = DLookup("管理者FLG", "T_ID_Pass", "ID='" & Replace(Me.txtID, "'", "''") & "'")
    
    If res1 = 0 And Not isDevMode Then
        MsgBox "　　施工管理ではありませんのでログインできません！！" & vbCrLf & vbCrLf & _
               "　　設定が必要な方は、本社施工管理担当者まで" & vbCrLf & vbCrLf & _
               "　　依頼してください！！　TEL 0766-20-2211"
        Exit Sub
    Else
        res = DLookup("Pass", "T_ID_Pass", "ID='" & Replace(Me.txtID, "'", "''") & "'")
        If IsNull(res) And Not isDevMode Then
            MsgBox "　　該当するID,PWがありません！！" & vbCrLf & vbCrLf & _
                   "　　設定が必要な為、本社施工管理担当者まで" & vbCrLf & vbCrLf & _
                   "　　連絡してください！！　TEL 0766-20-2211"
            Me.txtID.SetFocus
            Exit Sub
        End If
    End If
    
    If isDevMode Or res = Me.txtPass Then
        If isDevMode Then
            Call AppendDevLoginLog(Me.txtID)
        End If
        DoCmd.Close acForm, "F_Login"
        Dim RCount As Long
        RCount = DCount("*", "T023_地区CD設定")
        If RCount = 0 Then
            DoCmd.RunMacro "AutoExec_Restart"
            Exit Sub
        Else
            Call タイマーを開く
            DoCmd.RunMacro "AutoExec_A"
            Exit Sub
        End If
    Else
        MsgBox "　　パスワードが異なります！！" & vbCrLf & vbCrLf & _
               "　　わからない場合は、本社施工管理担当者まで" & vbCrLf & vbCrLf & _
               "　　連絡してください！！　TEL 0766-20-2211"
        Me.txtPass.SetFocus
    End If
    Exit Sub

Err_Shori:
    MsgBox "通信接続エラーです！！" & vbCrLf & vbCrLf & _
           "　　該当する【ログインID,PW】がありません！！" & vbCrLf & vbCrLf & _
           "　　設定が必要な為、本社施工管理担当者まで" & vbCrLf & vbCrLf & _
           "　　連絡してください！！　TEL 0766-20-2211", vbOKOnly + vbCritical
End Sub

Private Sub lblOpenPasswordTable_DblClick(Cancel As Integer)
    DoCmd.Close acForm, "F_Login"
    DoCmd.Close acForm, "F_ユーザー追加", acSaveNo
    DoCmd.Close acForm, "F_ユーザー追加_A", acSaveNo
    DoCmd.SetWarnings False
    MenuBarTrue
    DoCmd.SelectObject acForm, "", True
    
    Dim i As Long
    i = SysCmd(acSysCmdAccessVer)
    If i = 11 Then
        Call MenuBarTrueFalse(True)
    Else
        DoCmd.ShowToolbar "Ribbon", acToolbarYes
    End If
    
    DoCmd.SetWarnings False
    StatusBar_True
    DoCmd.OpenQuery "Q000_T_ID_PASS", acViewNormal, acEdit
    DoCmd.Maximize
    DoCmd.RunCommand acCmdAppMaximize
    DoCmd.Maximize
End Sub

Private Sub lblEndProcess_DblClick(Cancel As Integer)
    Dim objShell As Object
    Dim objExec As Object
    Set objShell = CreateObject("WScript.Shell")
    Set objExec = objShell.Exec("taskkill.exe /F /IM wmplayer.exe")
End Sub

Private Sub cmdClose_Click()
    DoCmd.Quit acQuitPrompt
End Sub

Public Function Login_Log_Append()
    Dim Out_File_Fno As Integer
    Out_File_Fno = FreeFile
    Open "D:\Log\Login.txt" For Append As #Out_File_Fno
    Close Out_File_Fno
End Function

Private Sub Form_KeyDown(KeyCode As Integer, Shift As Integer)
    Select Case KeyCode
        Case vbKeyF11
            KeyCode = 0
            MsgBox "ファンクション【F11】キーは無効に設定されてます！！"
        Case vbKeyF12
            KeyCode = 0
            MsgBox "ファンクション【F12】キーは無効に設定されてます！！"
        Case Else
    End Select
End Sub
