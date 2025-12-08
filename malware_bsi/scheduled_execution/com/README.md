# Scheduled Task COM API Persistence BSI

This directory contains a **Behavioral Subset Implementation (BSI)** derived from the **Carberp banking trojan** that demonstrates **scheduled task persistence using COM APIs** (MITRE ATT&CK Technique T1053.005).

## Overview

The original Carberp malware used Windows Task Scheduler COM APIs for persistence, bypassing command-line detection. This BSI isolates and demonstrates this technique with a benign payload.

**Original Malware:** Carberp Banking Trojan  
**Reference:** `Malware-Collection-master/Carberp Botnet/source/schtasks/schtasks.cpp`

## Files

- **`task_com_bsi.cpp`** - C++ implementation using Task Scheduler 2.0 COM API
- **`remove_task.js`** - Cleanup script to remove the scheduled task
- **`Makefile`** - Build configuration for MinGW
- **`Carberp_COM_API_implementation.md`** - Analysis of original Carberp implementation

## Behavior

The BSI uses Task Scheduler COM APIs to:

1. **Connect to ITaskService** - Establishes connection to Task Scheduler
2. **Create ITaskDefinition** - Defines new task
3. **Set ILogonTrigger** - Triggers at user logon (like original Carberp)
4. **Set IExecAction** - Executes JScript payload via wscript.exe
5. **Register Task** - Installs task with TASK_LOGON_INTERACTIVE_TOKEN
6. **Run Immediately** - Calls `IRegisteredTask::Run()` to execute without waiting for logon

**Payload:** Writes 10 timestamps to `C:\Users\Public\gimc_test.log` with 1-second delays between each write

**Key Implementation Detail:** Task Scheduler has a minimum interval of 1 minute for repetition patterns. To demonstrate faster execution, the BSI:
- Creates a logon-triggered task (runs at user logon)
- Immediately executes it via `Run()` method (COM equivalent of `schtasks /run`)
- Payload loops 10 times internally with 1-second delays

**Evasion Technique:** Uses COM APIs instead of `schtasks.exe` command-line, avoiding process creation monitoring.

## Compilation

Requires MinGW with Windows SDK:

```bash
make
```

Or manually:
```bash
g++ task_com_bsi.cpp -o task_com_bsi.exe -lole32 -loleaut32 -ltaskschd -lcomsupp -static
```

## Usage

### Install Persistence

**Must run as Administrator:**
```cmd
task_com_bsi.exe
```

The program:
1. Creates a scheduled task that triggers at user logon
2. Immediately runs the task via COM API (`IRegisteredTask::Run()`)
3. Payload writes 10 log entries with 1-second delays between each

The task will persist across reboots and execute at next logon.

### Verify Persistence is Working

**Method 1: Check the log file** (recommended)

```powershell
# View the log file (should show 10 entries from immediate execution)
Get-Content C:\Users\Public\gimc_test.log

# Expected output:
# [12/7/2025, 2:30:15 PM] Task executed (iteration 1/10)
# [12/7/2025, 2:30:16 PM] Task executed (iteration 2/10)
# [12/7/2025, 2:30:17 PM] Task executed (iteration 3/10)
# ... (continues to 10/10)
```

**Method 2: Run the task manually again**

```cmd
schtasks /Run /TN "GIMCTestBSI"
```

This will add 10 more entries to the log file.

```powershell
# Check if task exists
Get-ScheduledTask -TaskName "GIMCTestBSI"

# View task details
Get-ScheduledTaskInfo -TaskName "GIMCTestBSI"

# Or use schtasks
schtasks /Query /TN "GIMCTestBSI" /V /FO LIST
```

**Method 3: Query scheduled tasks**

```powershell
# Check if task exists
Get-ScheduledTask -TaskName "GIMCTestBSI"

# View task details
Get-ScheduledTaskInfo -TaskName "GIMCTestBSI"

# Or use schtasks
schtasks /Query /TN "GIMCTestBSI" /V /FO LIST
```

**Method 4: Run unit test**

```bash
make test
```

This runs the Python unit test that validates:
1. BSI installs successfully (exit code 0)
2. Log file is created
3. Log file updates at least 3 times in 10 seconds (achieved via immediate execution + looping)

