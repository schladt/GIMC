param(
    [switch]$u
)

function Install-Sysmon {
    Write-Host "Installing Sysmon with config.xml..."
    & .\sysmon64.exe -accepteula -i .\config.xml

}

function Uninstall-Sysmon {
    Write-Host "Uninstalling Sysmon..."
    & .\sysmon64.exe -u

}

if ($u) {
    Uninstall-Sysmon
} else {
    Install-Sysmon
}