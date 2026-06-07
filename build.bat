@echo off
echo Building Master Stego Suite Executable...

REM Make sure pyinstaller is installed: pip install pyinstaller
call pyinstaller ^
    --name MasterStegoSuite ^
    --noconsole ^
    --onedir ^
    --collect-all customtkinter ^
    --collect-all tkinterdnd2 ^
    --hidden-import PIL._tkinter_finder ^
    src\main.py

echo Build Complete! Check the dist\ folder.
pause
