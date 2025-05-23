#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <arpa/inet.h>
#include <unistd.h>

#define PORT 6969 // o el puerto que elijas

/*Este modelo de servidor recibe el paquete, lee los dos primeros bytes
extrae el nombre del archivo, extrae el modo e imprime todo
*/
int main() {
    int sockfd;                             // Descriptor del socket
    struct sockaddr_in servaddr, cliaddr;   // Estructuras para dirección del servidor y cliente
    unsigned char buffer[1024];             // Buffer para recibir datos

    //crea ek socket udp
    sockfd = socket(AF_INET, SOCK_DGRAM, 0);
    if(sockfd < 0) {
        perror("socket error");
        exit(1);
    }

    memset(&servaddr, 0, sizeof(servaddr));      // Pone en cero toda la estructura servaddr
    servaddr.sin_family = AF_INET;              
    servaddr.sin_addr.s_addr = INADDR_ANY;       // Acepta conexiones desde cualquier IP local
    servaddr.sin_port = htons(PORT);             // Puerto del servidor 

    //enlaza el socket a la direccion del servidor
    if(bind(sockfd, (const struct sockaddr *)&servaddr, sizeof(servaddr)) < 0) {
        perror("bind error");
        close(sockfd);
        exit(1);
    }

    printf("Servidor UDP esperando paquetes...\n");

    //queda esperando recibir un paquete udp
    socklen_t len = sizeof(cliaddr);
    int n = recvfrom(sockfd, buffer, sizeof(buffer), 0, (struct sockaddr*)&cliaddr, &len);
    if(n < 0) {
        perror("recvfrom error");
        close(sockfd);
        exit(1);
    }

    // ---- PARSEAR EL PAQUETE TFTP ----
    unsigned char *data = buffer; // puntero a los datos del paquete
    int opcode = (data[0] << 8) | data[1]; // extrae el opcode (primeros 2 bytes)

    // Extraer filename y mode buscando '\0'
    char filename[100], mode[20]; 
    strncpy(filename, (char*)&data[2], sizeof(filename)-1);
    filename[sizeof(filename)-1] = '\0';

    strncpy(mode, (char*)&data[2 + strlen(filename) + 1], sizeof(mode)-1);
    mode[sizeof(mode)-1] = '\0';

    printf("Opcode: %d, Archivo: %s, Modo: %s\n", opcode, filename, mode);

    // Ejemplo: responder ACK si es WRQ (opcode 2)
    if(opcode == 2) {
        unsigned char ack[4] = {0, 4, 0, 0}; // Opcode 4, block 0
        sendto(sockfd, ack, 4, 0, (struct sockaddr *)&cliaddr, len);
        printf("ACK enviado al cliente (block 0)\n");
    }
    // Esperar DATA
    n = recvfrom(sockfd, buffer, sizeof(buffer), 0, (struct sockaddr*)&cliaddr, &len);
    if(n >= 4 && buffer[1] == 3) { // opcode 3 = DATA
        int block_num = (buffer[2] << 8) | buffer[3];
        printf("Recibido DATA, bloque: %d, tamaño de datos: %d bytes\n", block_num, n-4);

        // Si querés guardar los datos en archivo:
        FILE *f = fopen("recibido.txt", "ab");
        if(f) {
            fwrite(&buffer[4], 1, n-4, f);
            fclose(f);
            printf("Datos guardados en recibido.txt\n");
        }

        // Enviar ACK para este bloque
        unsigned char ack_data[4] = {0, 4, buffer[2], buffer[3]};
        sendto(sockfd, ack_data, 4, 0, (struct sockaddr *)&cliaddr, len);
        printf("ACK enviado para bloque %d\n", block_num);
    }
    close(sockfd);
    return 0;
}
