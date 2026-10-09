@echo off
rem Build ftx1_tray.exe into dist\
rem Requires: py -m pip install pyinstaller
rem Uses "py -m PyInstaller" (or "python -m PyInstaller") so that the
rem PyInstaller command does not need to be on PATH.
cd /d %~dp0
where py >nul 2>nul
if %errorlevel%==0 (set PY=py) else (set PY=python)
%PY% -m PyInstaller --onefile --noconsole --icon ftx1_tray.ico --name ftx1_tray ftx1_tray.py
if errorlevel 1 (
  echo.
  echo Build failed.
  pause
  exit /b 1
)
if not exist dist\ftx1_tools.ini copy ftx1_tools.ini dist\
echo.
echo Done. See dist\
pause
