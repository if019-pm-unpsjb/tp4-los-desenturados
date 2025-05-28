import socket

server_ip = "127.0.0.1"
server_port = 6969
mode = "octet"

operacion = input("¿Qué operación querés realizar? (read/write): ").strip().lower()
if operacion not in ("read", "write"):
    print("Operación inválida, debe ser 'read' o 'write'.")
    exit(1)

filename = input("Nombre del archivo a transferir: ").strip()
if not filename:
    print("Debés ingresar un nombre de archivo.")
    exit(1)

# Códigos de operación (OPCODE)
RRQ = (1).to_bytes(2, byteorder='big')
WRQ = (2).to_bytes(2, byteorder='big')
DATA = (3).to_bytes(2, byteorder='big')
ACK = (4).to_bytes(2, byteorder='big')

# Crear socket UDP
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

filename_bytes=filename.encode() + b'\x00'
mode_bytes= mode.encode() + b'\x00'
if operacion=="read":
    request_packet= RRQ + filename_bytes + mode_bytes
    print(f"Enviado paquete RRQ (archivo:{filename}, modo:{mode})")
else:
    request_packet= WRQ + filename_bytes + mode_bytes
    print(f"Enviado paquete WRQ (archivo:{filename}, modo:{mode})")

sock.sendto(request_packet, (server_ip, server_port))

try:
    sock.settimeout(3)
    data, addr=sock.recvfrom(1024)
    
    if operacion=='write':
        if len(data)==4 and data[1]==4:
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

    elif operacion == "read":
        # --- RRQ: esperar y recibir datos del servidor ---
        if len(data) >= 4 and data[1] == 3:
            block_number = int.from_bytes(data[2:4], byteorder='big')
            received_data = data[4:]

            with open("descarga_" + filename, "wb") as f:
                print(f"Recibiendo datos para '{filename}'...")
                while True:
                    f.write(received_data)
                    print(f"Bloque recibido: {block_number} ({len(received_data)} bytes)")
                    # Enviar ACK por el bloque recibido
                    ack_packet = ACK + data[2:4]
                    sock.sendto(ack_packet, addr)

                    if len(received_data) < 512:
                        print("Fin de la transferencia.")
                        break
                    try:
                        data, addr = sock.recvfrom(1024)
                        if len(data) >= 4 and data[1] == 3:
                            block_number = int.from_bytes(data[2:4], byteorder='big')
                            received_data = data[4:]
                        else:
                            print(f"Paquete inesperado: {data}")
                            break
                    except socket.timeout:
                        print("Timeout esperando siguiente DATA.")
                        break
        else:
            print(f"Respuesta inesperada del servidor: {data}")

except socket.timeout:
    print("No se recibió respuesta del servidor (timeout)")

sock.close()
                    