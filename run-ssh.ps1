$scriptPath = (Resolve-Path $args[0]).Path
$env:SSH_ASKPASS = "C:\Users\User\AppData\Local\Temp\gk-askpass.cmd"
$env:SSH_ASKPASS_REQUIRE = "force"
$env:DISPLAY = ""
$bytes = [System.IO.File]::ReadAllBytes($scriptPath)
if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
    $bytes = $bytes[3..($bytes.Length-1)]
}
$cleanBytes = [System.Collections.Generic.List[byte]]::new()
for ($i = 0; $i -lt $bytes.Length; $i++) {
    if ($bytes[$i] -eq 13 -and ($i + 1) -lt $bytes.Length -and $bytes[$i+1] -eq 10) {
        continue
    }
    $cleanBytes.Add($bytes[$i])
}
$b64 = [Convert]::ToBase64String($cleanBytes.ToArray())
$remoteCmd = "echo $b64 | base64 -d | bash"
& ssh.exe -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 root@192.168.7.2 $remoteCmd
