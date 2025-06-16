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


listbox_conexiones = None  # Inicialización

# Cliente TCP
cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
areas_chat = {}  
# Conexión
SERVIDOR = "127.0.0.1"

PUERTO = 28008

listbox_conexiones = None  # Inicialización

# Cliente TCP
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


from pathlib import Path

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

    # Obtener solo el nombre (sin ruta)
    nombre_archivo = Path(filepath).name
    nombre_bytes = nombre_archivo.encode("utf-8")

    # Enviar primer paquete con el nombre del archivo
    paquete_nombre = construir_paquete(
        CODIGO_FILE,
        usuario=USUARIO.encode(),
        destino=contacto.encode(),
        datos=nombre_bytes
    )
    cliente.sendall(paquete_nombre)

    area.config(state=tk.NORMAL)
    area.insert(tk.END, f"[Archivo] Enviando archivo: {nombre_archivo}\n")

    # Ahora enviar los bloques binarios del archivo
    with open(filepath, "rb") as f:
        block_num = 1
        while True:
            bloque = f.read(4096)
            if not bloque:
                break
            paquete = construir_paquete(CODIGO_FILE, USUARIO.encode(), contacto.encode(), bloque)
            cliente.sendall(paquete)

            area.insert(tk.END, f"[Archivo] Enviado bloque {block_num} ({len(bloque)} bytes)\n")
            area.tag_config("der", justify="right")
            area.tag_add("der", "end-2l", "end-1l")
            area.config(state=tk.DISABLED)
            block_num += 1

    area.config(state=tk.NORMAL)
    area.insert(tk.END, f"[✓] Archivo '{nombre_archivo}' enviado completo\n")
    area.tag_add("der", "end-2l", "end-1l")
    area.tag_config("der", justify="right")
    area.config(state=tk.DISABLED)

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
            usuarios_conectados.add(emisor)
            usuarios_pendientes.discard(emisor)
            actualizar_listas()

        elif codigo == CODIGO_RECHAZADO:
            usuarios_pendientes.discard(emisor)
            actualizar_listas()
            
        elif codigo == CODIGO_FILE:
            # Primer mensaje: nombre del archivo
            nombre_archivo = contenido[:longitud_datos].decode(errors="replace")
            archivo_recibido = f"archivo_de_{emisor}_{nombre_archivo}"
            area.config(state=tk.NORMAL)
            area.insert(tk.END, f"[Archivo] Recibiendo archivo '{nombre_archivo}' de {emisor}\n")
            with open(archivo_recibido, "wb") as f:
                while True:
                    datos_archivo = recv_exact(cliente, 4168)
                    if datos_archivo is None:
                        messagebox.showerror("Error de conexión", "Conexión cerrada inesperadamente")
                        area.insert(tk.END, "[✗] Error: conexión cerrada inesperadamente.\n")
                        break
                    _, _, _, longitud_datos, contenido = struct.unpack("i32s32si4096s", datos_archivo)
                    f.write(contenido[:longitud_datos]) 
                    area.insert(tk.END, f"[Archivo] Bloque de {longitud_datos} bytes recibido...\n")
                    if longitud_datos < 4096:  # Último bloque
                        area.insert(tk.END, f"[✓] Archivo recibido completo: {archivo_recibido}\n")
                        break
            area.tag_add("izq", "end-2l", "end-1l")
            area.tag_config("izq", justify="left")
            area.config(state=tk.DISABLED)


        elif codigo == CODIGO_ERROR:
            if mensaje.startswith("El usuario ") and "se ha desconectado" in mensaje:
                usuario_desconectado = mensaje.split(" ")[2]

                if usuario_desconectado in usuarios_conectados:
                    usuarios_conectados.discard(usuario_desconectado)

                if usuario_desconectado in areas_chat:
                    area = areas_chat[usuario_desconectado]
                    area.config(state=tk.NORMAL)
                    area.insert(tk.END, f"[✗] El usuario '{usuario_desconectado}' se ha desconectado.\n")
                    area.config(state=tk.DISABLED)

                actualizar_listas()
                messagebox.showinfo("Desconexión", f"{usuario_desconectado} se ha desconectado. Ya no podés enviarle mensajes.")
            
            if mensaje.startswith("El usuario ") and "no esta en linea" in mensaje:
                ultimo_usuario= list(usuarios_pendientes)[-1]
                usuarios_pendientes.discard(ultimo_usuario)
                actualizar_listas()
                messagebox.showerror("Error", mensaje)
            
            else:
                # Asumimos que es un error por nombre en uso u otro
                messagebox.showerror("Error", mensaje)


def enviar():
    contacto = listbox_conexiones.get(tk.ACTIVE)
    mensaje = mensaje_entry.get().strip()
    if not contacto or not mensaje:
        return
    if contacto not in usuarios_conectados:
        messagebox.showwarning("Contacto no disponible", f"No podés enviar mensajes a '{contacto}' porque ya no está conectado.")
        return
    cliente.sendall(construir_paquete(CODIGO_MENSAJE, USUARIO.encode(), contacto.encode(), mensaje.encode()))

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
