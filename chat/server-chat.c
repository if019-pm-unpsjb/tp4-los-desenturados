#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <sys/select.h>
#include <arpa/inet.h>

#define PORT 7777
#define MAX_CLIENTS 10

typedef struct {
    int sockfd;
    char username[32];
} client_t;

client_t clients[MAX_CLIENTS];

int main() {
    int listenfd, maxfd, newsockfd, activity, i;
    struct sockaddr_in serv_addr, cli_addr;
    socklen_t clilen;
    fd_set readfds;

    // iniciar el socket
    listenfd = socket(AF_INET, SOCK_STREAM, 0);
    serv_addr.sin_family = AF_INET;
    serv_addr.sin_addr.s_addr = INADDR_ANY;
    serv_addr.sin_port = htons(PORT);

    bind(listenfd, (struct sockaddr *)&serv_addr, sizeof(serv_addr));
    listen(listenfd, 5);

    // Inicializa lista de clientes
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

            // Buscar lugar para el nuevo cliente
            for (i = 0; i < MAX_CLIENTS; i++) {
                if (clients[i].sockfd == 0) {
                    clients[i].sockfd = newsockfd;
                    // Leer username inicial (haz que el cliente envíe su nombre apenas conecta)
                    int n = read(newsockfd, clients[i].username, sizeof(clients[i].username) - 1);
                    clients[i].username[n] = '\0';
                    printf("Nuevo usuario: %s\n", clients[i].username);
                    break;
                }
            }
        }

        // chequea la info de los clientes
        for (i = 0; i < MAX_CLIENTS; i++) {
            int sd = clients[i].sockfd;
            if (sd > 0 && FD_ISSET(sd, &readfds)) {
                char buffer[2048];
                int n = read(sd, buffer, sizeof(buffer));
                if (n <= 0) {
                    printf("Usuario %s desconectado\n", clients[i].username);
                    close(sd);
                    clients[i].sockfd = 0;
                } else {
                    buffer[n] = '\0';
                    // Procesar mensaje y reenviar a destinatario
                    // ... (completar después)
                }
            }
        }
    }
    return 0;
}
