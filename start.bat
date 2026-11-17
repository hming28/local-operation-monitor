@echo off
chcp 65001 >NUL
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

where python >NUL 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [错误] 未检测到 Python，请先安装 Python 3.12 或更高版本并勾选 Add to PATH。
    pause
    exit /b 1
)

python server.py %*
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [总控台] 异常退出，错误码: %ERRORLEVEL%
    pause
)
