' Pornește uvicorn fără fereastră de consolă.
' În shell:startup pune o SCURTĂTURĂ către acest fișier (nu copia VBS-ul în Startup — calea rămâne cea din proiect).
' Ținta scurtăturii: wscript.exe
' Argumente: //nologo "C:\Users\Asus\Desktop\yourcar.deploy\START_MULBERRY_SILENT.vbs"
Option Explicit
Dim sh, fso, root
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = root
sh.Run "cmd /c python -m uvicorn backend.main:app --host 127.0.0.1 --port 9000 --reload", 0, False
