@echo off
echo ========================================
echo WMI Event Subscription Status Check
echo ========================================
echo.

echo [1] Checking for EventFilter...
powershell -Command "Get-WmiObject -Namespace root\subscription -Class __EventFilter | Where-Object {$_.Name -like '*GIMC*'} | Format-List Name, Query"
echo.

echo [2] Checking for EventConsumer...
powershell -Command "Get-WmiObject -Namespace root\subscription -Class ActiveScriptEventConsumer | Where-Object {$_.Name -like '*GIMC*'} | Format-List Name, ScriptingEngine, ScriptText"
echo.

echo [3] Checking for FilterToConsumerBinding...
powershell -Command "Get-WmiObject -Namespace root\subscription -Class __FilterToConsumerBinding | Where-Object {$_.Filter -like '*GIMC*'} | Format-List Filter, Consumer"
echo.

echo [4] Checking for TimerInstruction...
powershell -Command "Get-WmiObject -Namespace root\subscription -Class __IntervalTimerInstruction | Where-Object {$_.TimerID -like '*GIMC*'} | Format-List TimerID, IntervalBetweenEvents"
echo.

echo [5] Checking if scrcons.exe is running...
tasklist /FI "IMAGENAME eq scrcons.exe" 2>nul | find /I "scrcons.exe" >nul
if %ERRORLEVEL% EQU 0 (
    echo [FOUND] scrcons.exe is running
    tasklist /FI "IMAGENAME eq scrcons.exe"
) else (
    echo [NOT FOUND] scrcons.exe is not running - persistence may not be active
)
echo.

echo [6] Checking calculator processes...
tasklist /FI "IMAGENAME eq win32calc.exe" 2>nul | find /I "win32calc.exe" >nul
if %ERRORLEVEL% EQU 0 (
    echo [FOUND] Calculator processes:
    tasklist /FI "IMAGENAME eq win32calc.exe"
) else (
    echo [NOT FOUND] No calculator processes found yet
)
echo.

echo ========================================
echo If no artifacts found, the installation may have failed.
echo Check that you ran wmi_persistence_bsi.exe as Administrator.
echo.
pause
