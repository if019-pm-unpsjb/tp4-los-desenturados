import socket
import threading
import struct
import tkinter as tk
from tkinter import simpledialog, messagebox, scrolledtext, filedialog
import os

# Códigos
CODIGO_SYN = 0
CODIGO_ACK = 1
CODIGO_MENSAJE = 2
CODIGO_FILE = 3
CODIGO_FIN = 4
CODIGO_ACEPTADO = 5
CODIGO_RECHAZADO = 6
CODIGO_ERROR = 7


cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
areas_chat = {}  # contacto -> ScrolledText
# Conexión
SERVIDOR = "192.168.0.109"
PUERTO = 28008

listbox_conexiones = None  # Inicialización

# Cliente TCP
cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
usuarios_conectados = set()
usuarios_pendientes = set()
usuarios_pendientes_entrantes = set()
USUARIO = None


def construir_paquete(codigo, usuario=b"", destino=b"", datos=b""):
    datos = datos[:4096]
    longitud = len(datos)
    datos = datos + b'\x00' * (4096 - longitud)
    usuario = usuario.ljust(32, b'\x00')[:32]
    destino = destino.ljust(32, b'\x00')[:32]
    return struct.pack("i32s32si4096s", codigo, usuario, destino, longitud, datos)


def recv_exact(sock, size):
    buffer = b''
    while len(buffer) < size:
        parte = sock.recv(size - len(buffer))
        if not parte:
            return None
        buffer += parte
    return buffer


def actualizar_listas():

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


def aceptar_usuario(usuario):
    cliente.sendall(construir_paquete(CODIGO_ACEPTADO, USUARIO.encode(), usuario.encode()))
    usuarios_conectados.add(usuario)
    usuarios_pendientes.discard(usuario)
    actualizar_listas()
    if usuario not in areas_chat:
        area_nueva = scrolledtext.ScrolledText(frame_derecha, width=60, height=20, font=("Segoe UI", 10), bg="#f0f8ff")
        area_nueva.pack_forget()
        area_nueva.config(state=tk.DISABLED)
        areas_chat[usuario] = area_nueva


def rechazar_usuario(usuario):
    cliente.sendall(construir_paquete(CODIGO_RECHAZADO, USUARIO.encode(), usuario.encode()))
    usuarios_pendientes.discard(usuario)
    actualizar_listas()


def agregar_conexion():
    destino = simpledialog.askstring("Nueva conexión", "Nombre de usuario a contactar:")
    if not destino or destino == USUARIO:
        return
    cliente.sendall(construir_paquete(CODIGO_MENSAJE, USUARIO.encode(), destino.encode(), b""))
    usuarios_pendientes.add(destino)
    actualizar_listas()


def enviar_archivo():
    contacto = listbox_conexiones.get(tk.ACTIVE)
    if not contacto:
        return

    filepath = filedialog.askopenfilename()
    if not filepath:
        return

    area = areas_chat.get(contacto)
    if not area:
        return

    with open(filepath, "rb") as f:
        block_num = 1
        while True:
            bloque = f.read(4096)
            if not bloque:
                break
            paquete = construir_paquete(CODIGO_FILE, USUARIO.encode(), contacto.encode(), bloque)
            cliente.sendall(paquete)

            area.config(state=tk.NORMAL)
            area.insert(tk.END, f"[Archivo] Enviando bloque {block_num} de tamaño {len(bloque)} bytes\n")
            area.tag_add("der", "end-2l", "end-1l")
            area.tag_config("der", justify="right")
            area.config(state=tk.DISABLED)
            block_num += 1


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
            break

        codigo, usuario_emisor, usuario_destino, longitud_datos, contenido = struct.unpack("i32s32si4096s", datos)
        emisor = usuario_emisor.decode('utf-8').strip('\x00')
        raw = contenido[:longitud_datos]
        mensaje = raw.decode('utf-8', errors="ignore").strip() if longitud_datos > 0 else ""

        if emisor not in areas_chat:
            area_nueva = scrolledtext.ScrolledText(frame_derecha, width=60, height=20, font=("Segoe UI", 10), bg="#f0f8ff")
            area_nueva.pack_forget()
            area_nueva.config(state=tk.DISABLED)
            areas_chat[emisor] = area_nueva

        area = areas_chat[emisor]

        if codigo == CODIGO_MENSAJE:
            if emisor not in usuarios_conectados:
                usuarios_pendientes.add(emisor)
                usuarios_pendientes_entrantes.add(emisor)
                actualizar_listas()
            area.config(state=tk.NORMAL)
            area.insert(tk.END, f"{emisor}: {mensaje}\n")
            area.tag_add("izq", "end-2l", "end-1l")
            area.tag_config("izq", justify="left")
            area.config(state=tk.DISABLED)

        elif codigo == CODIGO_ACEPTADO:
            chat_area.config(state=tk.NORMAL)
            usuarios_conectados.add(emisor)
            usuarios_pendientes.discard(emisor)
            actualizar_listas()

        elif codigo == CODIGO_RECHAZADO:
            usuarios_pendientes.discard(emisor)
            actualizar_listas()

        elif codigo == CODIGO_FILE:
            filename = f"archivo_de_{emisor}.bin"
            with open(filename, "ab") as f:
                f.write(contenido[:longitud_datos])
            area.config(state=tk.NORMAL)
            area.insert(tk.END, f"[Archivo] Recibido bloque de {longitud_datos} bytes de {emisor}\n")
            area.tag_add("izq", "end-2l", "end-1l")
            area.tag_config("izq", justify="left")
            area.config(state=tk.DISABLED)

        elif codigo == CODIGO_ERROR:
            ultimo = list(usuarios_pendientes)[-1]
            usuarios_pendientes.discard(ultimo)
            actualizar_listas()
            messagebox.showerror("Error", mensaje)