### Verify Persistence Across Reboot

1. Reboot the system
2. Log back in (triggers the task)
3. Check the log file - 10 new entries should appear
4. Confirms task survived reboot and executes at logon

### Remove Persistence

**Option 1: Use cleanup script**
```cmd
cscript remove_task.js
```

**Option 2: Use schtasks command**
```cmd
schtasks /Delete /TN "GIMCTestBSI" /F
```

**Option 3: Use PowerShell**
```powershell
Unregister-ScheduledTask -TaskName "GIMCTestBSI" -Confirm:$false
```

**Option 4: Use Makefile**
```bash
make clean
```

## Detection

### Event Logs
- **Event ID 4698**: Scheduled task created
- **Event ID 4702**: Scheduled task updated
- **Event ID 106**: Task Scheduler - Task registered

### Process Monitoring
- `wscript.exe` executing JScript payload (runs once, writes 10 times)
- Creation of `gimc_payload.js` in %TEMP%
- Task execution completes in ~10 seconds (10 writes × 1 second delay)

### Task Scheduler Auditing
Monitor `\` folder for suspicious tasks:
```powershell
Get-ScheduledTask | Where-Object {$_.TaskPath -eq "\"}
```

### COM API Monitoring
- ETW (Event Tracing for Windows) can track COM object creation
- Monitor for `CLSID_TaskScheduler` instantiation
- Track `ITaskService::RegisterTaskDefinition` calls

## Defensive Guidance

1. **Enable Task Scheduler Operational Log**
   ```powershell
   wevtutil sl Microsoft-Windows-TaskScheduler/Operational /e:true
   ```

2. **Monitor for COM-based task creation**
   - Use Sysmon Event ID 1 (Process Creation) for wscript.exe
   - Track Task Scheduler events (4698, 106)

3. **Audit scheduled tasks regularly**
   ```powershell
   Get-ScheduledTask | Where-Object {$_.Author -notlike "*Microsoft*"}
   ```

4. **Restrict Task Scheduler permissions** for non-admin users

5. **Consider application whitelisting** to prevent unauthorized script execution

## MITRE ATT&CK Mapping

- **T1053.005** - Scheduled Task/Job: Scheduled Task (Primary)
- **T1106** - Native API (COM API usage)
- **T1059.007** - Command and Scripting Interpreter: JavaScript (JScript payload)

## Advantages of COM API over Command-Line

**Why Carberp used COM APIs instead of `schtasks.exe`:**

1. **No process creation** - Avoids spawning `schtasks.exe` child process
2. **No command-line logging** - Bypasses command-line auditing
3. **Harder to detect** - Requires ETW or API hooking to monitor
4. **Direct integration** - More reliable than parsing command output
5. **Professional appearance** - Better code quality than command injection

**Command-line equivalent (easily detected):**
```cmd
# Create task with logon trigger
schtasks /Create /TN "GIMCTestBSI" /TR "wscript.exe payload.js" /SC ONLOGON /F

# Run it immediately
schtasks /Run /TN "GIMCTestBSI"
```

This creates detectable command-line artifacts that COM APIs avoid.

## Testing with Unit Test

The BSI includes compatibility with the standard scheduled execution unit test:

```bash
python test_scheduled_execution.py task_com_bsi.exe C:\Users\Public\gimc_test.log
```

**Test validates:**
- ✓ Installation completes successfully
- ✓ Log file is created after installation
- ✓ Log file updates 3+ times in 10 seconds (payload writes 10 times with 1s delays)

**Note:** The BSI achieves the "recurring execution" requirement by immediately running the task and having the payload loop internally, rather than relying on Task Scheduler's repetition pattern (which has a 1-minute minimum interval).

## References

- [Carberp Banking Trojan Analysis](https://www.secureworks.com/research/carberp)
- [MITRE ATT&CK T1053.005](https://attack.mitre.org/techniques/T1053/005/)
- [Microsoft Task Scheduler COM API](https://docs.microsoft.com/en-us/windows/win32/taskschd/task-scheduler-start-page)
- [Task Scheduler Schema](https://docs.microsoft.com/en-us/windows/win32/taskschd/task-scheduler-schema)
