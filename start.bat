@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python was not found in your PATH.
    echo Please install Python 3.12 or newer and check 'Add python.exe to PATH'.
    pause
    exit /b 1
)

python server.py %*
if %ERRORLEVEL% neq 0 (
    echo.
    echo [Local Ops] Exited with error code %ERRORLEVEL%.
    pause
)
