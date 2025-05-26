#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <arpa/inet.h>
#include <unistd.h>

#define PORT 6969

int main() {
    int sockfd;
    struct sockaddr_in servaddr, cliaddr;
    unsigned char buffer[1024];

    sockfd = socket(AF_INET, SOCK_DGRAM, 0);
    if(sockfd < 0) {
        perror("socket error");
        exit(1);
    }

    memset(&servaddr, 0, sizeof(servaddr));
    servaddr.sin_family = AF_INET;              
    servaddr.sin_addr.s_addr = INADDR_ANY;       
    servaddr.sin_port = htons(PORT);             

    if(bind(sockfd, (const struct sockaddr *)&servaddr, sizeof(servaddr)) < 0) {
        perror("bind error");
        close(sockfd);
        exit(1);
    }

    printf("Servidor UDP esperando paquetes...\n");

    socklen_t len = sizeof(cliaddr);

    while (1) {
        int n = recvfrom(sockfd, buffer, sizeof(buffer), 0, (struct sockaddr*)&cliaddr, &len);
        if(n < 0) {
            perror("recvfrom error");
            continue;
        }

        unsigned char *data = buffer;
        int opcode = (data[0] << 8) | data[1];

        if(opcode == 2) { // WRQ
            char filename[100], mode[20]; 
            strncpy(filename, (char*)&data[2], sizeof(filename)-1);
            filename[sizeof(filename)-1] = '\0';

            strncpy(mode, (char*)&data[2 + strlen(filename) + 1], sizeof(mode)-1);
            mode[sizeof(mode)-1] = '\0';

            printf("Opcode: %d, Archivo: %s, Modo: %s\n", opcode, filename, mode);

            unsigned char ack[4] = {0, 4, 0, 0};
            sendto(sockfd, ack, 4, 0, (struct sockaddr *)&cliaddr, len);
            printf("ACK enviado al cliente (block 0)\n");

            // Abrimos archivo para escribir (sobreescribimos si ya existe)
            FILE *f = fopen("recibido.txt", "wb");
            if (!f) {
                perror("No se pudo abrir recibido.txt");
                continue;
            }

            // Recibir bloques DATA hasta que el tamaño de datos < 512 (fin de archivo)
            while (1) {
                n = recvfrom(sockfd, buffer, sizeof(buffer), 0, (struct sockaddr*)&cliaddr, &len);
                if(n < 0) {
                    perror("recvfrom DATA error");
                    break;
                }

                if(buffer[1] == 3) { // DATA
                    int block_num = (buffer[2] << 8) | buffer[3];
                    int data_len = n - 4;
                    printf("Recibido DATA, bloque: %d, tamaño: %d bytes\n", block_num, data_len);

                    fwrite(&buffer[4], 1, data_len, f);

                    unsigned char ack_data[4] = {0, 4, buffer[2], buffer[3]};
                    sendto(sockfd, ack_data, 4, 0, (struct sockaddr *)&cliaddr, len);
                    printf("ACK enviado para bloque %d\n", block_num);

                    if(data_len < 512) {
                        printf("Transferencia completada\n");
                        break;
                    }
                }
            }
            fclose(f);
        }
        else {
            printf("Paquete no reconocido (opcode %d)\n", opcode);
        }
    }

    close(sockfd);
    return 0;
}
