Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
WshShell.CurrentDirectory = FSO.GetParentFolderName(WScript.ScriptFullName)
WshShell.Run chr(34) & WshShell.CurrentDirectory & "\START_JARVIS_ALLES_AUTOMATISCH.bat" & chr(34), 1, False
