@echo off
setlocal

rem ================================================================
rem Add or remove projector IP addresses in PROJECTOR_IPS.
rem Each projector is processed sequentially. A failed projector does
rem not prevent the remaining projectors from being processed.
rem PJLink default port is 4352.
rem ================================================================
set "PROJECTOR_IPS=192.168.0.141 192.168.0.142"
set "PROJECTOR_PORT=4352"
set "PROJECT_DIR=C:\PowerController"
set "LOG_FILE=%PROJECT_DIR%\startup_power_multi.log"

if not exist "%PROJECT_DIR%\.venv\Scripts\python.exe" (
    echo Python environment not found: %PROJECT_DIR%\.venv
    exit /b 1
)

if not exist "%PROJECT_DIR%\main_2.py" (
    echo Power controller not found: %PROJECT_DIR%\main_2.py
    exit /b 1
)

cd /d "%PROJECT_DIR%"
set /a FAILURES=0

>> "%LOG_FILE%" echo ================================================================
>> "%LOG_FILE%" echo [%date% %time%] Starting projector power-on sequence

for %%I in (%PROJECTOR_IPS%) do (
    >> "%LOG_FILE%" echo [%date% %time%] Processing %%I
    "%PROJECT_DIR%\.venv\Scripts\python.exe" "%PROJECT_DIR%\main_2.py" ^
        --ip "%%I" --port "%PROJECTOR_PORT%" --on ^
        --retries 5 --delay 5 >> "%LOG_FILE%" 2>&1

    if errorlevel 1 (
        >> "%LOG_FILE%" echo [%date% %time%] Failed to power on %%I
        set /a FAILURES+=1
    ) else (
        >> "%LOG_FILE%" echo [%date% %time%] Completed %%I
    )
)

>> "%LOG_FILE%" echo [%date% %time%] Sequence finished

if not "%FAILURES%"=="0" exit /b 1
exit /b 0
