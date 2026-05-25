Attribute VB_Name = "Mod_TestModule"
Option Compare Database
Option Explicit

Public Const MY_CONST = 100
Public GlobalVar As String

Public Sub SayHello()
    MsgBox "Hello from VBA!"
    Call OtherSub
End Sub

Private Function AddNumbers(ByVal a As Integer, ByVal b As Integer) As Integer
    AddNumbers = a + b
End Function
