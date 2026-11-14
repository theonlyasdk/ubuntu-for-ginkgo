import sys, subprocess

cmd = sys.argv[1]
res = subprocess.run([
    'wsl', '-d', 'Ubuntu-26.04', '-u', 'root', '-e',
    'sshpass', '-p', 'password',
    'ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null',
    'root@192.168.7.2', cmd
], capture_output=True, text=True)

print(res.stdout)
if res.stderr:
    print("STDERR:", res.stderr, file=sys.stderr)
sys.exit(res.returncode)
