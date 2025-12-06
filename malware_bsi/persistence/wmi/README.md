# WMI Event Subscription Persistence BSI

This directory contains a **Behavioral Subset Implementation (BSI)** derived from the **WMIGhost malware** that demonstrates **WMI Event Subscription persistence** (MITRE ATT&CK Technique T1546.003).

## Overview

The original WMIGhost malware used WMI Event Subscriptions for fileless persistence and C2 communication. This BSI isolates and demonstrates only the WMI persistence mechanism with a benign payload.

**Original Malware Hash:** `a3c930f64cbb4e0b259fe6e966ebfb27caa90b540d193e4627b6256962b28864`

## Files

- **`wmi_persistence_bsi.cpp`** - C++ implementation that creates WMI event subscriptions
- **`remove_wmi_persistence.js`** - Cleanup script to remove WMI artifacts
- **`WMIGhost_original.js`** - Commented original malware source (for reference only)

## Behavior

The BSI creates the following WMI objects for persistence:

1. **ActiveScriptEventConsumer** - Executes a JScript payload
2. **__IntervalTimerInstruction** - Timer trigger (every 10 seconds)
3. **__EventFilter** - Monitors for timer events
4. **__FilterToConsumerBinding** - Links the filter to the consumer

**Payload:** Writes timestamped log entries to `C:\Users\Public\gimc_wmi_test.log` every 10 seconds

> **Note:** The payload runs in Session 0 (non-interactive services session), so GUI applications won't appear on your desktop. The log file provides observable proof that the persistence mechanism is executing.

## ⚠️ Important: Disable Windows Defender for Testing

This BSI will trigger Windows Defender behavioral detection (`Behavior:Win32/SuspWmiExec.J!ibt`) because it uses the same WMI persistence technique as real malware. This is expected and validates that the BSI works correctly.

**Before testing, temporarily disable real-time protection:**

```powershell
# Run PowerShell as Administrator
Set-MpPreference -DisableRealtimeMonitoring $true

# Or add an exclusion for the test directory
Add-MpPreference -ExclusionPath "<YourWorkingDirectoryHere>"
```

**After testing, re-enable protection:**
```powershell
Set-MpPreference -DisableRealtimeMonitoring $false
```

> **Note:** The detection is caused by `scrcons.exe` (Script Event Consumer), a legitimate Windows process that executes ActiveScriptEventConsumer WMI subscriptions. This process is commonly abused by malware for persistence, which is why Defender flags it.

## Compilation

Requires Windows SDK and WMI libraries:

```cmd
cl wmi_persistence_bsi.cpp /EHsc /link wbemuuid.lib ole32.lib oleaut32.lib
```

Or using MinGW:
```cmd
g++ wmi_persistence_bsi.cpp -o wmi_persistence_bsi.exe -lole32 -loleaut32 -lwbemuuid
```

Or create a Visual Studio project with these linker dependencies:
- `wbemuuid.lib`
- `ole32.lib`
- `oleaut32.lib`

## Usage

### Install Persistence

**Must run as Administrator:**
```cmd
wmi_persistence_bsi.exe
```

The program will create WMI event subscriptions that persist across reboots.

### Verify Persistence is Working

**Method 1: Check the log file** (recommended)

The payload writes timestamps to a log file every 10 seconds:

```powershell
# View the log file
Get-Content C:\Users\Public\gimc_wmi_test.log

# Watch in real-time (Ctrl+C to stop)
Get-Content C:\Users\Public\gimc_wmi_test.log -Wait

# Expected output:
# [12/6/2025, 10:15:23 AM] WMI persistence triggered
# [12/6/2025, 10:15:33 AM] WMI persistence triggered
# [12/6/2025, 10:15:43 AM] WMI persistence triggered
```

**Method 2: Run the status check script**

```cmd
check_status.bat
```

This will show all WMI artifacts and whether `scrcons.exe` is running.

**Method 3: Query WMI manually**

```powershell
Get-WmiObject -Namespace root\subscription -Class __EventFilter | Where-Object {$_.Name -like "GIMCTestBSI*"}
Get-WmiObject -Namespace root\subscription -Class ActiveScriptEventConsumer | Where-Object {$_.Name -like "GIMCTestBSI*"}
Get-WmiObject -Namespace root\subscription -Class __FilterToConsumerBinding | Where-Object {$_.Filter -like "*GIMC*"}
```

### Verify Persistence Across Reboot

1. Reboot the system
2. Check the log file again - new entries should appear every 10 seconds
3. This confirms the WMI subscription survived the reboot

### Remove Persistence

Run the cleanup script:
```cmd
cscript remove_wmi_persistence.js
```

Or manually delete via PowerShell:
```powershell
Get-WmiObject -Namespace root\subscription -Class __FilterToConsumerBinding | 
    Where-Object {$_.Filter -like "*GIMCTestBSI*"} | Remove-WmiObject

Get-WmiObject -Namespace root\subscription -Class __EventFilter | 
    Where-Object {$_.Name -like "GIMCTestBSI*"} | Remove-WmiObject

Get-WmiObject -Namespace root\subscription -Class ActiveScriptEventConsumer | 
    Where-Object {$_.Name -like "GIMCTestBSI*"} | Remove-WmiObject

Get-WmiObject -Namespace root\subscription -Class __IntervalTimerInstruction | 
    Where-Object {$_.TimerID -like "GIMCTestBSI*"} | Remove-WmiObject
```

## Detection

### Event Logs
- Event ID 5861: WMI event consumer creation
- Event ID 19-21 (Sysmon): WMI event filter/consumer/binding activity

### WMI Monitoring
Monitor the `root\subscription` namespace for suspicious:
- ActiveScriptEventConsumer objects
- CommandLineEventConsumer objects
- __FilterToConsumerBinding objects

### Process Monitoring
- `scrcons.exe` (WMI Active Script Consumer host) executing unusual scripts

## Defensive Guidance

1. **Enable Sysmon** with WMI monitoring (Events 19-21)
2. **Audit WMI Activity** - Enable WMI-Activity/Operational log
3. **Regularly audit** `root\subscription` namespace for unauthorized consumers
4. **Restrict WMI permissions** for non-admin users
5. **Consider disabling** ActiveScriptEventConsumer if not needed

## MITRE ATT&CK Mapping

- **T1546.003** - Event Triggered Execution: Windows Management Instrumentation Event Subscription
- **T1047** - Windows Management Instrumentation

## References

- [WMIGhost Malware Analysis](https://blog.trendmicro.com/trendlabs-security-intelligence/wmighost-wmi-backdoor/)
- [MITRE ATT&CK T1546.003](https://attack.mitre.org/techniques/T1546/003/)
- [Microsoft: WMI Event Subscriptions](https://docs.microsoft.com/en-us/windows/win32/wmisdk/receiving-event-notifications-through-wmi)
