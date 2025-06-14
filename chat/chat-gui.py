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
CODIGO_ERROR = 7

# Conexión
SERVIDOR = "192.168.0.106"
PUERTO = 28008

# Cliente TCP
cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
areas_chat = {}  # clave: nombre del contacto, valor: widget ScrolledText
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

def actualizar_lista_conexiones():
    listbox_conexiones.delete(0, tk.END)
    for usuario in sorted(usuarios_conectados):
        listbox_conexiones.insert(tk.END, usuario)

def mostrar_chat_para(contacto):
    for area in areas_chat.values():
        area.pack_forget()
    if contacto not in areas_chat:
        area_nueva = scrolledtext.ScrolledText(frame_derecha, width=60, height=20, font=("Segoe UI", 10), bg="#f0f8ff")
        area_nueva.pack()
        area_nueva.config(state=tk.DISABLED)
        areas_chat[contacto] = area_nueva
    else:
        areas_chat[contacto].pack()

def escuchar():
    while True:
        datos = recv_exact(cliente, 4168)
        if datos is None:
            for area in areas_chat.values():
                area.config(state=tk.NORMAL)
                area.insert(tk.END, "[!] Desconectado del servidor.\n")
                area.config(state=tk.DISABLED)
            break

        codigo, usuario_emisor, usuario_destino, longitud_datos, contenido = struct.unpack("i32s32si4096s", datos)
        emisor = usuario_emisor.decode('utf-8').strip('\x00')
        mensaje = contenido[:longitud_datos].split(b'\x00')[0].decode('utf-8', errors="ignore").strip()


        if codigo == CODIGO_MENSAJE:
            if emisor not in areas_chat:
                area_nueva = scrolledtext.ScrolledText(frame_derecha, width=60, height=20, font=("Segoe UI", 10), bg="#f0f8ff")
                area_nueva.pack_forget()
                area_nueva.config(state=tk.DISABLED)
                areas_chat[emisor] = area_nueva

            area = areas_chat[emisor]
            area.config(state=tk.NORMAL)
            area.insert(tk.END, f"[{emisor}] {mensaje}\n")
            area.config(state=tk.DISABLED)

        elif codigo == CODIGO_ACEPTADO:
            usuarios_conectados.add(emisor)
            actualizar_lista_conexiones()

            if emisor not in areas_chat:
                area_nueva = scrolledtext.ScrolledText(frame_derecha, width=60, height=20, font=("Segoe UI", 10), bg="#f0f8ff")
                area_nueva.pack_forget()
                area_nueva.config(state=tk.DISABLED)
                areas_chat[emisor] = area_nueva

        elif codigo == CODIGO_RECHAZADO:
            messagebox.showinfo("Conexión rechazada", f"{emisor} rechazó la conexión.")
        elif codigo == CODIGO_ERROR:
            messagebox.showerror("Error", mensaje)

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
        actualizar_lista_conexiones()
        return

    elif mensaje.startswith("/rechazar "):
        usuario_a_rechazar = mensaje.split()[1].strip()
        paquete = construir_paquete(CODIGO_RECHAZADO, usuario=USUARIO.encode(), destino=usuario_a_rechazar.encode())
        cliente.sendall(paquete)
        return

    # Mensaje normal
    paquete = construir_paquete(CODIGO_MENSAJE, usuario=USUARIO.encode(), destino=destino.encode(), datos=mensaje.encode())
    cliente.sendall(paquete)

    if destino not in areas_chat:
        area_nueva = scrolledtext.ScrolledText(frame_derecha, width=60, height=20, font=("Segoe UI", 10), bg="#f0f8ff")
        area_nueva.pack_forget()
        area_nueva.config(state=tk.DISABLED)
        areas_chat[destino] = area_nueva

    area = areas_chat[destino]
    area.config(state=tk.NORMAL)
    area.insert(tk.END, f"[Yo → {destino}] {mensaje}\n")
    area.config(state=tk.DISABLED)

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

    global label_usuario_logeado
    label_usuario_logeado.config(text=f"Usuario logueado: {USUARIO}")

    cliente.sendall(construir_paquete(CODIGO_SYN, usuario=USUARIO.encode()))
    respuesta = recv_exact(cliente, 4168)
    if not respuesta:
        messagebox.showerror("Error", "Servidor no responde.")
        exit()

    codigo, usuario_emisor, usuario_destino, longitud_datos, contenido = struct.unpack("i32s32si4096s", respuesta)
    mensaje = contenido[:longitud_datos].decode(errors="ignore").rstrip()

    if codigo == CODIGO_SYN:
        cliente.sendall(construir_paquete(CODIGO_ACK, usuario=USUARIO.encode()))
    if codigo == CODIGO_ERROR:
        messagebox.showerror("Error", mensaje)
        ventana.destroy()
        exit()
    threading.Thread(target=escuchar, daemon=True).start()

# GUI
ventana = tk.Tk()
ventana.title("Chat MAILU")

frame_principal = tk.Frame(ventana)
frame_principal.pack(padx=10, pady=10)

# Izquierda: conexiones aceptadas
frame_izquierda = tk.Frame(frame_principal)
frame_izquierda.pack(side=tk.LEFT, padx=(0, 10), fill=tk.Y)

tk.Label(frame_izquierda, text="Conexiones aceptadas").pack()
listbox_conexiones = tk.Listbox(frame_izquierda, width=25)
listbox_conexiones.pack(fill=tk.BOTH, expand=True)
listbox_conexiones.bind("<<ListboxSelect>>", lambda e: mostrar_chat_para(listbox_conexiones.get(tk.ACTIVE)))

# Derecha: chat
frame_derecha = tk.Frame(frame_principal)
frame_derecha.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
label_usuario_logeado = tk.Label(frame_derecha, text="Usuario logueado: ", font=("Arial", 10, "bold"))
label_usuario_logeado.pack(anchor='w', padx=5, pady=(0,5))

# Abajo: input y botones
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
