import sys, socket, threading, paramiko

def run(cmd):
    sock = socket.socket()
    sock.settimeout(5.0)
    sock.connect(("192.168.7.2", 22))

    t = paramiko.Transport(sock)
    event = threading.Event()
    t.start_client(event=event)
    event.wait(5.0)
    if not t.is_active():
        print("Transport failed to start:", t.get_exception())
        return

    t.auth_password("root", "password")
    if not t.is_authenticated():
        print("Auth failed!")
        return

    chan = t.open_session()
    chan.exec_command(cmd)
    stdout = chan.makefile("r")
    stderr = chan.makefile_stderr("r")
    out = stdout.read()
    err = stderr.read()
    if out:
        print(out)
    if err:
        print("ERR:", err, file=sys.stderr)
    t.close()

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "uname -a"
    run(cmd)
