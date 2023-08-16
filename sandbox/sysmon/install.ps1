# Script to install Sysmon with config.xml
# -u switch to uninstall Sysmon 

param(
    [switch]$u
)

function Install-Sysmon {
    Write-Host "Installing Sysmon with config.xml..."
    Start-Process -FilePath .\Sysmon64.exe -ArgumentList "-accepteula", "-i", ".\config.xml" -Wait
    Write-Host "Sysmon Installed!"
}

function Uninstall-Sysmon {
    Write-Host "Uninstalling Sysmon..."
    Start-Process -FilePath .\Sysmon64.exe -ArgumentList "-u", "--force" -Wait
    Write-Host "Sysmon Uninstalled!"
}

if ($u) {
    Uninstall-Sysmon
} else {
    Install-Sysmon
}