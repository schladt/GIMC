/*
 * WMI Event Subscription Persistence Removal Script
 * 
 * This script removes all WMI artifacts created by wmi_persistence_bsi.cpp
 * 
 * Usage: cscript remove_wmi_persistence.js
 */

var INSTALL_NAME = "GIMCTestBSI";

var oWMI = GetObject("winmgmts:\\\\.\\root\\subscription");

WScript.Echo("=== Removing WMI Event Subscription Persistence ===");
WScript.Echo("Target: " + INSTALL_NAME + "\n");

var success = true;
var itemsDeleted = 0;

// Step 1: Remove FilterToConsumerBinding
try {
    var bindings = oWMI.ExecQuery(
        "SELECT * FROM __FilterToConsumerBinding WHERE Filter=\"__EventFilter.Name='" + 
        INSTALL_NAME + "_filter'\""
    );
    
    var bindEnum = new Enumerator(bindings);
    while (!bindEnum.atEnd()) {
        bindEnum.item().Delete_();
        WScript.Echo("[+] Deleted __FilterToConsumerBinding");
        itemsDeleted++;
        bindEnum.moveNext();
    }
} catch(e) {
    WScript.Echo("[-] Warning: Could not delete binding: " + e.description);
    success = false;
}

// Step 2: Remove EventFilter
try {
    var filter = oWMI.Get("__EventFilter.Name='" + INSTALL_NAME + "_filter'");
    filter.Delete_();
    WScript.Echo("[+] Deleted __EventFilter: " + INSTALL_NAME + "_filter");
    itemsDeleted++;
} catch(e) {
    WScript.Echo("[-] Warning: Could not delete event filter: " + e.description);
    success = false;
}

// Step 3: Remove ActiveScriptEventConsumer
try {
    var consumer = oWMI.Get("ActiveScriptEventConsumer.Name='" + INSTALL_NAME + "_consumer'");
    consumer.Delete_();
    WScript.Echo("[+] Deleted ActiveScriptEventConsumer: " + INSTALL_NAME + "_consumer");
    itemsDeleted++;
} catch(e) {
    WScript.Echo("[-] Warning: Could not delete event consumer: " + e.description);
    success = false;
}

// Step 4: Remove IntervalTimerInstruction
try {
    var timer = oWMI.Get("__IntervalTimerInstruction.TimerID='" + INSTALL_NAME + "_Timer'");
    timer.Delete_();
    WScript.Echo("[+] Deleted __IntervalTimerInstruction: " + INSTALL_NAME + "_Timer");
    itemsDeleted++;
} catch(e) {
    WScript.Echo("[-] Warning: Could not delete timer instruction: " + e.description);
    success = false;
}

// Step 5: Kill scrcons.exe (WMI script consumer host process) to stop running payload
try {
    var oWMI2 = GetObject("winmgmts:\\\\.\\root\\cimv2");
    var processes = oWMI2.ExecQuery("SELECT * FROM Win32_Process WHERE Name='scrcons.exe'");
    
    var procEnum = new Enumerator(processes);
    while (!procEnum.atEnd()) {
        procEnum.item().Terminate();
        WScript.Echo("[+] Terminated scrcons.exe process");
        itemsDeleted++;
        procEnum.moveNext();
    }
} catch(e) {
    WScript.Echo("[-] Note: No scrcons.exe process found or could not terminate");
}

// Summary
WScript.Echo("\n=== Cleanup Summary ===");
if (itemsDeleted > 0) {
    WScript.Echo("[SUCCESS] Removed " + itemsDeleted + " WMI artifact(s)");
    WScript.Echo("WMI persistence has been cleaned up.");
} else {
    WScript.Echo("[INFO] No artifacts found. Persistence may have already been removed.");
}

if (!success) {
    WScript.Echo("\n[WARNING] Some items could not be deleted. You may need administrator privileges.");
    WScript.Quit(1);
}

WScript.Quit(0);