def enviar():
    contacto = listbox_conexiones.get(tk.ACTIVE)
    mensaje = mensaje_entry.get().strip()
    if not contacto or not mensaje:
        return

    cliente.sendall(construir_paquete(CODIGO_MENSAJE, USUARIO.encode(), contacto.encode(), mensaje.encode()))
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

    if contacto not in areas_chat:
        area_nueva = scrolledtext.ScrolledText(frame_derecha, width=60, height=20, font=("Segoe UI", 10), bg="#f0f8ff")
        area_nueva.pack_forget()
        area_nueva.config(state=tk.DISABLED)
        areas_chat[contacto] = area_nueva

    area = areas_chat[contacto]
    area.config(state=tk.NORMAL)
    area.insert(tk.END, f"{mensaje}\n")
    area.tag_add("der", "end-2l", "end-1l")
    area.tag_config("der", justify="right")
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

    label_usuario_logeado.config(text=f"Usuario logueado: {USUARIO}")
    cliente.sendall(construir_paquete(CODIGO_SYN, usuario=USUARIO.encode()))
    respuesta = recv_exact(cliente, 4168)
    if not respuesta:
        messagebox.showerror("Error", "Servidor no responde.")
        exit()

    codigo, usuario_emisor, usuario_destino, longitud_datos, contenido = struct.unpack("i32s32si4096s", respuesta)
    if codigo == CODIGO_SYN:
        cliente.sendall(construir_paquete(CODIGO_ACK, usuario=USUARIO.encode()))
    elif codigo == CODIGO_ERROR:
        mensaje = contenido[:longitud_datos].decode(errors="ignore").strip()
        messagebox.showerror("Error", mensaje)
        ventana.destroy()
        exit()

    threading.Thread(target=escuchar, daemon=True).start()

ventana = tk.Tk()
ventana.title("Chat MAILU")

frame_principal = tk.Frame(ventana)
frame_principal.pack(padx=10, pady=10)

frame_izquierda = tk.Frame(frame_principal)
frame_izquierda.pack(side=tk.LEFT, padx=(0, 10), fill=tk.Y)

frame_aceptadas = tk.Frame(frame_izquierda)
frame_aceptadas.pack(fill=tk.BOTH, expand=True)
tk.Label(frame_izquierda, text="Conexiones aceptadas").pack()
listbox_conexiones = tk.Listbox(frame_izquierda, width=25)
listbox_conexiones.pack(fill=tk.BOTH, expand=True)
listbox_conexiones.bind("<<ListboxSelect>>", lambda e: mostrar_chat_para(listbox_conexiones.get(tk.ACTIVE)))
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

frame_pendientes = tk.Frame(frame_izquierda)
frame_pendientes.pack(fill=tk.BOTH, expand=True)

cabecera = tk.Frame(frame_pendientes)
cabecera.pack(fill=tk.X)
tk.Label(cabecera, text="Conexiones pendientes").pack(side=tk.LEFT)
tk.Button(cabecera, text="+ Agregar", command=agregar_conexion).pack(side=tk.RIGHT)

canvas = tk.Canvas(frame_pendientes, height=150)
scrollbar = tk.Scrollbar(frame_pendientes, orient="vertical", command=canvas.yview)
frame_pendientes_usuarios = tk.Frame(canvas)
frame_pendientes_usuarios.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
canvas.create_window((0, 0), window=frame_pendientes_usuarios, anchor="nw")
canvas.configure(yscrollcommand=scrollbar.set)
canvas.pack(side="left", fill="both", expand=True)
scrollbar.pack(side="right", fill="y")

frame_derecha = tk.Frame(frame_principal)
frame_derecha.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
label_usuario_logeado = tk.Label(frame_derecha, text="Usuario logueado: ", font=("Arial", 10, "bold"))
label_usuario_logeado.pack(anchor='w', padx=5, pady=(0, 5))

frame_abajo = tk.Frame(ventana)
frame_abajo.pack(padx=10, pady=5)
mensaje_entry = tk.Entry(frame_abajo, width=60)
mensaje_entry.grid(row=0, column=0, padx=5)
boton_enviar = tk.Button(frame_abajo, text="Enviar", command=enviar)
boton_enviar.grid(row=0, column=1)
boton_archivo = tk.Button(frame_abajo, text="Archivo", command=enviar_archivo)
boton_archivo.grid(row=0, column=2, padx=5)

conectar()
ventana.mainloop()
