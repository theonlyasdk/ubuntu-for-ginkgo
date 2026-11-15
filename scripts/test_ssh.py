import paramiko, socket

sock = socket.socket()
sock.settimeout(5.0)
sock.connect(("192.168.7.2", 22))

t = paramiko.Transport(sock)
t.connect(username="root", password="password")
print("Auth success:", t.is_authenticated())

session = t.open_session()
session.exec_command("uname -a; uptime")
print(session.recv(1024).decode())
t.close()
