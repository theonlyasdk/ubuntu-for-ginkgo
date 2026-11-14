param([string]$cmd)
$env:SSH_ASKPASS = "C:\Users\User\AppData\Local\Temp\gk-askpass.cmd"
$env:SSH_ASKPASS_REQUIRE = "force"
$env:DISPLAY = ""
$target = if ($env:GINKGO_IP) { $env:GINKGO_IP } else { "192.168.7.2" }
$bind = if ($target -eq "192.168.7.2") { @("-b", "192.168.7.1") } else { @() }
& ssh.exe -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 @bind "root@$target" $cmd
