@echo off
REM Cleanup script for Scheduled Task CMD Persistence BSI

echo Removing scheduled task GIMCTestBSI...

schtasks /Delete /TN "GIMCTestBSI" /F

if %ERRORLEVEL% EQU 0 (
    echo [SUCCESS] Scheduled task removed
) else (
    echo [ERROR] Failed to remove scheduled task
)

echo.
echo Removing payload script...

if exist "C:\Users\Public\gimc_payload.js" (
    del /F /Q "C:\Users\Public\gimc_payload.js"
    echo [SUCCESS] Payload script removed
) else (
    echo [INFO] Payload script not found
)

echo.
echo Cleanup complete.
pause
