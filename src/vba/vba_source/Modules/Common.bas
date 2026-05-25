Attribute VB_Name = "Common"
Option Compare Database
Option Explicit

Public Sub Judge_Inst()
    MsgBox "Executing Judge_Inst", vbInformation
End Sub

Public Function IsLoginDevModeEnabled() As Boolean
    IsLoginDevModeEnabled = True
End Function

Public Sub AppendDevLoginLog(usr As String)
    Debug.Print "Dev login bypass for user: " & usr
End Sub

Public Sub SetEnabledState(st As Boolean)
    Debug.Print "SetEnabledState: " & st
End Sub

Public Sub SetWindowTop(hWnd As Long, topFlag As Boolean)
    Debug.Print "SetWindowTop: " & hWnd & " -> " & topFlag
End Sub

Public Sub SwitchShiftKey(st As Boolean)
    Debug.Print "SwitchShiftKey: " & st
End Sub

Public Sub SetAccWinStyle()
    Debug.Print "SetAccWinStyle executed"
End Sub

Public Sub MenuBarTrue()
    Debug.Print "MenuBarTrue executed"
End Sub

Public Sub MenuBarTrueFalse(st As Boolean)
    Debug.Print "MenuBarTrueFalse: " & st
End Sub

Public Sub StatusBar_True()
    Debug.Print "StatusBar_True executed"
End Sub

Public Sub タイマーを開く()
    Debug.Print "タイマーを開く executed"
End Sub
