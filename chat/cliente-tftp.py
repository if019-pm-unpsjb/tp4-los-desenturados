import socket

MAX_RETRIES = 3
TIMEOUT = 2  # segundos

server_ip = input("IP del servidor TFTP (ej: 192.168.1.10): ").strip()
if not server_ip:
    print("Debés ingresar una IP.")
    exit(1)

server_port = input("Puerto del servidor [6969]: ").strip()
server_port = int(server_port) if server_port else 6969
mode = "octet"

operacion = input("¿Qué operación querés realizar? (read/write): ").strip().lower()
if operacion not in ("read", "write"):
    print("Operación inválida, debe ser 'read' o 'write'.")
    exit(1)

filename = input("Nombre del archivo: ").strip()
if not filename:
    print("Debés ingresar un nombre de archivo.")
    exit(1)

# Códigos de operación (OPCODE)
RRQ = (1).to_bytes(2, byteorder='big')
WRQ = (2).to_bytes(2, byteorder='big')
DATA = (3).to_bytes(2, byteorder='big')
ACK = (4).to_bytes(2, byteorder='big')

# Crear socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(TIMEOUT)

filename_bytes = filename.encode() + b'\x00'
mode_bytes = mode.encode() + b'\x00'
if operacion == "read":
    request_packet = RRQ + filename_bytes + mode_bytes
else:
    request_packet = WRQ + filename_bytes + mode_bytes

# --- REINTENTOS DEL PRIMER PAQUETE ---
retries = 0
response_received = False
server_addr = (server_ip, server_port)

while retries < MAX_RETRIES and not response_received:
    print(f"Enviado paquete {'RRQ' if operacion == 'read' else 'WRQ'} (intento {retries+1})")
    sock.sendto(request_packet, server_addr)

    try:
        data, server_addr = sock.recvfrom(1024)
        response_received = True
    except socket.timeout:
        print("Timeout esperando respuesta del servidor, reintentando...")
        retries += 1
        
if not response_received:
    print("No se recibió respuesta del servidor después de 3 intentos. Abandonando.")
    sock.close()
    exit(1)

# --- MANEJO DE PAQUETE DE ERROR TFTP ---
if len(data) >= 4 and data[1] == 5:
    error_code = data[3]
    error_msg = data[4:-1].decode(errors="replace")
    print(f"\nERROR TFTP del servidor ({error_code}): {error_msg}\n")
    sock.close()
    exit(1)

if operacion == 'write':
    if len(data) == 4 and data[1] == 4:
        print("ACK recibido, comenzando envio")
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

                    retries = 0
                    ack_received = False

                    while retries < MAX_RETRIES and not ack_received:
                        sock.sendto(data_packet, server_addr)

                        print(f"Enviado DATA bloque {block_number} (intento {retries + 1})")
                        try:
                            ack_data, _ = sock.recvfrom(1024)
                            if len(ack_data) >= 4 and ack_data[1] == 5:
                                # Error recibido
                                error_code = ack_data[3]
                                error_msg = ack_data[4:-1].decode(errors="replace")
                                print(f"\nERROR TFTP del servidor ({error_code}): {error_msg}\n")
                                sock.close()
                                exit(1)
                            if len(ack_data) == 4 and ack_data[1] == 4 and ack_data[2:4] == block:
                                print(f"ACK recibido para bloque {block_number}")
                                ack_received = True
                            else:
                                print(f"ACK inválido o inesperado: {ack_data}")
                                retries += 1
                        except socket.timeout:
                            print(f"Timeout esperando ACK del bloque {block_number}, reintentando...")
                            retries += 1

                    if not ack_received:
                        print(f"No se recibió ACK para el bloque {block_number} después de {MAX_RETRIES} intentos. Abandonando la transferencia.")
                        break

                    block_number += 1
        except FileNotFoundError:
            print(f"El archivo '{filename}' no fue encontrado.")
    else:
        print(f"Respuesta inesperada del servidor: {data}")

elif operacion == "read":
    if len(data) >= 4 and data[1] == 3:
        block_number = int.from_bytes(data[2:4], byteorder='big')
        received_data = data[4:]

        with open("descarga_" + filename, "wb") as f:
            print(f"Recibiendo datos para '{filename}'...")
            while True:
                f.write(received_data)
                print(f"Bloque recibido: {block_number} ({len(received_data)} bytes)")
                ack_packet = ACK + data[2:4]
                sock.sendto(ack_packet, server_addr)

                if len(received_data) < 512:
                    print("Fin de la transferencia.")
                    break

                retries = 0
                while retries < MAX_RETRIES:
                    try:
                        data, server_addr = sock.recvfrom(1024)
                        if len(data) >= 4 and data[1] == 5:
                            # Error recibido
                            error_code = data[3]
                            error_msg = data[4:-1].decode(errors="replace")
                            print(f"\nERROR TFTP del servidor ({error_code}): {error_msg}\n")
                            sock.close()
                            exit(1)
                        if len(data) >= 4 and data[1] == 3:
                            block_number = int.from_bytes(data[2:4], byteorder='big')
                            received_data = data[4:]
                            break  # Salimos del while retries para procesar el siguiente bloque
                        else:
                            print(f"Paquete inesperado: {data}")
                            retries += 1
                    except socket.timeout:
                        print(f"Timeout esperando DATA. Reintentando ({retries + 1}/{MAX_RETRIES})...")
                        retries += 1

                if retries == MAX_RETRIES:
                    print("No se recibió el siguiente bloque después de 3 intentos. Transferencia abortada.")
                    break
    else:
        print(f"Respuesta inesperada del servidor: {data}")

sock.close()