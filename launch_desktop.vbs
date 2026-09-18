' Silent Windows Launcher for Sage AI
' Launches Sage AI Desktop without showing any console or command prompt window.
Set objFSO = CreateObject("Scripting.FileSystemObject")
Set objShell = CreateObject("WScript.Shell")

strScriptDir = objFSO.GetParentFolderName(WScript.ScriptFullName)
strVenvPythonw = strScriptDir & "\.venv\Scripts\pythonw.exe"
strMainPy = strScriptDir & "\main.py"

If objFSO.FileExists(strVenvPythonw) Then
    objShell.CurrentDirectory = strScriptDir
    objShell.Run """" & strVenvPythonw & """ """ & strMainPy & """", 0, False
Else
    objShell.CurrentDirectory = strScriptDir
    objShell.Run "pythonw """ & strMainPy & """", 0, False
End If
