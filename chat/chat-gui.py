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
SERVIDOR = "192.168.0.109"
PUERTO = 28008

listbox_conexiones = None  # Inicialización

# Cliente TCP
cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
usuarios_pendientes = set()
usuarios_pendientes_entrantes = set()  # Solo a los que yo puedo aceptar o rechazar
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


def actualizar_listas():
    # Conexiones aceptadas
    listbox_conexiones.delete(0, tk.END)
    for usuario in sorted(usuarios_conectados):
        listbox_conexiones.insert(tk.END, usuario)

    # Limpiar frame pendientes
    for widget in frame_pendientes_usuarios.winfo_children():
        widget.destroy()

    # Mostrar pendientes
    for usuario in sorted(usuarios_pendientes):
        fila = tk.Frame(frame_pendientes_usuarios)
        fila.pack(fill=tk.X, pady=1, padx=2)

        lbl = tk.Label(fila, text=usuario, width=12, anchor="w")
        lbl.pack(side=tk.LEFT)

        if usuario in usuarios_pendientes_entrantes:
            btn_aceptar = tk.Button(fila, text="✓", fg="green", width=2, command=lambda u=usuario: aceptar_usuario(u))
            btn_aceptar.pack(side=tk.LEFT, padx=2)

            btn_rechazar = tk.Button(fila, text="✗", fg="red", width=2, command=lambda u=usuario: rechazar_usuario(u))
            btn_rechazar.pack(side=tk.LEFT)
        else:
            lbl_pendiente = tk.Label(fila, text="(pendiente)", fg="gray")
            lbl_pendiente.pack(side=tk.LEFT, padx=4)


def aceptar_usuario(usuario):
    paquete = construir_paquete(CODIGO_ACEPTADO, usuario=USUARIO.encode(), destino=usuario.encode())
    cliente.sendall(paquete)
    usuarios_conectados.add(usuario)
    usuarios_pendientes.discard(usuario)
    actualizar_listas()
    chat_area.config(state=tk.NORMAL)
    chat_area.insert(tk.END, f"[+] Aceptaste la conexión con {usuario}\n")
    chat_area.config(state=tk.DISABLED)
    chat_area.yview(tk.END)

def rechazar_usuario(usuario):
    paquete = construir_paquete(CODIGO_RECHAZADO, usuario=USUARIO.encode(), destino=usuario.encode())
    cliente.sendall(paquete)
    usuarios_pendientes.discard(usuario)
    actualizar_listas()
    chat_area.config(state=tk.NORMAL)
    chat_area.insert(tk.END, f"[-] Rechazaste la conexión con {usuario}\n")
    chat_area.config(state=tk.DISABLED)
    chat_area.yview(tk.END)



def escuchar():
    while True:
        datos = recv_exact(cliente, 4168)
        if datos is None:
            chat_area.insert(tk.END, "[!] Desconectado del servidor.\n")
            break
        codigo, usuario_emisor, usuario_destino, longitud_datos, contenido = struct.unpack("i32s32si4096s", datos)
        emisor = usuario_emisor.decode('utf-8').strip('\x00')
        mensaje = contenido[:longitud_datos].decode(errors="ignore").rstrip()
        
        if codigo == CODIGO_MENSAJE:
            chat_area.config(state=tk.NORMAL)
            if emisor in usuarios_conectados:
                chat_area.insert(tk.END, f"[{emisor}] {mensaje}\n")
            else:
                chat_area.insert(tk.END, f"[Solicitud] Conexión de '{emisor}'. Escribí /aceptar {emisor} o /rechazar {emisor}\n")
                usuarios_pendientes.add(emisor)
                usuarios_pendientes_entrantes.add(emisor)
                actualizar_listas()
            chat_area.config(state=tk.DISABLED)
            chat_area.yview(tk.END)
        elif codigo == CODIGO_ACEPTADO:
            chat_area.config(state=tk.NORMAL)
            usuarios_conectados.add(emisor)
            usuarios_pendientes.discard(emisor)
            actualizar_listas()
            chat_area.insert(tk.END, f"[+] Conexión aceptada con '{emisor}'. Ya podés chatear.\n")
            chat_area.config(state=tk.DISABLED)
            chat_area.yview(tk.END)
        elif codigo == CODIGO_RECHAZADO:
            chat_area.config(state=tk.NORMAL)
            usuarios_pendientes.discard(emisor)
            chat_area.insert(tk.END, f"[-] {emisor} rechazó la conexión.\n")
            chat_area.config(state=tk.DISABLED)
            chat_area.yview(tk.END)

        elif codigo == CODIGO_ERROR:  # CODIGO_ERROR
            chat_area.config(state=tk.NORMAL)
            chat_area.insert(tk.END, f"[ERROR] {mensaje}\n")
            chat_area.config(state=tk.DISABLED)
            chat_area.see(tk.END)
            messagebox.showerror("Error", mensaje)        
            

