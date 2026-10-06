@echo off
cd /d "%~dp0"

set "PY=python"
where py >nul 2>nul && set "PY=py -3"
%PY% --version >nul 2>nul
if errorlevel 1 (
  echo Python is not installed.
  echo Install it from https://www.python.org/downloads/ and check "Add python.exe to PATH".
  pause
  exit /b 1
)

rem Install packages only when something is missing (first run).
%PY% -c "import pptx, PIL, numpy, tifffile, png" >nul 2>nul
if errorlevel 1 (
  echo Installing required packages - first run only...
  %PY% -m pip install --disable-pip-version-check --no-warn-script-location --no-cache-dir -q -r requirements.txt
  if errorlevel 1 (
    echo Package install failed. Check your internet connection.
    pause
    exit /b 1
  )
)

%PY% pptx2tif_gui.py
if errorlevel 1 pause
