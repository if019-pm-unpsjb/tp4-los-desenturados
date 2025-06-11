import socket
import threading
import time
import struct

# Códigos de tipo de paquete
CODIGO_SYN = 0
CODIGO_ACK = 1
CODIGO_MENSAJE = 2
CODIGO_FILE = 3
CODIGO_FIN = 4
CODIGO_ACEPTADO = 5
CODIGO_RECHAZADO = 6

# ANSI colors para mejorar visualización
ROJO = '\033[91m'
VERDE = '\033[92m'
AZUL = '\033[94m'
AMARILLO = '\033[93m'
NEGRITA = '\033[1m'
RESET = '\033[0m'

SERVIDOR = "132.255.7.157"
PUERTO = 28008
USUARIO = input(f"{NEGRITA}Usuario:{RESET} ").strip().encode('utf-8')[:32]

usuarios_conectados = set()  

socket_cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    socket_cliente.connect((SERVIDOR, PUERTO))
except ConnectionRefusedError:
    print(f"{ROJO}[!] No se pudo conectar al servidor en {SERVIDOR}:{PUERTO}.{RESET}")
    exit(1)

def construir_paquete(codigo, usuario=b"", destino=b"", datos=b""):
    usuario = usuario.ljust(32, b'\x00')[:32]
    destino = destino.ljust(32, b'\x00')[:32]
    longitud_datos = len(datos)
    datos = datos + b'\x00' * (4096 - len(datos)) if len(datos) < 4096 else datos[:4096]

    formato_paquete = "i32s32si4096s" #buscar para entender
    return struct.pack(formato_paquete, codigo, usuario, destino, longitud_datos, datos)

def limpiar_nombre(nombre_bytes):
    return nombre_bytes.decode('utf-8').strip('\x00').strip()

def recv_exact(sock, size):
    buffer = b''
    while len(buffer) < size:
        parte = sock.recv(size - len(buffer))
        if not parte:
            # Conexión cerrada prematuramente
            return None
        buffer += parte
    return buffer
def realizar_conexion():
    print(f"{AZUL}[*] Iniciando conexion...{RESET}")

    # Paso 1: Enviar SYN
    paquete_syn = construir_paquete(CODIGO_SYN, usuario=USUARIO)
    socket_cliente.sendall(paquete_syn)

    try:
        respuesta = recv_exact(socket_cliente, 4168)
    except ConnectionResetError:
        print(f"{ROJO}[!] El servidor cerró la conexión abruptamente (reset by peer){RESET}")
        return False

    if respuesta is None:
        print(f"{ROJO}[!] Conexión cerrada por el servidor{RESET}")
        return False

    codigo, usuario_resp, destino_resp, longitud_datos, datos = struct.unpack("i32s32si4096s", respuesta)
    if codigo == CODIGO_SYN:
        print(f"{VERDE}[*] Recibido ACK{RESET}")
        # Paso 2: Enviar ACK
        paquete_ack = construir_paquete(CODIGO_ACK, usuario=USUARIO)
        socket_cliente.sendall(paquete_ack)
        time.sleep(0.2)

        # NO ENVIAMOS MENSAJE A UNO MISMO, evitamos comportamiento inesperado
        return True
    else:
        print(f"{ROJO}[!] Se esperaba SYN pero se recibió código {codigo}{RESET}")
        return False


def escuchar_mensajes():
    while True:
        try:
            datos = recv_exact(socket_cliente, 4168)
            if datos is None:
                print(f"{ROJO}Servidor desconectado{RESET}")
                break

            codigo, usuario_emisor, usuario_destino, longitud_datos, contenido = struct.unpack("i32s32si4096s", datos)

            usuario_emisor = limpiar_nombre(usuario_emisor)
            usuario_destino = limpiar_nombre(usuario_destino)
            mensaje = contenido[:longitud_datos].decode(errors="ignore")#buscar que significa

            if codigo == CODIGO_MENSAJE:
                if usuario_emisor in usuarios_conectados:
                    print(f"\n{VERDE}[Mensaje de {usuario_emisor}]{RESET}: {mensaje}")
                else:
                    print(f"\n{AZUL}[Solicitud] Conexión de '{usuario_emisor}'. Usá {NEGRITA}/aceptar {usuario_emisor}{RESET}{AZUL} o {NEGRITA}/rechazar {usuario_emisor}{RESET}{AZUL}.{RESET}")
            
            #codigo del chat
            elif codigo == CODIGO_FILE:
                # Primer mensaje: nombre del archivo
                nombre_archivo = contenido[:longitud_datos].decode(errors="replace")
                archivo_recibido = f"archivo_de_{usuario_emisor}_{nombre_archivo}"
                print(f"{AZUL}[←] Recibiendo archivo '{nombre_archivo}' de {usuario_emisor}{RESET}")
                with open(archivo_recibido, "wb") as f:
                    while True:
                        datos_archivo = recv_exact(socket_cliente, 4168)
                        if datos_archivo is None:
                            print(f"{ROJO}Conexión cerrada inesperadamente{RESET}")
                            break
                        print(f"[Bloque recibido] {longitud_datos} bytes de {usuario_emisor}")
                        _, _, _, longitud_datos, contenido = struct.unpack("i32s32si4096s", datos_archivo)
                        f.write(contenido[:longitud_datos]) 
                        if longitud_datos < 4096: # último bloque recibido
                            print(f"{VERDE}[✓] Archivo recibido completo: {archivo_recibido}{RESET}")
                            break

                    else:
                        print(f"{AMARILLO}[Código desconocido {codigo} de {usuario_emisor}]{RESET}: {mensaje}")

            elif codigo == CODIGO_ACEPTADO:
                usuarios_conectados.add(usuario_emisor)
                print(f"\n{VERDE}[Conexión aceptada] Ya podés chatear con '{usuario_emisor}'.{RESET}")
                print(f"[Debug] usuarios_conectados: {usuarios_conectados}")
                print(f"[Debug] Mensaje de: '{usuario_emisor}'")
            else:
                print(f"{AMARILLO}[Código desconocido {codigo} de {usuario_emisor}]{RESET}: {mensaje}")

        except Exception as e:
            print(f"{ROJO}[!] Error al recibir mensaje: {e}{RESET}")
            break

