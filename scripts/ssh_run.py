import sys, paramiko

cmd = sys.argv[1] if len(sys.argv) > 1 else "uname -a"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.7.2', username='root', password='password', timeout=10)
stdin, stdout, stderr = client.exec_command(cmd)
out = stdout.read().decode('utf-8', errors='replace')
err = stderr.read().decode('utf-8', errors='replace')
if out:
    print(out, end='')
if err:
    print(err, file=sys.stderr, end='')
client.close()
