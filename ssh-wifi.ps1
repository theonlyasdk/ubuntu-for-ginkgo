param([string]$targetIp = "10.220.61.17", [string]$cmd = "uname -a; uptime")
$env:SSH_ASKPASS = "C:\Users\User\AppData\Local\Temp\gk-askpass.cmd"
$env:SSH_ASKPASS_REQUIRE = "force"
$env:DISPLAY = ""
& ssh.exe -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 "root@$targetIp" $cmd
