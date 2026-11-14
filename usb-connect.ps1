#requires -Version 5.1
<#
.SYNOPSIS
  Re-point the Windows RNDIS adapter at the ginkgo phone after every reboot.
  Windows equivalent of scripts/usb-connect.sh. Run as Administrator.
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\usb-connect.ps1
#>
param(
    [string]$AdapterName,
    [string]$PhoneIP    = "192.168.7.2",
    [string]$HostIP     = "192.168.7.1",
    [string]$IcsIP      = "192.168.137.1",
    [int]$WaitAdapter   = 45,
    [int]$WaitPing      = 60
)

$ErrorActionPreference = "Stop"

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Error "Run this script as Administrator (right-click PowerShell -> Run as Administrator)."
    exit 1
}

function Find-RndisAdapter {
    param([string]$Name)
    if ($Name) { return Get-NetAdapter -Name $Name -ErrorAction SilentlyContinue }
    # The phone's USB gadget enumerates as an RNDIS / USB-Ethernet NIC.
    return Get-NetAdapter | Where-Object {
        $_.InterfaceDescription -match 'RNDIS|Remote NDIS|USB Ethernet|CDC|Gadget'
    } | Select-Object -First 1
}

Write-Host "==> Waiting for the phone's RNDIS adapter..."
$adapter = $null
for ($i = 0; $i -lt $WaitAdapter; $i++) {
    $adapter = Find-RndisAdapter -Name $AdapterName
    if ($adapter) { break }
    Start-Sleep -Seconds 1
}
if (-not $adapter) {
    Write-Error "No USB RNDIS adapter found. Is the phone booted and plugged in?`n$(Get-NetAdapter | Format-Table Name,InterfaceDescription,Status | Out-String)"
    exit 1
}

$idx = $adapter.ifIndex
Write-Host "==> RNDIS adapter: $($adapter.Name) ($($adapter.InterfaceDescription))"

if ($adapter.Status -ne 'Up') {
    Enable-NetAdapter -Name $adapter.Name -Confirm:$false
    Start-Sleep -Seconds 2
}

# DHCP on this NIC fails and flushes the static address; turn it off.
Set-NetIPInterface -InterfaceIndex $idx -Dhcp Disabled -ErrorAction SilentlyContinue

Get-NetIPAddress -InterfaceIndex $idx -ErrorAction SilentlyContinue |
    Remove-NetIPAddress -Confirm:$false -ErrorAction SilentlyContinue
Get-NetRoute -InterfaceIndex $idx -ErrorAction SilentlyContinue |
    Remove-NetRoute -Confirm:$false -ErrorAction SilentlyContinue

New-NetIPAddress -InterfaceIndex $idx -IPAddress $HostIP -PrefixLength 24 | Out-Null
New-NetIPAddress -InterfaceIndex $idx -IPAddress $IcsIP  -PrefixLength 24 -ErrorAction SilentlyContinue | Out-Null

Write-Host "==> Host $HostIP (+$IcsIP) -> phone $PhoneIP"

Write-Host "==> Waiting for ping..."
$pinged = $false
for ($i = 0; $i -lt $WaitPing; $i++) {
    if (Test-Connection -ComputerName $PhoneIP -Count 1 -Quiet -ErrorAction SilentlyContinue) {
        Write-Host "==> Ping OK ($($i + 1)s)"
        $pinged = $true
        break
    }
    Start-Sleep -Seconds 1
}
if (-not $pinged) {
    Write-Warning "$PhoneIP not pingable after ${WaitPing}s. Windows Firewall often drops ICMP here; SSH can still work."
}

# Optional SSH probe, same askpass helper as ssh-exec.ps1.
$askpass = Join-Path $env:LOCALAPPDATA "Temp\gk-askpass.cmd"
if (Test-Path $askpass) {
    $env:SSH_ASKPASS = $askpass
    $env:SSH_ASKPASS_REQUIRE = "force"
    $env:DISPLAY = ""
    $ok = & ssh.exe -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 -b $HostIP "root@$PhoneIP" "echo ssh-ok" 2>$null
    if ($ok -match "ssh-ok") { Write-Host "==> SSH OK" }
} else {
    Write-Host "==> (no askpass helper at $askpass; skipping SSH probe)"
}

Write-Host "SSH: ssh -b $HostIP root@$PhoneIP"