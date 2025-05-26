import socket

server_ip = "127.0.0.1"
server_port = 6969

filename = "archivo_grande.txt"
mode = "octet"

# Códigos de operación (OPCODE)
WRQ = (2).to_bytes(2, byteorder='big')
DATA = (3).to_bytes(2, byteorder='big')
ACK = (4).to_bytes(2, byteorder='big')

# Crear socket UDP
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Armar y enviar paquete WRQ (Write Request)
filename_bytes = filename.encode() + b'\x00'
mode_bytes = mode.encode() + b'\x00'
wrq_packet = WRQ + filename_bytes + mode_bytes
sock.sendto(wrq_packet, (server_ip, server_port))
print(f"Enviado paquete WRQ (archivo: {filename}, modo: {mode})")

try:
    sock.settimeout(3)
    data, addr = sock.recvfrom(1024)

    # Verificar si recibimos un ACK válido
    if len(data) == 4 and data[1] == 4:
        print("ACK recibido del servidor, comenzando envío del archivo...")

        try:
            with open(filename, "rb") as f:
                block_number = 1

                while True:
                    filedata = f.read(512)
                    if not filedata:
                        print("Fin del archivo alcanzado.")
                        break

                    block = block_number.to_bytes(2, byteorder='big')
                    data_packet = DATA + block + filedata
                    sock.sendto(data_packet, (server_ip, server_port))
                    print(f"Enviado DATA bloque {block_number}")

                    # Esperar ACK para el bloque
                    try:
                        ack_data, _ = sock.recvfrom(1024)
                        if len(ack_data) == 4 and ack_data[1] == 4 and ack_data[2:4] == block:
                            print(f"ACK recibido para bloque {block_number}")
                        else:
                            print(f"ACK inválido o inesperado: {ack_data}")
                            break
                    except socket.timeout:
                        print(f"Timeout esperando ACK del bloque {block_number}")
                        break

                    block_number += 1

        except FileNotFoundError:
            print(f"El archivo '{filename}' no fue encontrado.")

    else:
        print(f"Respuesta inesperada del servidor: {data}")

except socket.timeout:
    print("No se recibió ACK de WRQ (timeout)")

sock.close()
