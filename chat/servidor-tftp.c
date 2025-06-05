#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <signal.h>
#include <sys/wait.h>
#include <sys/time.h> // Para struct timeval


#define PORT 6969
#define MAX_RETRIES 5

int retries = 0;
unsigned char last_ack[4];
int last_block = 0;
// Enviar paquete de error TFTP
void send_tftp_error(int sockfd, struct sockaddr_in *cliaddr, socklen_t len,
                     unsigned short error_code, const char *err_msg)
{
    unsigned char pkt[516];
    size_t msg_len = strlen(err_msg);

    pkt[0] = 0x00;
    pkt[1] = 0x05; // Opcode ERROR
    pkt[2] = 0x00;
    pkt[3] = error_code; // Código de error (ver lista)
    memcpy(&pkt[4], err_msg, msg_len);
    pkt[4 + msg_len] = 0x00; // Fin de string

    sendto(sockfd, pkt, 5 + msg_len, 0, (struct sockaddr *)cliaddr, len);
}

// Para evitar procesos zombies
void reap_children(int sig)
{
    (void)sig;
    while (waitpid(-1, NULL, WNOHANG) > 0)
        ;
}

// Lógica de transferencia (el hijo hace TODO esto)
void handle_transfer(int opcode, char *filename, char *mode, struct sockaddr_in cliaddr, socklen_t len)
{
    int sockfd = socket(AF_INET, SOCK_DGRAM, 0);
    if (sockfd < 0)
    {
        perror("socket error (child)");
        exit(1);
    }

    unsigned char buffer[1024];
    printf("Atendiendo cliente PID=%d, archivo=%s, modo=%s, opcode=%d\n", getpid(), filename, mode, opcode);

    if (opcode == 2)
    { // WRQ
        unsigned char ack[4] = {0, 4, 0, 0};
        sendto(sockfd, ack, 4, 0, (struct sockaddr *)&cliaddr, len);
        printf("ACK enviado al cliente (block 0)\n");

        FILE *f = fopen(filename, "wb");
        if (!f)
        {
            perror("No se pudo abrir archivo para escribir");
            send_tftp_error(sockfd, &cliaddr, len, 2, "Violación de acceso");
            close(sockfd);
            exit(1);
        }

        while (1)
        {
            fd_set readfds;
            struct timeval timeout;

            FD_ZERO(&readfds);
            FD_SET(sockfd, &readfds);

            timeout.tv_sec = 3; // 3 segundos de espera
            timeout.tv_usec = 0;

            int activity = select(sockfd + 1, &readfds, NULL, NULL, &timeout);

            if (activity < 0)
            {
                perror("select error");
                break;
            }
            else if (activity == 0)
            {
                // Timeout: reenviar ACK
                if (retries >= MAX_RETRIES)
                {
                    printf("Se alcanzó el máximo de reintentos. Cancelando transferencia.\n");
                    break;
                }

                retries++;
                printf("Timeout (%d/%d). Reenviando ACK del bloque %d\n", retries, MAX_RETRIES, last_block);
                sendto(sockfd, last_ack, 4, 0, (struct sockaddr *)&cliaddr, len);
                continue;
            }

            int n = recvfrom(sockfd, buffer, sizeof(buffer), 0, (struct sockaddr *)&cliaddr, &len);
            if (n < 0)
            {
                perror("recvfrom DATA error");
                break;
            }
            retries = 0; // Reset si llega algo

            int data_opcode = (buffer[0] << 8) | buffer[1];
            if (data_opcode == 3) // DATA
            {
                int block_num = (buffer[2] << 8) | buffer[3];
                int data_len = n - 4;
                printf("Recibido DATA, bloque: %d, tamaño: %d bytes\n", block_num, data_len);

                fwrite(&buffer[4], 1, data_len, f);

                last_block = block_num;
                last_ack[2] = buffer[2];
                last_ack[3] = buffer[3];

                unsigned char ack_data[4] = {0, 4, buffer[2], buffer[3]};
                sendto(sockfd, last_ack, 4, 0, (struct sockaddr *)&cliaddr, len);
                printf("ACK enviado para bloque %d\n", block_num);

                if (data_len < 512)
                {
                    printf("Transferencia completada\n");
                    break;
                }
            }
        }
        fclose(f);
    }
    else if (opcode == 1)
    { // RRQ
        FILE *f = fopen(filename, "rb");
        if (!f)
        {
            perror("No se pudo abrir archivo solicitado");
            send_tftp_error(sockfd, &cliaddr, len, 1, "Archivo no encontrado");
            close(sockfd);
            exit(1);
        }
        unsigned char data_packet[516];
        int block_number = 1;
        size_t bytes_read;
        ssize_t sent;
        int retries;

        data_packet[0] = 0;
        data_packet[1] = 3; // Opcode DATA

        while (1)
        {
            bytes_read = fread(&data_packet[4], 1, 512, f);
            if (ferror(f))
            {
                perror("Error leyendo archivo");
                fclose(f);
                send_tftp_error(sockfd, &cliaddr, len, 0, "Error indefinido");
                break;
            }

            data_packet[2] = (block_number >> 8) & 0xFF;
            data_packet[3] = block_number & 0xFF;
            retries = 0;

            while (retries < MAX_RETRIES)
            {

                sent = sendto(sockfd, data_packet, bytes_read + 4, 0, (struct sockaddr *)&cliaddr, len);
                if (sent < 0)
                {
                    perror("Error enviando DATA");
                    fclose(f);
                    send_tftp_error(sockfd, &cliaddr, len, 3, "Disco lleno o límite superado");
                    break;
                }
                printf("Enviado bloque %d (%ld bytes)\n", block_number, sent);
                fd_set readfds;
                struct timeval timeout;

                FD_ZERO(&readfds);
                FD_SET(sockfd, &readfds);

                timeout.tv_sec = 3;
                timeout.tv_usec = 0;
                int activity = select(sockfd + 1, &readfds, NULL, NULL, &timeout);

                if (activity < 0)
                {
                    perror("select error");
                    fclose(f);
                    return;
                }
                else if (activity == 0)
                {
                    retries++;
                    printf("Timeout esperando ACK (intento %d/%d). Reenviando bloque %d\n", retries, MAX_RETRIES, block_number);
                    continue;
                }

                int n = recvfrom(sockfd, buffer, sizeof(buffer), 0, (struct sockaddr *)&cliaddr, &len);
                if (n < 0)
                {
                    perror("error paquete ack");
                    fclose(f);
                    return;
                }
                int ack_opcode = (buffer[0] << 8) | buffer[1];
                int ack_block = (buffer[2] << 8) | buffer[3];
                if (ack_opcode == 4 && ack_block == block_number)
                {
                    printf("Recibido ACK, bloque: %d\n", ack_block);
                    break; // Salir del bucle de reintentos
                }
                else
                {
                    printf("ACK inválido. Esperado: %d, recibido: %d\n", block_number, ack_block);
                }
            }
            if (retries == MAX_RETRIES)
            {
                printf("No se recibió ACK tras %d intentos. Cancelando transferencia.\n", MAX_RETRIES);
                fclose(f);
                break;
            }
            block_number += 1;

            if (bytes_read < 512)
            {
                printf("Transferencia completada\n");
                fclose(f);
                break;
            }
        }
    }

    close(sockfd);
    printf("Cliente atendido. Proceso hijo PID=%d termina.\n", getpid());
    exit(0);
}

