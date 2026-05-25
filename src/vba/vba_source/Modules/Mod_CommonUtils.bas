Attribute VB_Name = "Mod_CommonUtils"
Option Compare Database
Option Explicit

Public Function SafeString(val As Variant) As String
    If IsNull(val) Then
        SafeString = ""
    Else
        SafeString = Trim(CStr(val))
    End If
End Function

Public Sub LogError(errDesc As String, errNum As Long)
    Debug.Print "Error [" & errNum & "]: " & errDesc
    DoCmd.RunSQL "INSERT INTO TBL_ErrorLogs (Description, Number) VALUES ('" & errDesc & "', " & errNum & ")"
End Sub
