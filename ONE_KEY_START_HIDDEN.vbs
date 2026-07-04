Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
ScriptPath = FSO.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = ScriptPath
WshShell.Run Chr(34) & ScriptPath & "\START_ALLES.bat" & Chr(34), 1, False
