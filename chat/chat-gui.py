import socket
import threading
import struct
import tkinter as tk
from tkinter import scrolledtext, simpledialog, messagebox

# Códigos
CODIGO_SYN = 0
CODIGO_ACK = 1
CODIGO_MENSAJE = 2
CODIGO_FILE = 3
CODIGO_FIN = 4
CODIGO_ACEPTADO = 5
CODIGO_RECHAZADO = 6

# Conexión
SERVIDOR = "127.0.0.1"
PUERTO = 28008

# Cliente TCP
cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

usuarios_conectados = set()
USUARIO = None

def construir_paquete(codigo, usuario=b"", destino=b"", datos=b""):
    usuario = usuario.ljust(32, b'\x00')[:32]
    destino = destino.ljust(32, b'\x00')[:32]
    datos = datos + b'\x00' * (4096 - len(datos)) if len(datos) < 4096 else datos[:4096]
    return struct.pack("i32s32si4096s", codigo, usuario, destino, len(datos), datos)

def recv_exact(sock, size):
    buffer = b''
    while len(buffer) < size:
        parte = sock.recv(size - len(buffer))
        if not parte:
            return None
        buffer += parte
    return buffer

def escuchar():
    while True:
        datos = recv_exact(cliente, 4168)
        if datos is None:
            chat_area.insert(tk.END, "[!] Desconectado del servidor.\n")
            break
        codigo, usuario_emisor, usuario_destino, longitud_datos, contenido = struct.unpack("i32s32si4096s", datos)
        emisor = usuario_emisor.decode('utf-8').strip('\x00')
        mensaje = contenido[:longitud_datos].decode(errors="ignore")

        if codigo == CODIGO_MENSAJE:
            if emisor in usuarios_conectados:
                chat_area.insert(tk.END, f"[{emisor}] {mensaje}\n")
            else:
                chat_area.insert(tk.END, f"[Solicitud] Conexión de '{emisor}'. Escribí /aceptar {emisor} o /rechazar {emisor}\n")
        elif codigo == CODIGO_ACEPTADO:
            usuarios_conectados.add(emisor)
            chat_area.insert(tk.END, f"[+] Conexión aceptada con '{emisor}'. Ya podés chatear.\n")
        elif codigo == CODIGO_RECHAZADO:
            chat_area.insert(tk.END, f"[-] {emisor} rechazó la conexión.\n")

def enviar():
    destino = destino_entry.get().strip()
    mensaje = mensaje_entry.get().strip()

    if not destino or not mensaje:
        return

    if mensaje.startswith("/aceptar "):
        usuario_a_aceptar = mensaje.split()[1].strip()
        paquete = construir_paquete(CODIGO_ACEPTADO, usuario=USUARIO.encode(), destino=usuario_a_aceptar.encode())
        cliente.sendall(paquete)
        usuarios_conectados.add(usuario_a_aceptar)
        chat_area.insert(tk.END, f"[+] Aceptaste la conexión con {usuario_a_aceptar}\n")
        cliente.sendall(construir_paquete(CODIGO_MENSAJE, USUARIO.encode(), usuario_a_aceptar.encode(), b""))
    elif mensaje.startswith("/rechazar "):
        usuario_a_rechazar = mensaje.split()[1].strip()
        paquete = construir_paquete(CODIGO_RECHAZADO, usuario=USUARIO.encode(), destino=usuario_a_rechazar.encode())
        cliente.sendall(paquete)
        chat_area.insert(tk.END, f"[-] Rechazaste la conexión con {usuario_a_rechazar}\n")
    else:
        paquete = construir_paquete(CODIGO_MENSAJE, usuario=USUARIO.encode(), destino=destino.encode(), datos=mensaje.encode())
        cliente.sendall(paquete)
        chat_area.insert(tk.END, f"[Yo → {destino}] {mensaje}\n")

    mensaje_entry.delete(0, tk.END)

def conectar():
    global USUARIO
    USUARIO = simpledialog.askstring("Usuario", "Ingresá tu nombre de usuario:")
    if not USUARIO:
        exit()
    try:
        cliente.connect((SERVIDOR, PUERTO))
    except:
        messagebox.showerror("Error", "No se pudo conectar al servidor.")
        exit()

    # Handshake
    cliente.sendall(construir_paquete(CODIGO_SYN, usuario=USUARIO.encode()))
    respuesta = recv_exact(cliente, 4168)
    if not respuesta:
        messagebox.showerror("Error", "Servidor no responde.")
        exit()
    codigo, _, _, _, _ = struct.unpack("i32s32si4096s", respuesta)
    if codigo == CODIGO_SYN:
        cliente.sendall(construir_paquete(CODIGO_ACK, usuario=USUARIO.encode()))
    else:
        messagebox.showerror("Error", "Fallo el handshake con el servidor.")
        exit()

    threading.Thread(target=escuchar, daemon=True).start()

# GUI
ventana = tk.Tk()
ventana.title("Chat MAILU")

chat_area = scrolledtext.ScrolledText(ventana, width=60, height=20)
chat_area.pack(padx=10, pady=10)
chat_area.config(state=tk.NORMAL)

frame_abajo = tk.Frame(ventana)
frame_abajo.pack(padx=10, pady=5)

tk.Label(frame_abajo, text="Destinatario:").grid(row=0, column=0)
destino_entry = tk.Entry(frame_abajo, width=20)
destino_entry.grid(row=0, column=1)

mensaje_entry = tk.Entry(frame_abajo, width=40)
mensaje_entry.grid(row=1, column=0, columnspan=2, padx=5, pady=5)

boton_enviar = tk.Button(frame_abajo, text="Enviar", command=enviar)
boton_enviar.grid(row=1, column=2, padx=5)

conectar()
ventana.mainloop()
