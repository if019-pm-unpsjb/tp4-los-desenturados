import socket
import threading
import time
import struct

# Códigos de tipo de paquete
CODIGO_SYN = 0
CODIGO_ACK = 1
CODIGO_MENSAJE = 2
CODIGO_FILE = 3,
CODIGO_FIN = 4,
CODIGO_ACEPTADO = 5,
CODIGO_RECHAZADO = 6


SERVIDOR = "127.0.0.1"
PUERTO = 7777
USUARIO = input("Usuario: ").strip().encode('utf-8')[:32]

usuarios_conectados = set()  

socket_cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    socket_cliente.connect((SERVIDOR, PUERTO))
except ConnectionRefusedError:
    print(f"[!] No se pudo conectar al servidor en {SERVIDOR}:{PUERTO}. ¿Está corriendo?")
    exit(1)

def construir_paquete(codigo, usuario=b"", destino=b"", datos=b""):
    usuario = usuario.ljust(32, b'\x00')[:32]
    destino = destino.ljust(32, b'\x00')[:32]
    longitud_datos = len(datos)
    datos = datos.ljust(4096, b'\x00')[:4096]

    formato_paquete = "i32s32si4096s" #buscar para entender
    return struct.pack(formato_paquete, codigo, usuario, destino, longitud_datos, datos)

def realizar_conexion():
    print("[*] Iniciando conexion...")

    # Paso 1: Enviar SYN
    paquete_syn = construir_paquete(CODIGO_SYN, usuario=USUARIO)
    socket_cliente.sendall(paquete_syn)

    respuesta = socket_cliente.recv(4196)
    if len(respuesta) < 4168:
        print("[!] Paquete de respuesta incompleto")
        return False

    # Desempaquetar respuesta
    codigo, usuario_resp, destino_resp, longitud_datos, datos = struct.unpack("i32s32si4096s", respuesta)
    if codigo == CODIGO_SYN:
        print("[*] Recibido ACK")
        # Paso 2: Enviar ACK
        paquete_ack = construir_paquete(CODIGO_ACK, usuario=USUARIO)
        socket_cliente.sendall(paquete_ack)
        time.sleep(0.2) #buscar si tiene relevancia
        return True
    else:
        print("[!] Error: se esperaba SYN pero se recibió código", codigo)
        return False

def escuchar_mensajes():
    while True:
        try:
            datos = socket_cliente.recv(4196)
            if not datos:
                print("Servidor desconectado")
                break


            codigo, usuario_emisor, usuario_destino, longitud_datos, contenido = struct.unpack("i32s32si4096s", datos)
            usuario_emisor = usuario_emisor.decode().strip()
            mensaje = contenido[:longitud_datos].decode(errors="ignore") #buscar que significa

            if codigo == CODIGO_MENSAJE:
                if usuario_emisor in usuarios_conectados:
                    print(f"[Mensaje de {usuario_emisor}]: {mensaje}")
                else:
                    print(f"\n[*] Nueva solicitud de conexión de '{usuario_emisor}'")
                    opcion = input(f"¿Aceptar conexión de {usuario_emisor}? (aceptar/rechazar): ").strip().lower()
                    if opcion == "aceptar": #agregar mas formas de escritura
                        # Enviar paquete de aceptación
                        paquete_aceptacion = construir_paquete(CODIGO_ACEPTADO, usuario=USUARIO, destino=usuario_emisor)
                        socket_cliente.sendall(paquete_aceptacion)
                        usuarios_conectados.add(usuario_emisor)
                        print(f"[+] Conexión aceptada. Ahora puedes recibir mensajes de {usuario_emisor}")
                    else:
                        print(f"[-] Conexión rechazada para {usuario_emisor}")
                  
            elif codigo == CODIGO_ACEPTADO:
                usuarios_conectados.add(usuario_emisor)
                print(f"{mensaje}")
            else:
                print(f"[Código desconocido {codigo} de {usuario_emisor}]: {mensaje}")

        except Exception as e:
            print(f"[!] Error al recibir mensaje: {e}")
            break


if realizar_conexion():
    threading.Thread(target=escuchar_mensajes, daemon=True).start()
    print("[*] Conexión establecida correctamente")

    while True:
        mensaje = input("Mensaje (o 'salir' para cerrar): ")
        if mensaje.lower() == "salir":  
            break


        destino = input("Enviar a (usuario destino): ").strip().encode('utf-8')[:32]
        mensaje_bytes = mensaje.encode('utf-8')
        paquete = construir_paquete(CODIGO_MENSAJE, usuario=USUARIO, destino=destino, datos=mensaje_bytes)
        socket_cliente.sendall(paquete)
else:
    print("[!] conexion fallida. Cerrando conexión.")
    socket_cliente.close()
