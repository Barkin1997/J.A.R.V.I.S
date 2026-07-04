Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.Run chr(34) & folder & "\Starte Jarvis KI.bat" & chr(34), 1, False
