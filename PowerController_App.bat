@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    where uv >nul 2>nul
    if errorlevel 1 (
        echo [ERROR] uv is not installed or is not available in PATH.
        echo Install uv, then run this file again.
        pause
        exit /b 1
    )

    echo Setting up the Python environment...
    uv sync
    if errorlevel 1 (
        echo [ERROR] Failed to install the required packages.
        pause
        exit /b 1
    )
)

".venv\Scripts\python.exe" main.py
if errorlevel 1 (
    echo.
    echo [ERROR] The application exited with an error.
    pause
    exit /b 1
)

endlocal
