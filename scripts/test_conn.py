import socket
s = socket.socket()
s.settimeout(2.0)
try:
    s.connect(("192.168.7.2", 22))
    print("Connected successfully!")
    banner = s.recv(1024)
    print("Banner:", banner)
except Exception as e:
    print("Connection error:", e)
finally:
    s.close()
