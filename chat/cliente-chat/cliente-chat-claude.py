import socket
import struct
import threading
import os
from typing import Optional

class MessagingClient:
    # Códigos de operación según la documentación
    SYN = 0
    ACK = 1
    MSG = 2
    FILE_CODE = 3
    FIN = 4
    ACEPTADO = 5
    RECHAZADO = 6
    ERROR = 7
    
    # Tamaños de campos según protocolo
    PACKET_SIZE = 4168  # 4 + 32 + 32 + 4 + 4096
    CODE_SIZE = 4
    USER_SIZE = 32
    DEST_SIZE = 32
    LENGTH_SIZE = 4
    DATA_SIZE = 4096
    
    def __init__(self, server_host='localhost', server_port=6969):
        self.server_host = server_host
        self.server_port = server_port
        self.socket = None
        self.username = ""
        self.connected = False
        self.receiving_files = {}  # Para manejar archivos entrantes
        
    def create_packet(self, code: int, user: str, dest: str, data: bytes) -> bytes:
        """Crea un paquete según el formato especificado"""
        # Asegurar que los strings no excedan el tamaño
        user_bytes = user.encode('utf-8')[:self.USER_SIZE].ljust(self.USER_SIZE, b'\x00')
        dest_bytes = dest.encode('utf-8')[:self.DEST_SIZE].ljust(self.DEST_SIZE, b'\x00')
        
        # Limitar datos a 4096 bytes
        if len(data) > self.DATA_SIZE:
            data = data[:self.DATA_SIZE]
        
        length = len(data)
        
        # Crear el paquete: código(4) + usuario(32) + destino(32) + longitud(4) + datos(4096)
        packet = struct.pack('<I', code)  # Código (little endian)
        packet += user_bytes             # Usuario (32 bytes)
        packet += dest_bytes             # Destino (32 bytes)
        packet += struct.pack('<I', length)  # Longitud (little endian)
        packet += data.ljust(self.DATA_SIZE, b'\x00')  # Datos rellenados a 4096 bytes
        
        return packet
    
    def parse_packet(self, packet: bytes) -> tuple:
        """Parsea un paquete recibido"""
        if len(packet) != self.PACKET_SIZE:
            raise ValueError(f"Tamaño de paquete inválido: {len(packet)}")
        
        # Extraer campos
        code = struct.unpack('<I', packet[0:4])[0]
        user = packet[4:36].rstrip(b'\x00').decode('utf-8')
        dest = packet[36:68].rstrip(b'\x00').decode('utf-8')
        length = struct.unpack('<I', packet[68:72])[0]
        data = packet[72:72+length] if length > 0 else b''
        
        return code, user, dest, length, data
    
    def is_valid_ip(self, ip: str) -> bool:
        """Valida si una IP es válida"""
        try:
            socket.inet_aton(ip)
            return True
        except socket.error:
            return False
    
    def connect_to_server(self, username: str) -> bool:
        """Establece conexión con el servidor"""
        try:
            print(f"Intentando conectar a {self.server_host}:{self.server_port}...")
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)  # Timeout de 10 segundos para la conexión
            self.socket.connect((self.server_host, self.server_port))
            self.socket.settimeout(None)  # Quitar timeout después de conectar
            
            # Enviar SYN con nombre de usuario
            syn_packet = self.create_packet(self.SYN, username, "", b"")
            self.socket.send(syn_packet)
            
            # Esperar respuesta del servidor
            response = self.socket.recv(self.PACKET_SIZE)
            code, user, dest, length, data = self.parse_packet(response)
            
            if code == self.SYN:
                # Servidor acepta, enviar ACK
                ack_packet = self.create_packet(self.ACK, username, "", b"")
                self.socket.send(ack_packet)
                self.username = username
                self.connected = True
                print(f"✓ Conectado como {username} al servidor {self.server_host}:{self.server_port}")
                
                # Iniciar hilo para recibir mensajes
                receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
                receive_thread.start()
                
                return True
            elif code == self.ERROR:
                error_msg = data.decode('utf-8') if data else "Error desconocido"
                print(f"✗ Error de conexión: {error_msg}")
                self.socket.close()
                return False
        except socket.timeout:
            print(f"✗ Timeout conectando al servidor {self.server_host}:{self.server_port}")
            if self.socket:
                self.socket.close()
            return False
        except ConnectionRefusedError:
            print(f"✗ Conexión rechazada por {self.server_host}:{self.server_port}")
            if self.socket:
                self.socket.close()
            return False
        except Exception as e:
            print(f"✗ Error conectando al servidor: {e}")
            if self.socket:
                self.socket.close()
            return False
    
    def receive_messages(self):
        """Hilo para recibir mensajes del servidor"""
        while self.connected:
            try:
                packet = self.socket.recv(self.PACKET_SIZE)
                if not packet:
                    break
                
                code, user, dest, length, data = self.parse_packet(packet)
                
                if code == self.MSG:
                    # Mensaje de texto
                    if user == "":  # Solicitud de aceptación
                        print(f"\n📩 Solicitud de conexión de {dest}")
                        print("Responde con: /accept {usuario} o /reject {usuario}")
                    else:
                        message = data.decode('utf-8')
                        print(f"\n💬 {user}: {message}")
                
                elif code == self.FILE_CODE:
                    self.handle_file_packet(user, data)
                
                elif code == self.ACEPTADO:
                    print(f"✓ {user} aceptó tu solicitud de conexión")
                
                elif code == self.RECHAZADO:
                    print(f"✗ {user} rechazó tu solicitud de conexión")
                
                elif code == self.ERROR:
                    error_msg = data.decode('utf-8') if data else "Error desconocido"
                    print(f"✗ Error del servidor: {error_msg}")
                    
            except Exception as e:
                if self.connected:
                    print(f"Error recibiendo mensajes: {e}")
                break
    
    def handle_file_packet(self, sender: str, data: bytes):
        """Maneja paquetes de archivo"""
        if sender not in self.receiving_files:
            # Primer paquete: nombre del archivo
            filename = data.decode('utf-8').strip()
            output_filename = f"{filename}_de_{sender}_{filename.split('.')[-1] if '.' in filename else 'bin'}"
            self.receiving_files[sender] = {
                'filename': output_filename,
                'file': open(output_filename, 'wb'),
                'total_received': 0
            }
            print(f"📁 Recibiendo archivo '{filename}' de {sender}...")
        else:
            # Paquetes siguientes: contenido del archivo
            file_info = self.receiving_files[sender]
            file_info['file'].write(data)
            file_info['total_received'] += len(data)
            
            # Si el paquete es menor a 4096 bytes, es el último
            if len(data) < self.DATA_SIZE:
                file_info['file'].close()
                print(f"✓ Archivo '{file_info['filename']}' recibido completamente ({file_info['total_received']} bytes)")
                del self.receiving_files[sender]
    
    def send_message(self, dest_user: str, message: str):
        """Envía un mensaje a otro usuario"""
        if not self.connected:
            print("✗ No estás conectado")
            return
        
        try:
            data = message.encode('utf-8')
            packet = self.create_packet(self.MSG, self.username, dest_user, data)
            self.socket.send(packet)
        except Exception as e:
            print(f"Error enviando mensaje: {e}")
    
    def send_file(self, dest_user: str, filepath: str):
        """Envía un archivo a otro usuario"""
        if not self.connected:
            print("✗ No estás conectado")
            return
        
        if not os.path.exists(filepath):
            print(f"✗ Archivo no encontrado: {filepath}")
            return
        
        try:
            filename = os.path.basename(filepath)
            
            # Enviar primer paquete con nombre del archivo
            name_packet = self.create_packet(self.FILE_CODE, self.username, dest_user, filename.encode('utf-8'))
            self.socket.send(name_packet)
            
            # Enviar contenido del archivo en bloques
            with open(filepath, 'rb') as f:
                bytes_sent = 0
                while True:
                    chunk = f.read(self.DATA_SIZE)
                    if not chunk:
                        break
                    
                    file_packet = self.create_packet(self.FILE_CODE, self.username, dest_user, chunk)
                    self.socket.send(file_packet)
                    bytes_sent += len(chunk)
                    
                    if len(chunk) < self.DATA_SIZE:  # Último bloque
                        break
            
            print(f"✓ Archivo '{filename}' enviado ({bytes_sent} bytes)")
            
        except Exception as e:
            print(f"Error enviando archivo: {e}")
    
    def accept_connection(self, user: str):
        """Acepta conexión de otro usuario"""
        try:
            packet = self.create_packet(self.ACEPTADO, self.username, user, b"")
            self.socket.send(packet)
            print(f"✓ Conexión con {user} aceptada")
        except Exception as e:
            print(f"Error aceptando conexión: {e}")
    
    def reject_connection(self, user: str):
        """Rechaza conexión de otro usuario"""
        try:
            packet = self.create_packet(self.RECHAZADO, self.username, user, b"")
            self.socket.send(packet)
            print(f"✗ Conexión con {user} rechazada")
        except Exception as e:
            print(f"Error rechazando conexión: {e}")
    
    def disconnect(self):
        """Desconecta del servidor"""
        if self.connected:
            try:
                fin_packet = self.create_packet(self.FIN, self.username, "", b"")
                self.socket.send(fin_packet)
            except:
                pass
            finally:
                self.connected = False
                if self.socket:
                    self.socket.close()
                print("✓ Desconectado del servidor")
    
    def run_interactive(self):
        """Ejecuta el cliente de forma interactiva"""
        print("=== Cliente de Mensajería ===")
        
        # Solicitar IP del servidor
        server_ip = input("Ingresa la IP del servidor (Enter para localhost): ").strip()
        if not server_ip:
            server_ip = 'localhost'
        elif server_ip != 'localhost' and not self.is_valid_ip(server_ip):
            print(f"✗ IP inválida: {server_ip}")
            return
        
        # Solicitar puerto del servidor
        server_port_input = input("Ingresa el puerto del servidor (Enter para 8080): ").strip()
        if server_port_input:
            try:
                server_port = int(server_port_input)
                if server_port < 1 or server_port > 65535:
                    print("✗ Puerto debe estar entre 1 y 65535")
                    return
            except ValueError:
                print("✗ Puerto debe ser un número válido")
                return
        else:
            server_port = 8080
        
        # Actualizar configuración del cliente
        self.server_host = server_ip
        self.server_port = server_port
        
        # Conectar al servidor
        username = input("Ingresa tu nombre de usuario: ").strip()
        if not username:
            print("Nombre de usuario no puede estar vacío")
            return
        
        if not self.connect_to_server(username):
            return
        
        print("\nComandos disponibles:")
        print("/msg <usuario> <mensaje> - Enviar mensaje")
        print("/file <usuario> <archivo> - Enviar archivo")
        print("/accept <usuario> - Aceptar conexión")
        print("/reject <usuario> - Rechazar conexión")
        print("/quit - Salir")
        print("-" * 40)
        
        try:
            while self.connected:
                command = input().strip()
                
                if not command:
                    continue
                
                if command.startswith('/msg '):
                    parts = command.split(' ', 2)
                    if len(parts) >= 3:
                        dest_user = parts[1]
                        message = parts[2]
                        self.send_message(dest_user, message)
                    else:
                        print("Uso: /msg <usuario> <mensaje>")
                
                elif command.startswith('/file '):
                    parts = command.split(' ', 2)
                    if len(parts) >= 3:
                        dest_user = parts[1]
                        filepath = parts[2]
                        self.send_file(dest_user, filepath)
                    else:
                        print("Uso: /file <usuario> <archivo>")
                
                elif command.startswith('/accept '):
                    parts = command.split(' ', 1)
                    if len(parts) >= 2:
                        user = parts[1]
                        self.accept_connection(user)
                    else:
                        print("Uso: /accept <usuario>")
                
                elif command.startswith('/reject '):
                    parts = command.split(' ', 1)
                    if len(parts) >= 2:
                        user = parts[1]
                        self.reject_connection(user)
                    else:
                        print("Uso: /reject <usuario>")
                
                elif command == '/quit':
                    break
                
                else:
                    print("Comando no reconocido")
                    
        except KeyboardInterrupt:
            pass
        finally:
            self.disconnect()

if __name__ == "__main__":
    client = MessagingClient()
    client.run_interactive()