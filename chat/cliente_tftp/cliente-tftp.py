import socket

ROJO = '\033[91m'
VERDE = '\033[92m'
AMARILLO = '\033[93m'
AZUL = '\033[94m'
NEGRITA = '\033[1m'
RESET = '\033[0m'

def info(msg):
    print(f"{AZUL}ℹ️  {msg}{RESET}")

def exito(msg):
    print(f"{VERDE}✅ {msg}{RESET}")

def advertencia(msg):
    print(f"{AMARILLO}⚠️  {msg}{RESET}")

def error(msg):
    print(f"{ROJO}❌ {msg}{RESET}")

MAX_RETRIES = 3
TIMEOUT = 2  

server_ip = input("🔌 IP del servidor TFTP (ej: 192.168.1.10): ").strip()
if not server_ip:
    error("Debés ingresar una IP.")
    exit(1)

server_port = input("📦 Puerto del servidor [6969]: ").strip()
server_port = int(server_port) if server_port else 6969
mode = "octet"

operacion = input("📁 ¿Qué operación querés realizar? (read/write): ").strip().lower()
if operacion not in ("read", "write"):
    error("Operación inválida, debe ser 'read' o 'write'.")
    exit(1)

filename = input("📝 Nombre del archivo: ").strip()
if not filename:
    error("Debés ingresar un nombre de archivo.")
    exit(1)

RRQ = (1).to_bytes(2, 'big')
WRQ = (2).to_bytes(2, 'big')
DATA = (3).to_bytes(2, 'big')
ACK = (4).to_bytes(2, 'big')

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(TIMEOUT)

filename_bytes = filename.encode() + b'\x00'
mode_bytes = mode.encode() + b'\x00'
request_packet = (RRQ if operacion == "read" else WRQ) + filename_bytes + mode_bytes

retries = 0
response_received = False
server_addr = (server_ip, server_port)

while retries < MAX_RETRIES and not response_received:
    info(f"Enviando paquete {'RRQ' if operacion == 'read' else 'WRQ'} (intento {retries + 1})")
    sock.sendto(request_packet, server_addr)
    try:
        data, server_addr = sock.recvfrom(516)
        response_received = True
    except socket.timeout:
        advertencia("Timeout esperando respuesta del servidor. Reintentando...")
        retries += 1

if not response_received:
    error("No se recibió respuesta después de 3 intentos. Abandonando.")
    sock.close()
    exit(1)

# --- MANEJO DE ERRORES ---
if len(data) >= 4 and data[1] == 5:
    error_code = data[3]
    error_msg = data[4:-1].decode(errors="replace")
    error(f"ERROR TFTP ({error_code}): {error_msg}")
    sock.close()
    exit(1)

# --- TRANSFERENCIA WRITE ---
if operacion == 'write':
    if len(data) == 4 and data[1] == 4:
        exito("ACK recibido. Comenzando envío...")
        try:
            with open(filename, "rb") as f:
                block_number = 1
                while True:
                    filedata = f.read(512)
                    if not filedata:
                        exito("Fin del archivo alcanzado.")
                        break

                    data_packet = DATA + block_number.to_bytes(2, 'big') + filedata
                    ack_received = False
                    retries = 0

                    while retries < MAX_RETRIES and not ack_received:
                        sock.sendto(data_packet, server_addr)
                        info(f"📤 Enviado bloque {block_number} (intento {retries + 1})")
                        try:
                            ack_data, _ = sock.recvfrom(516)
                            if len(ack_data) >= 4 and ack_data[1] == 5:
                                error(f"TFTP ERROR ({ack_data[3]}): {ack_data[4:-1].decode(errors='replace')}")
                                sock.close()
                                exit(1)
                            if ack_data[1] == 4 and ack_data[2:4] == block_number.to_bytes(2, 'big'):
                                exito(f"ACK recibido para bloque {block_number}")
                                ack_received = True
                            else:
                                advertencia("ACK inválido o inesperado.")
                                retries += 1
                        except socket.timeout:
                            advertencia("Timeout esperando ACK. Reintentando...")
                            retries += 1

                    if not ack_received:
                        error(f"Sin ACK para bloque {block_number}. Abortando.")
                        break

                    block_number += 1
        except FileNotFoundError:
            error(f"El archivo '{filename}' no fue encontrado.")
    else:
        advertencia(f"Respuesta inesperada: {data}")

# --- TRANSFERENCIA READ ---
elif operacion == 'read':
    if len(data) >= 4 and data[1] == 3:
        block_number = int.from_bytes(data[2:4], 'big')
        received_data = data[4:]

        with open("descarga_" + filename, "wb") as f:
            info(f"Descargando '{filename}'...")
            while True:
                f.write(received_data)
                exito(f"📥 Bloque {block_number} ({len(received_data)} bytes)")
                ack_packet = ACK + data[2:4]
                sock.sendto(ack_packet, server_addr)

                if len(received_data) < 512:
                    exito("Transferencia finalizada correctamente.")
                    break

                retries = 0
                while retries < MAX_RETRIES:
                    try:
                        data, server_addr = sock.recvfrom(516)
                        if len(data) >= 4 and data[1] == 5:
                            error(f"TFTP ERROR ({data[3]}): {data[4:-1].decode(errors='replace')}")
                            sock.close()
                            exit(1)
                        if data[1] == 3:
                            block_number = int.from_bytes(data[2:4], 'big')
                            received_data = data[4:]
                            break
                        else:
                            advertencia("Paquete inesperado.")
                            retries += 1
                    except socket.timeout:
                        advertencia("Timeout esperando DATA. Reintentando...")
                        retries += 1

                if retries == MAX_RETRIES:
                    error("No se recibió el siguiente bloque. Transferencia abortada.")
                    break
    else:
        advertencia(f"Respuesta inesperada: {data}")

sock.close()