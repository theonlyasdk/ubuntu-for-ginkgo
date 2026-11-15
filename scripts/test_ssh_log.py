import paramiko, socket, logging, sys

logging.basicConfig(level=logging.DEBUG)

sock = socket.socket()
sock.settimeout(5.0)
sock.connect(("192.168.7.2", 22))

t = paramiko.Transport(sock)
t.start_client(timeout=5.0)
print("Client started")
