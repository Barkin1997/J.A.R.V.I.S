Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
ScriptPath = FSO.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = ScriptPath
WshShell.Run Chr(34) & ScriptPath & "\start_jarvis.bat" & Chr(34), 0, False
