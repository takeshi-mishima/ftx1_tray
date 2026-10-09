@echo off
rem Build ftx1_tray.exe into dist\
rem Requires: pip install pyinstaller
cd /d %~dp0
py -m PyInstaller --onefile --noconsole --icon ftx1_tray.ico --name ftx1_tray ftx1_tray.py
if not exist dist\ftx1_tools.ini copy ftx1_tools.ini dist\
echo.
echo Done. See dist\
pause
