import socket

server_ip = "127.0.0.1"
server_port = 6969

filename = "prueba.txt"
mode = "octet"

# OPCODE
WRQ = (2).to_bytes(2, byteorder='big')
DATA = (3).to_bytes(2, byteorder='big')
ACK = (4).to_bytes(2, byteorder='big')

# Abrimos el archivo para enviar (si no existe, enviamos datos de prueba)
try:
    with open(filename, "rb") as f:
        filedata = f.read(512)  # Leer el primer bloque
except FileNotFoundError:
    filedata = b"Este es un bloque de prueba enviado desde el cliente.\n"  # Dummy

# Paquete WRQ
filename_bytes = filename.encode() + b'\x00'
mode_bytes = mode.encode() + b'\x00'
wrq_packet = WRQ + filename_bytes + mode_bytes

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.sendto(wrq_packet, (server_ip, server_port))
print(f"Enviado paquete WRQ (archivo: {filename}, modo: {mode})")

try:
    sock.settimeout(3)
    data, addr = sock.recvfrom(1024)
    if len(data) == 4 and data[1] == 4:
        print(f"ACK recibido del servidor, enviando DATA...")

        # Armado de paquete DATA: [2 bytes opcode][2 bytes block][N bytes data]
        block = (1).to_bytes(2, byteorder='big')  # Primer bloque es el número 1
        data_packet = DATA + block + filedata
        sock.sendto(data_packet, (server_ip, server_port))
        print("Enviado primer paquete DATA")

        # Esperar el ACK del bloque 1
        ack_data, _ = sock.recvfrom(1024)
        if len(ack_data) == 4 and ack_data[1] == 4 and ack_data[3] == 1:
            print("ACK del bloque 1 recibido, transferencia exitosa (1 bloque)")
        else:
            print(f"ACK inesperado: {ack_data}")

    else:
        print(f"Respuesta inesperada del servidor: {data}")
except socket.timeout:
    print("No se recibió respuesta (timeout)")

sock.close()
