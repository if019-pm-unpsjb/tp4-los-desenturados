import socket
import struct
import threading

SERVER_IP = '127.0.0.1'
SERVER_PORT = 7777

# Códigos de paquete
SYN = 0
ACK = 1
MSG = 2
FILE = 3
FIN = 4

def pack_packet(code, username, dest, data):
    # Prepara el paquete en binario según la estructura C
    username = username.encode('utf-8')[:32]
    username += b'\x00' * (32 - len(username))

    dest = dest.encode('utf-8')[:32]
    dest += b'\x00' * (32 - len(dest))

    if isinstance(data, str):
        data = data.encode('utf-8')
    data = data[:4096]
    datalen = len(data)
    data += b'\x00' * (4096 - len(data))

    return struct.pack('i32s32si4096s', code, username, dest, datalen, data)

def unpack_packet(packet):
    code, username, dest, datalen, data = struct.unpack('i32s32si4096s', packet)
    username = username.split(b'\x00', 1)[0].decode('utf-8')
    dest = dest.split(b'\x00', 1)[0].decode('utf-8')
    data = data[:datalen]
    try:
        data = data.decode('utf-8')
    except:
        pass  # para binarios
    return code, username, dest, datalen, data

def receive_loop(sock):
    while True:
        try:
            packet = sock.recv(4168)
            if not packet:
                print("Desconectado del servidor")
                break
            code, username, dest, datalen, data = unpack_packet(packet)
            if code == MSG:
                print(f"\n[{username} → {dest}]: {data}")
            elif code == FILE:
                print(f"\n[Archivo de {username} → {dest}]: {datalen} bytes (no implementado guardar)")
            elif code == SYN:
                print(f"\n[SERVIDOR]: Handshake recibido (SYN)")
            elif code == ACK:
                print(f"\n[SERVIDOR]: Handshake completado (ACK)")
            elif code == FIN:
                print(f"\n[{username}] terminó la conexión")
                break
        except Exception as e:
            print("Error de recepción:", e)
            break

def main():
    username = input("Tu nombre de usuario: ")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((SERVER_IP, SERVER_PORT))

    # --- Three-way handshake ---
    pkt_syn = pack_packet(SYN, username, '', '')
    sock.sendall(pkt_syn)

    # Espera respuesta SYN del servidor
    resp = sock.recv(4168)
    code, _, _, _, _ = unpack_packet(resp)
    if code == SYN:
        pkt_ack = pack_packet(ACK, username, '', '')
        sock.sendall(pkt_ack)
        print("Handshake completado")

    # Thread para escuchar mensajes entrantes
    threading.Thread(target=receive_loop, args=(sock,), daemon=True).start()

    # --- Loop principal para enviar mensajes ---
    while True:
        print("\nOpciones: 1. Enviar mensaje | 2. Salir")
        opcion = input("Elegí opción: ")
        if opcion == '1':
            dest = input("Usuario destinatario: ")
            mensaje = input("Mensaje: ")
            pkt_msg = pack_packet(MSG, username, dest, mensaje)
            sock.sendall(pkt_msg)
        elif opcion == '2':
            pkt_fin = pack_packet(FIN, username, '', '')
            sock.sendall(pkt_fin)
            print("Desconectando...")
            break
        else:
            print("Opción no válida")

    sock.close()

if __name__ == '__main__':
    main()
