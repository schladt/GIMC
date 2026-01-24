# Scheduled Task Command-Line Persistence BSI

This directory contains a **Behavioral Subset Implementation (BSI)** derived from **AsyncRAT**, **QuasarRAT**, and **RedLine Stealer** that demonstrates **scheduled task persistence using command-line schtasks.exe** (MITRE ATT&CK Technique T1053.005).

## Overview

Multiple malware families use the `schtasks.exe` command-line tool for persistence. This BSI demonstrates this technique with a benign payload, highlighting the differences between command-line and COM API approaches.

**Original Malware Families:**
- AsyncRAT - Privileged logon task with highest privilege level
- QuasarRAT - Fallback mechanism with registry persistence
- RedLine Stealer - Persistent daily task with continuous re-creation

**References:** See analysis markdown files in this directory

## Files

- **`task_cmd_bsi.c`** - C implementation using schtasks.exe command-line tool
- **`remove_task.bat`** - Cleanup script to remove the scheduled task
- **`Makefile`** - Build configuration for MinGW
- **`*.md`** - Analysis files of original malware implementations

## Behavior

The BSI uses command-line schtasks.exe to:

1. **Write Payload Script** - Creates batch file at `C:\Users\Public\gimc_payload.bat`
2. **Create Scheduled Task** - Executes `schtasks /create` with logon trigger
3. **Run Immediately** - Executes `schtasks /run` to start without waiting for logon

**Command executed:**
```cmd
schtasks /create /tn "GIMCTestBSI" /tr "C:\Users\Public\gimc_payload.bat" /sc onlogon /rl highest /f
schtasks /run /tn "GIMCTestBSI"
```

**Payload:** Batch script that writes 10 timestamps to `C:\Users\Public\gimc_test.log` with 1-second delays

**Key Difference from COM API:** This approach spawns `cmd.exe` and `schtasks.exe` processes, creating command-line artifacts that are easily detected by process monitoring and command-line logging.

## Compilation

Requires MinGW:

```bash
make
```

Or manually:
```bash
gcc -std=c11 -O2 -Wall task_cmd_bsi.c -o task_cmd_bsi.exe -static
```

## Usage

### Install Persistence

**Must run as Administrator:**
```cmd
task_cmd_bsi.exe
```

The program:
1. Creates batch payload at `C:\Users\Public\gimc_payload.bat`
2. Creates scheduled task that triggers at user logon with highest privileges
3. Immediately runs the task via `schtasks /run`
4. Payload writes 10 log entries with 1-second delays between each

The task will persist across reboots and execute at next logon.

### Verify Persistence is Working

**Method 1: Check the log file** (recommended)

```powershell
# View the log file (should show 10 entries from immediate execution)
Get-Content C:\Users\Public\gimc_test.log

# Expected output:
# [Sun 12/08/2025 14:30:15.23] Task executed (iteration 1/10)
# [Sun 12/08/2025 14:30:16.25] Task executed (iteration 2/10)
# [Sun 12/08/2025 14:30:17.27] Task executed (iteration 3/10)
# ... (continues to 10/10)
```

**Method 2: Run the task manually again**

```cmd
schtasks /Run /TN "GIMCTestBSI"
```

This will add 10 more entries to the log file.

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
remove_task.bat
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

### Command-Line Artifacts (PRIMARY DETECTION)
This is the **main difference** from the COM API approach - command-line execution creates easily detectable artifacts:

**Process Creation:**
- `cmd.exe` spawned by the BSI
- `schtasks.exe` spawned by cmd.exe
- Command-line logged: `schtasks /create /tn "GIMCTestBSI" /tr "C:\Users\Public\gimc_payload.bat" /sc onlogon /rl highest /f`

**Sysmon Event ID 1 (Process Creation):**
```
ParentImage: task_cmd_bsi.exe
Image: C:\Windows\System32\cmd.exe
CommandLine: cmd.exe /c schtasks /create /tn "GIMCTestBSI" ...
```

**Why This Matters:**
- EDR and SIEM solutions commonly monitor command-lines
- Easy to create detection rules for suspicious schtasks usage
- Process tree reveals parent-child relationship

### Event Logs
- **Event ID 4698**: Scheduled task created (Windows Security Log)
- **Event ID 106**: Task Scheduler - Task registered
- **Event ID 200**: Task Scheduler - Task executed

### File System Artifacts
- Payload script at `C:\Users\Public\gimc_payload.bat`
- Log file at `C:\Users\Public\gimc_test.log`
- Task definition XML in `C:\Windows\System32\Tasks\`

### Task Scheduler Monitoring
```powershell
# Find tasks in root directory
Get-ScheduledTask | Where-Object {$_.TaskPath -eq "\"}

# Find recently created tasks
Get-ScheduledTask | Where-Object {$_.Date -gt (Get-Date).AddHours(-1)}
```

## Defensive Guidance

1. **Monitor command-line execution** (PRIMARY DEFENSE)
   - Deploy Sysmon with command-line logging
   - Alert on `schtasks.exe /create` with suspicious parameters
   - Look for tasks with `/rl highest` or `/sc onlogon`

2. **Enable Task Scheduler Operational Log**
   ```powershell
   wevtutil sl Microsoft-Windows-TaskScheduler/Operational /e:true
   ```

3. **Command-line detection rules**
   ```
   ProcessName: schtasks.exe
   CommandLine contains: /create AND (/rl highest OR /sc onlogon)
   ParentProcess NOT: (legitimate admin tools)
   ```

4. **Audit scheduled tasks regularly**
   ```powershell
   Get-ScheduledTask | Where-Object {$_.Author -notlike "*Microsoft*"}
   ```

5. **Restrict Task Scheduler permissions** for non-admin users

6. **Application whitelisting** to prevent unauthorized executables

## MITRE ATT&CK Mapping

- **T1053.005** - Scheduled Task/Job: Scheduled Task (Primary)
- **T1059.003** - Command and Scripting Interpreter: Windows Command Shell (cmd.exe)
- **T1059.001** - Command and Scripting Interpreter: PowerShell (if using PS version)
- **T1106** - Native API (CreateProcess for command execution)
- **T1548.002** - Abuse Elevation Control Mechanism: Bypass User Account Control (/rl highest)

## Testing with Unit Test

The BSI includes compatibility with the standard scheduled execution unit test:

```bash
python test_scheduled_execution.py task_cmd_bsi.exe C:\Users\Public\gimc_test.log
```

**Test validates:**
- ✓ Installation completes successfully
- ✓ Log file is created after installation
- ✓ Log file updates 3+ times in 10 seconds (payload writes 10 times with 1s delays)

**Note:** The BSI achieves the "recurring execution" requirement by immediately running the task and having the payload loop internally, rather than relying on Task Scheduler's repetition pattern (which has a 1-minute minimum interval).

## References

- [AsyncRAT Scheduled Task Implementation](AsyncRAT_privileged_onlogon.md)
- [QuasarRAT Fallback Mechanism](QuasarRAT_fallback_mechanism.md)
- [RedLine Stealer Persistent Task](RedlineStealer_persistent_daily_task.md)
- [MITRE ATT&CK T1053.005](https://attack.mitre.org/techniques/T1053/005/)
- [Microsoft schtasks Documentation](https://docs.microsoft.com/en-us/windows-server/administration/windows-commands/schtasks)
- [Sysmon Configuration Guide](https://github.com/SwiftOnSecurity/sysmon-config)
