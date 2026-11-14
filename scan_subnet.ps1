$subnet = "10.220.61."
1..254 | ForEach-Object {
    $ip = $subnet + $_
    $p = New-Object System.Net.NetworkInformation.Ping
    [void]$p.SendAsync($ip, 250, [byte[]]@(1))
}
Start-Sleep -Milliseconds 800
Get-NetNeighbor -InterfaceAlias "WiFi" | Where-Object { $_.IPAddress -like "10.220.61.*" } | Format-Table -AutoSize
