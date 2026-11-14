param([string]$src, [string]$dst)
$env:SSH_ASKPASS = "C:\Users\User\AppData\Local\Temp\gk-askpass.cmd"
$env:SSH_ASKPASS_REQUIRE = "force"
$env:DISPLAY = ""
$target = if ($env:GINKGO_IP) { $env:GINKGO_IP } else { "192.168.7.2" }
& scp.exe -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 $src "root@${target}:${dst}"
