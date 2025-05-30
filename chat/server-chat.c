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
    int acuerdod;     // 0 = esperando acuerdo, 1 = listo para chat
} client_t;

client_t clients[MAX_CLIENTS];

int find_client_by_username(const char *username) {
    for (int i = 0; i < MAX_CLIENTS; i++) {
        if (clients[i].sockfd > 0 && clients[i].acuerdod == 1 &&
            strcmp(clients[i].username, username) == 0)
            return i;
    }
    return -1;
}

void send_packet(int sockfd, packet_t *pkt) {
    write(sockfd, pkt, sizeof(packet_t));
}

int main() {
    int listenfd, maxfd, newsockfd, activity, i;
    struct sockaddr_in serv_addr, cli_addr;
    socklen_t clilen;
    fd_set readfds;

    listenfd = socket(AF_INET, SOCK_STREAM, 0);
    serv_addr.sin_family = AF_INET;
    serv_addr.sin_addr.s_addr = INADDR_ANY;
    serv_addr.sin_port = htons(PORT);

    bind(listenfd, (struct sockaddr *)&serv_addr, sizeof(serv_addr));
    listen(listenfd, 5);

    for (i = 0; i < MAX_CLIENTS; i++) clients[i].sockfd = 0;

    printf("Servidor de chat iniciado en puerto %d\n", PORT);

    while (1) {
        FD_ZERO(&readfds);
        FD_SET(listenfd, &readfds);
        maxfd = listenfd;

        for (i = 0; i < MAX_CLIENTS; i++) {
            int sd = clients[i].sockfd;
            if (sd > 0) FD_SET(sd, &readfds);
            if (sd > maxfd) maxfd = sd;
        }

        activity = select(maxfd + 1, &readfds, NULL, NULL, NULL);

        if (FD_ISSET(listenfd, &readfds)) {
            clilen = sizeof(cli_addr);
            newsockfd = accept(listenfd, (struct sockaddr *)&cli_addr, &clilen);

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
                    // acuerdo de 3 vías
                    if (clients[i].acuerdod == 0) {
                        if (pkt.code == SYN) {
                            printf("Recibido SYN de %s\n", pkt.username);
                            strncpy(clients[i].username, pkt.username, 31);

                            // Responde SYN-ACK
                            packet_t synack;
                            synack.code = SYN;
                            strncpy(synack.username, "server", 31);
                            strncpy(synack.dest, pkt.username, 31);
                            synack.datalen = 0;
                            send_packet(sd, &synack);
                        } else if (pkt.code == ACK) {
                            clients[i].acuerdod = 1;
                            printf("Cliente %s completó acuerdo\n", clients[i].username);
                        }
                        continue;
                    }

                    // Procesar paquetes normales
                    if (pkt.code == MSG) {
                        int idx = find_client_by_username(pkt.dest);
                        if (idx >= 0) {
                            printf("Mensaje de %s para %s: %s\n", pkt.username, pkt.dest, pkt.data);
                            send_packet(clients[idx].sockfd, &pkt);
                        }
                    } else if (pkt.code == FILE) {
                        int idx = find_client_by_username(pkt.dest);
                        if (idx >= 0) {
                            printf("Archivo de %s para %s: %s (%d bytes)\n", pkt.username, pkt.dest, pkt.data, pkt.datalen);
                            send_packet(clients[idx].sockfd, &pkt);
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