def enviar():
    destino = destino_entry.get().strip()
    mensaje = mensaje_entry.get().strip()

    if not destino or not mensaje:
        return

    """ if mensaje.startswith("/aceptar "):
        usuario_a_aceptar = mensaje.split()[1].strip()
        paquete = construir_paquete(CODIGO_ACEPTADO, usuario=USUARIO.encode(), destino=usuario_a_aceptar.encode())
        cliente.sendall(paquete)
        usuarios_conectados.add(usuario_a_aceptar)
        usuarios_pendientes.discard(usuario_a_aceptar)
        actualizar_listas()
        chat_area.insert(tk.END, f"[+] Aceptaste la conexión con {usuario_a_aceptar}\n")
        cliente.sendall(construir_paquete(CODIGO_MENSAJE, USUARIO.encode(), usuario_a_aceptar.encode(), b""))
    elif mensaje.startswith("/rechazar "):
        usuario_a_rechazar = mensaje.split()[1].strip()
        paquete = construir_paquete(CODIGO_RECHAZADO, usuario=USUARIO.encode(), destino=usuario_a_rechazar.encode())
        cliente.sendall(paquete)
        usuarios_pendientes.discard(usuario_a_rechazar)
        actualizar_listas() 
        chat_area.insert(tk.END, f"[-] Rechazaste la conexión con {usuario_a_rechazar}\n")
    else: """
    paquete = construir_paquete(CODIGO_MENSAJE, usuario=USUARIO.encode(), destino=destino.encode(), datos=mensaje.encode())
    cliente.sendall(paquete)
    chat_area.config(state=tk.NORMAL)
    chat_area.insert(tk.END, f"[Yo → {destino}] {mensaje}\n")
    chat_area.config(state=tk.DISABLED)
    chat_area.yview(tk.END)
    if destino not in usuarios_conectados:
        usuarios_pendientes.add(destino)
    actualizar_listas()

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
    # Handshake
    cliente.sendall(construir_paquete(CODIGO_SYN, usuario=USUARIO.encode()))
    respuesta = recv_exact(cliente, 4168)
    if not respuesta:
        messagebox.showerror("Error", "Servidor no responde.")
        exit()
    codigo, usuario_emisor, usuario_destino, longitud_datos, contenido = struct.unpack("i32s32si4096s", respuesta)
    mensaje = contenido[:longitud_datos].decode(errors="ignore").rstrip()
            
    if codigo == CODIGO_SYN:
        cliente.sendall(construir_paquete(CODIGO_ACK, usuario=USUARIO.encode()))
    if codigo == CODIGO_ERROR:  # CODIGO_ERROR
        chat_area.config(state=tk.NORMAL)
        chat_area.insert(tk.END, f"[ERROR] {mensaje}\n")
        chat_area.config(state=tk.DISABLED)
        chat_area.see(tk.END)
        messagebox.showerror("Error", mensaje)
        ventana.destroy()
        exit()
        return
    threading.Thread(target=escuchar, daemon=True).start()

# GUI
ventana = tk.Tk()
ventana.title("Chat MAILU")

frame_principal = tk.Frame(ventana)
frame_principal.pack(padx=10, pady=10)

# Panel izquierdo: conexiones aceptadas
frame_izquierda = tk.Frame(frame_principal)
frame_izquierda.pack(side=tk.LEFT, padx=(0, 10), fill=tk.Y)

frame_aceptadas = tk.Frame(frame_izquierda)
frame_aceptadas.pack(fill=tk.BOTH, expand=True)
tk.Label(frame_izquierda, text="Conexiones aceptadas").pack()
listbox_conexiones = tk.Listbox(frame_izquierda, width=25)
listbox_conexiones.pack(fill=tk.BOTH, expand=True)
label_usuario_logeado = None  # antes del mainloop

# Subframe para conexiones pendientes
frame_pendientes = tk.Frame(frame_izquierda)
frame_pendientes.pack(fill=tk.BOTH, expand=True)
tk.Label(frame_pendientes, text="Conexiones pendientes").pack()

# Scrollable frame para los pendientes
canvas = tk.Canvas(frame_pendientes, height=150)
scrollbar = tk.Scrollbar(frame_pendientes, orient="vertical", command=canvas.yview)
frame_pendientes_usuarios = tk.Frame(canvas)

frame_pendientes_usuarios.bind(
    "<Configure>",
    lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
)

canvas.create_window((0, 0), window=frame_pendientes_usuarios, anchor="nw")
canvas.configure(yscrollcommand=scrollbar.set)

canvas.pack(side="left", fill="both", expand=True)
scrollbar.pack(side="right", fill="y")

# Panel derecho: chat
frame_derecha = tk.Frame(frame_principal)
frame_derecha.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
label_usuario_logeado = tk.Label(frame_derecha, text="Usuario logueado: ", font=("Arial", 10, "bold"))
label_usuario_logeado.pack(anchor='w', padx=5, pady=(0,5))


chat_area = scrolledtext.ScrolledText(frame_derecha, width=60, height=20)
chat_area.pack()
chat_area.config(state=tk.DISABLED)


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