int main()
{
    // Evita procesos zombies
    signal(SIGCHLD, reap_children);

    int sockfd;
    struct sockaddr_in servaddr, cliaddr;
    unsigned char buffer[1024];

    sockfd = socket(AF_INET, SOCK_DGRAM, 0);
    if (sockfd < 0)
    {
        perror("socket error");
        exit(1);
    }

    memset(&servaddr, 0, sizeof(servaddr));
    servaddr.sin_family = AF_INET;
    servaddr.sin_addr.s_addr = INADDR_ANY;
    servaddr.sin_port = htons(PORT);

    if (bind(sockfd, (const struct sockaddr *)&servaddr, sizeof(servaddr)) < 0)
    {
        perror("bind error");
        close(sockfd);
        exit(1);
    }

    printf("Servidor UDP esperando paquetes...\n");

    socklen_t len = sizeof(cliaddr);

    while (1)
    {
        int n = recvfrom(sockfd, buffer, sizeof(buffer), 0, (struct sockaddr *)&cliaddr, &len);
        if (n < 0)
        {
            perror("recvfrom error");
            continue;
        }

        unsigned char *data = buffer;
        int opcode = (data[0] << 8) | data[1];

        if (opcode == 1 || opcode == 2) // RRQ o WRQ
        {
            char filename[100], mode[20];
            char *ptr = (char *)&data[2];

            // Copiar filename desde ptr
            strncpy(filename, ptr, sizeof(filename) - 1);
            filename[sizeof(filename) - 1] = '\0';

            // Avanzar ptr más allá del filename y su terminador nulo
            ptr += strlen(ptr) + 1;

            // Copiar mode desde la nueva posición
            strncpy(mode, ptr, sizeof(mode) - 1);
            mode[sizeof(mode) - 1] = '\0';

            pid_t pid = fork();
            if (pid < 0)
            {
                perror("fork error");
                continue;
            }
            if (pid == 0)
            {
                // HIJO: atiende al cliente
                close(sockfd); // El hijo no usa el socket principal
                handle_transfer(opcode, filename, mode, cliaddr, len);
                // Nunca vuelve acá
            }
            // PADRE: sigue escuchando
        }
        else
        {
            // Paquete desconocido: ignorar o responder error si querés
            send_tftp_error(sockfd, &cliaddr, len, 4, "Operación TFTP ilegal");
        }
    }

    close(sockfd);
    return 0;
}
