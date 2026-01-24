/*
 * Scheduled Task Removal Script
 * 
 * Removes the scheduled task created by task_com_bsi.exe
 * 
 * Usage: cscript remove_task.js
 */

var TASK_NAME = "GIMCTestBSI";
var TEMP_SCRIPT = "gimc_payload.js";

WScript.Echo("=== Removing Scheduled Task Persistence ===");
WScript.Echo("Task: " + TASK_NAME + "\n");

try {
    // Method 1: Use Task Scheduler COM API
    var taskService = new ActiveXObject("Schedule.Service");
    taskService.Connect();
    
    var rootFolder = taskService.GetFolder("\\");
    
    try {
        rootFolder.DeleteTask(TASK_NAME, 0);
        WScript.Echo("[+] Deleted scheduled task: " + TASK_NAME);
    } catch(e) {
        WScript.Echo("[-] Task not found or already deleted: " + TASK_NAME);
    }
    
} catch(e) {
    WScript.Echo("[ERROR] COM API failed: " + e.description);
    WScript.Echo("[INFO] Trying command-line method...");
    
    // Method 2: Fallback to command-line
    var shell = new ActiveXObject("WScript.Shell");
    var result = shell.Run('schtasks /Delete /TN "' + TASK_NAME + '" /F', 0, true);
    
    if (result === 0) {
        WScript.Echo("[+] Task deleted via schtasks command");
    } else {
        WScript.Echo("[-] Task may not exist or could not be deleted");
    }
}

// Clean up temporary payload script
try {
    var fso = new ActiveXObject("Scripting.FileSystemObject");
    var tempPath = fso.GetSpecialFolder(2); // Get temp folder
    var scriptPath = tempPath + "\\" + TEMP_SCRIPT;
    
    if (fso.FileExists(scriptPath)) {
        fso.DeleteFile(scriptPath);
        WScript.Echo("[+] Deleted temporary script: " + scriptPath);
    }
} catch(e) {
    // Not critical if cleanup fails
}

WScript.Echo("\n[SUCCESS] Cleanup complete");
WScript.Quit(0);
