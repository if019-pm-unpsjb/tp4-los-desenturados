import socket
import threading

SERVER = "127.0.0.1"
PORT = 7777
USERNAME = input("Usuario: ")

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((SERVER, PORT))
sock.send(USERNAME.encode())

def listen():
    while True:
        data = sock.recv(4096)
        if not data:
            print("Servidor desconectado")
            break
        print(data.decode(errors="ignore"))

threading.Thread(target=listen, daemon=True).start()

while True:
    msg = input()
    sock.send(msg.encode())
