#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <sys/select.h>

#define PORT 7777
#define MAX_CLIENTS 10

enum {SYN = 0, ACK = 1, MSG = 2, FILE = 3, FIN = 4};

typedef struct {
    int code;           // codigo del paquete
    char username[32];  // emisor
    char dest[32];      // receptor
    int datalen;        // long del msg/archivo
    char data[4096];    // msg/Archivo
} packet_t;

typedef struct {
    int sockfd;
    char username[32];
    int acuerdod;     // 0 = esperando 1 = listo para chat
} client_t;

client_t clients[MAX_CLIENTS];

int encontrar_cliente_por_nombre(const char *username) {
    for (int i = 0; i < MAX_CLIENTS; i++) {
        if (clients[i].sockfd > 0 && clients[i].acuerdod == 1 &&
            strcmp(clients[i].username, username) == 0)
            return i;
    }
    return -1;
}

void enviar_paquete(int sockfd, packet_t *pkt) {
    write(sockfd, pkt, sizeof(packet_t));
}

int main() {
    int escuchandofd, maxfd, newsockfd, activity, i;
    struct sockaddr_in serv_addr, cli_addr;
    socklen_t clilen;
    fd_set readfds;

    escuchandofd = socket(AF_INET, SOCK_STREAM, 0);
    serv_addr.sin_family = AF_INET;
    serv_addr.sin_addr.s_addr = INADDR_ANY;
    serv_addr.sin_port = htons(PORT);

    bind(escuchandofd, (struct sockaddr *)&serv_addr, sizeof(serv_addr));
    listen(escuchandofd, 5);

    for (i = 0; i < MAX_CLIENTS; i++) clients[i].sockfd = 0;

    printf("Servidor de chat iniciado en puerto %d\n", PORT);

    while (1) {
        FD_ZERO(&readfds);
        FD_SET(escuchandofd, &readfds);
        maxfd = escuchandofd;

        for (i = 0; i < MAX_CLIENTS; i++) {
            int sd = clients[i].sockfd;
            if (sd > 0) FD_SET(sd, &readfds);
            if (sd > maxfd) maxfd = sd;
        }

        activity = select(maxfd + 1, &readfds, NULL, NULL, NULL);

        if (FD_ISSET(escuchandofd, &readfds)) {
            clilen = sizeof(cli_addr);
            newsockfd = accept(escuchandofd, (struct sockaddr *)&cli_addr, &clilen);

            for (i = 0; i < MAX_CLIENTS; i++) {
                if (clients[i].sockfd == 0) {
                    clients[i].sockfd = newsockfd;
                    clients[i].acuerdod = 0;
                    clients[i].username[0] = '\0';
                    printf("Nuevo cliente conectado (sin acuerdo aún)\n");
                    break;
                }
            }
        }

        for (i = 0; i < MAX_CLIENTS; i++) {
            int sd = clients[i].sockfd;
            if (sd > 0 && FD_ISSET(sd, &readfds)) {
                packet_t pkt;
                int n = read(sd, &pkt, sizeof(pkt));
                if (n <= 0) {
                    printf("Cliente %s desconectado\n", clients[i].username);
                    close(sd);
                    clients[i].sockfd = 0;
                } else {
                    // aca empieza el 3 vias
                    if (clients[i].acuerdod == 0) {
                        if (pkt.code == SYN) {
                            printf("Recibido SYN de %s\n", pkt.username);
                            strncpy(clients[i].username, pkt.username, 31);

                            // se responde el syn-ack
                            packet_t synack;
                            synack.code = SYN;
                            strncpy(synack.username, "server", 31);
                            strncpy(synack.dest, pkt.username, 31);
                            synack.datalen = 0;
                            enviar_paquete(sd, &synack);
                        } else if (pkt.code == ACK) {
                            clients[i].acuerdod = 1;
                            printf("Cliente %s completó acuerdo\n", clients[i].username);
                        }
                        continue;
                    }

                    // procesar paquetes mensajes o archivos
                    if (pkt.code == MSG) {
                        int idx = encontrar_cliente_por_nombre(pkt.dest);
                        if (idx >= 0) {
                            printf("Mensaje de %s para %s: %s\n", pkt.username, pkt.dest, pkt.data);
                            enviar_paquete(clients[idx].sockfd, &pkt);
                        }
                    } else if (pkt.code == FILE) {
                        int idx = encontrar_cliente_por_nombre(pkt.dest);
                        if (idx >= 0) {
                            printf("Archivo de %s para %s: %s (%d bytes)\n", pkt.username, pkt.dest, pkt.data, pkt.datalen);
                            enviar_paquete(clients[idx].sockfd, &pkt);
                        }
                    } else if (pkt.code == FIN) {
                        printf("Cliente %s pidió FIN\n", pkt.username);
                        close(sd);
                        clients[i].sockfd = 0;
                    }
                }
            }
        }
    }
    return 0;
}
