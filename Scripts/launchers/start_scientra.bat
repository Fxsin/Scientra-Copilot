@echo off
REM ============================================================
REM  Scientra Copilot — One-Click Windows Launcher
REM
REM  Double-click this file or run from terminal:
REM    start_scientra.bat
REM ============================================================

cd /d "%~dp0"

echo.
echo   Scientra Copilot Launcher
echo   =========================
echo.

REM Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo   [ERROR] Python not found. Please install Python 3.11+.
    echo           https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Run the orchestrator
python Scripts\start_all.py %*

if %errorlevel% neq 0 (
    echo.
    echo   [FAILED] One or more services could not start.
    echo            Check logs\startup.log for details.
    pause
    exit /b 1
)

echo.
echo   Press any key to close this window...
pause >nul