if realizar_conexion():
    threading.Thread(target=escuchar_mensajes, daemon=True).start()
    print(f"{VERDE}[*] Conexión establecida correctamente{RESET}")

    while True:
        destino_str = input(f"{NEGRITA}Enviar a (usuario destino) > {RESET}").strip()
        destino = destino_str.encode('utf-8')[:32]
        entrada = input("'Mensaje' para chatear o '/archivo' para enviar archivo (escribí 'salir' para cerrar): ").strip()
        #mandar archivo
        if (entrada.startswith("/archivo")):
            if(destino_str in usuarios_conectados):
                nombre_archivo= input(f"Ingrese nombre de archivo").strip()
                try:
                    with open(nombre_archivo, "rb") as archivo:
                        print(f"{AZUL}Enviando archivo {nombre_archivo} a {destino_str}{RESET}")
                        
                        nombre_bytes = nombre_archivo.encode("utf-8")
                        paquete_nombre = construir_paquete(
                            CODIGO_FILE,
                            usuario=USUARIO,
                            destino=destino,
                            datos=nombre_bytes  # solo el nombre del archivo
                        )
                        socket_cliente.sendall(paquete_nombre)
                        print(f"[→] Nombre del archivo enviado: {nombre_archivo}")
                        numero_bloque = 1
                        while True:
                            datos = archivo.read(4096)
                            if not datos:
                                print(f"{VERDE}Archivo enviado correctamente.{RESET}")
                                break
                            paquete = construir_paquete(CODIGO_FILE, usuario=USUARIO, destino=destino, datos=datos)
                            socket_cliente.sendall(paquete)
                            print(f"Enviado bloque {numero_bloque} del archivo {nombre_archivo}")
                            numero_bloque += 1
                        print(f"{VERDE}Fin de envío del archivo.{RESET}")          
                except FileNotFoundError:
                    print(f"{ROJO}[!] El archivo '{nombre_archivo}' no existe{RESET}")
                except Exception as e:
                    print(f"{ROJO}[!] Error al enviar archivo: {e}{RESET}")
                continue
            else:
                print(f"{ROJO}[!] no tiene una conexion establecida con el usuario {destino}{RESET}")
                continue

        if entrada.lower() == "salir":
            paquete = construir_paquete(CODIGO_FIN, usuario=USUARIO)
            socket_cliente.sendall(paquete)
            print(f"{AMARILLO}[*] Cerrando conexión y saliendo...{RESET}")
            break

        elif entrada.startswith("/aceptar "):
            usuario_a_aceptar = entrada.split(maxsplit=1)[1].strip().encode('utf-8')[:32]
            paquete_aceptar = construir_paquete(CODIGO_ACEPTADO, usuario=USUARIO, destino=usuario_a_aceptar)
            socket_cliente.sendall(paquete_aceptar)
            usuarios_conectados.add(usuario_a_aceptar.decode())
            print(f"{VERDE}[+] Aceptaste la conexión con {usuario_a_aceptar.decode()}{RESET}")
            continue
 
        elif entrada.startswith("/rechazar "):
            usuario_a_rechazar = entrada.split(maxsplit=1)[1].strip().encode('utf-8')[:32]
            paquete_rechazar = construir_paquete(CODIGO_RECHAZADO, usuario=USUARIO, destino=usuario_a_rechazar)
            socket_cliente.sendall(paquete_rechazar)
            print(f"{ROJO}[-] Rechazaste la conexión con {usuario_a_rechazar.decode()}{RESET}")
            continue

        # Si no es comando, se trata como mensaje común
        mensaje_bytes = entrada.encode('utf-8')
        paquete = construir_paquete(CODIGO_MENSAJE, usuario=USUARIO, destino=destino, datos=mensaje_bytes)
        socket_cliente.sendall(paquete)
else:
    print(f"{ROJO}[!] Conexión fallida. Cerrando cliente.{RESET}")
    socket_cliente.close()