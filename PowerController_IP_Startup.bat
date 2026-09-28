@echo off
setlocal

rem ================================================================
rem Edit PROJECTOR_IP below before copying this file to shell:startup.
rem PJLink default port is 4352.
rem ================================================================
set "PROJECTOR_IP=192.168.0.100"
set "PROJECTOR_PORT=4352"
set "PROJECT_DIR=C:\PowerController"

if not exist "%PROJECT_DIR%\.venv\Scripts\python.exe" (
    echo Python environment not found: %PROJECT_DIR%\.venv
    exit /b 1
)

cd /d "%PROJECT_DIR%"
"%PROJECT_DIR%\.venv\Scripts\python.exe" "%PROJECT_DIR%\main_2.py" ^
    --ip "%PROJECTOR_IP%" --port "%PROJECTOR_PORT%" --on ^
    --retries 5 --delay 5 >> "%PROJECT_DIR%\startup_power.log" 2>&1

endlocal
