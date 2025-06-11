#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <sys/select.h>
#include <pthread.h>
#include <stdlib.h>

#define MAX_NAME_LEN 32
#define MAX_CONEXIONES 100
#define PORT 28008
#define MAX_CLIENTS 10

enum
{
    SYN = 0,
    ACK = 1,
    MSG = 2,
    FILE_CODE = 3,
    FIN = 4,
    ACEPTADO = 5,
    RECHAZADO = 6
};

typedef enum
{
    CONECTADO,
    BLOQUEADO,
    PENDIENTE
} EstadoConexion;

typedef struct
{
    char usuario1[MAX_NAME_LEN];
    char usuario2[MAX_NAME_LEN];
    EstadoConexion estado;
} Conexion;

typedef struct
{
    int code;                    // codigo del paquete
    char username[MAX_NAME_LEN]; // emisor
    char dest[MAX_NAME_LEN];     // receptor
    int datalen;                 // long del msg/archivo
    char data[4096];             // msg/Archivo
} packet_t;

typedef struct
{
    int sockfd;
    char username[32];
    int acuerdod; // 0 = esperando 1 = listo para chat
} client_t;

client_t clients[MAX_CLIENTS];
Conexion conexiones[MAX_CONEXIONES];
int num_conexiones = 0;

int encontrar_cliente_por_nombre(const char *username)
{
    for (int i = 0; i < MAX_CLIENTS; i++)
    {
        if (clients[i].sockfd > 0 && clients[i].acuerdod == 1 && strcmp(clients[i].username, username) == 0)
            return i;
    }
    return -1;
}

void agregar_conexion(const char *u1, const char *u2, EstadoConexion estado)
{
    if (num_conexiones >= MAX_CONEXIONES)
    {
        printf("Error: n煤mero m谩ximo de conexiones alcanzado.\n");
        return;
    }
    strncpy(conexiones[num_conexiones].usuario1, u1, MAX_NAME_LEN);
    strncpy(conexiones[num_conexiones].usuario2, u2, MAX_NAME_LEN);
    conexiones[num_conexiones].estado = estado;
    num_conexiones++;
}

int buscar_conexion(const char *u1, const char *u2)
{
    for (int i = 0; i < num_conexiones; i++)
    {
        if ((strncmp(conexiones[i].usuario1, u1, 32) == 0 && strncmp(conexiones[i].usuario2, u2, 32) == 0) ||
        (strncmp(conexiones[i].usuario1, u2, 32) == 0 && strncmp(conexiones[i].usuario2, u1, 32) == 0))
        return i;

    }
    return -1;
}

void eliminar_conexiones_de_usuario(const char *username)
{
    for (int i = 0; i < num_conexiones; i++)
    {
        if (!strcmp(conexiones[i].usuario1, username) || !strcmp(conexiones[i].usuario2, username))
        {
            printf("Eliminando conexi贸n entre %s y %s\n",conexiones[i].usuario1, conexiones[i].usuario2);
            for (int k = i; k < num_conexiones - 1; k++)
                conexiones[k] = conexiones[k + 1];
            num_conexiones--;
            i--;
        }
    }
}

void enviar_paquete(int sockfd, packet_t *pkt) {
    write(sockfd, pkt, sizeof(*pkt));
}

void nueva_conexion(int escuchandofd)
{
    struct sockaddr_in cli_addr;
    socklen_t clilen = sizeof(cli_addr);
    int newsockfd = accept(escuchandofd, (struct sockaddr *)&cli_addr, &clilen);
    if (newsockfd < 0)
        return;

    for (int i = 0; i < MAX_CLIENTS; i++)
    {
        if (clients[i].sockfd == 0)
        {
            clients[i].sockfd = newsockfd;
            clients[i].acuerdod = 0;
            clients[i].username[0] = '\0';
            printf("Nuevo cliente conectado (sin acuerdo a煤n)\n");
            break;
        }
    }
}

void imprimir_estado_conexiones()
{
    printf("\n=== Estado actual de conexiones ===\n");
    for (int i = 0; i < MAX_CONEXIONES; i++)
    {
        if (strlen(conexiones[i].usuario1) == 0 && strlen(conexiones[i].usuario2) == 0)
        {
            // Entrada vac铆a, ignorar
            continue;
        }

        const char *estado_str = "DESCONOCIDO";
        switch (conexiones[i].estado)
        {
        case CONECTADO:
            estado_str = "CONECTADO";
            break;
        case BLOQUEADO:
            estado_str = "BLOQUEADO";
            break;
        case PENDIENTE:
            estado_str = "PENDIENTE";
            break;
        }

        printf("Conexi贸n %d: '%s' <-> '%s' | Estado: %s\n",i, conexiones[i].usuario1, conexiones[i].usuario2, estado_str);
    }
    printf("===================================\n\n");
}

void procesar_paquete(int client_idx, packet_t *pkt)
{}

void* manejar_cliente(void* args) {
    thread_args_t* targs = (thread_args_t*) args;
    int client_idx = targs->client_idx;
    free(targs);

    int sd = clients[client_idx].sockfd;
    packet_t pkt;

    while (1) {
        int n = read(sd, &pkt, sizeof(pkt));
        if (n <= 0) {
            printf("Cliente %s desconectado\n", clients[client_idx].username);
            close(sd);
            clients[client_idx].sockfd = 0;
            eliminar_conexiones_de_usuario(clients[client_idx].username);
            break;
        }

        // Procesar el paquete recibido
        switch (pkt.code) {
            case MSG: {
                int idx = encontrar_cliente_por_nombre(pkt.dest);
                if (idx >= 0) {
                    int conn_idx = buscar_conexion(pkt.username, pkt.dest);
                    if (conn_idx < 0) {
                        agregar_conexion(pkt.username, pkt.dest, PENDIENTE);
                        printf("Solicitud de conexión de %s a %s\n", pkt.username, pkt.dest);
                        enviar_paquete(clients[idx].sockfd, &pkt);
                    } else {
                        EstadoConexion estado = conexiones[conn_idx].estado;
                        if (estado == CONECTADO) {
                            enviar_paquete(clients[idx].sockfd, &pkt);
                        } else {
                            printf("Mensaje descartado (%s -> %s) por estado %s\n",
                                pkt.username, pkt.dest, estado == BLOQUEADO ? "BLOQUEADO" : "PENDIENTE");
                        }
                    }
                }
                break;
            }

            case ACEPTADO: {
                int conn_idx = buscar_conexion(pkt.dest, pkt.username);
                if (conn_idx >= 0 && conexiones[conn_idx].estado == PENDIENTE) {
                    conexiones[conn_idx].estado = CONECTADO;
                    printf("Conexión aceptada entre %s y %s\n", pkt.dest, pkt.username);
                    imprimir_estado_conexiones();

                    int emisor_idx = encontrar_cliente_por_nombre(pkt.dest);
                    if (emisor_idx >= 0) {
                        packet_t confirm;
                        confirm.code = ACEPTADO;
                        strncpy(confirm.username, pkt.username, MAX_NAME_LEN);
                        strncpy(confirm.dest, pkt.dest, MAX_NAME_LEN);
                        confirm.datalen = snprintf(confirm.data, sizeof(confirm.data),
                            "Conexión aceptada por %s", pkt.username);
                        enviar_paquete(clients[emisor_idx].sockfd, &confirm);
                    }
                }
                break;
            }

            case RECHAZADO: {
                int conn_idx = buscar_conexion(pkt.dest, pkt.username);
                if (conn_idx >= 0 && conexiones[conn_idx].estado == PENDIENTE) {
                    conexiones[conn_idx].estado = RECHAZADO;
                    printf("Conexión rechazada entre %s y %s\n", pkt.dest, pkt.username);
                    imprimir_estado_conexiones();
                }
                break;
            }

            case FILE_CODE: {
                int idx = encontrar_cliente_por_nombre(pkt.dest);
                if (idx >= 0) {
                    int conn_idx = buscar_conexion(pkt.username, pkt.dest);
                    if (conn_idx >= 0 && conexiones[conn_idx].estado == CONECTADO) {
                        printf("Iniciando transferencia de archivo de %s a %s\n", pkt.username, pkt.dest);
                        enviar_paquete(clients[idx].sockfd, &pkt);
                    } else {
                        printf("Archivo descartado (%s -> %s) por estado %s\n", pkt.username, pkt.dest,
                            conexiones[conn_idx].estado == BLOQUEADO ? "BLOQUEADO" : "PENDIENTE");
                    }
                }
                break;
            }

            case FIN: {
                printf("Cliente %s pidió FIN\n", pkt.username);
                close(sd);
                clients[client_idx].sockfd = 0;
                eliminar_conexiones_de_usuario(pkt.username);
                pthread_exit(NULL);
            }
        }
    }
}


int main()
{
    int escuchandofd, maxfd, activity, i;
    struct sockaddr_in serv_addr;
    fd_set readfds;

    escuchandofd = socket(AF_INET, SOCK_STREAM, 0);
    serv_addr.sin_family = AF_INET;
    serv_addr.sin_addr.s_addr = INADDR_ANY;
    serv_addr.sin_port = htons(PORT);

    bind(escuchandofd, (struct sockaddr *)&serv_addr, sizeof(serv_addr));
    listen(escuchandofd, 5);

    for (i = 0; i < MAX_CLIENTS; i++)
        clients[i].sockfd = 0;

    printf("FUNCIONA Servidor de chat iniciado en puerto %d\n", PORT);

    while (1)
    {
        FD_ZERO(&readfds);
        FD_SET(escuchandofd, &readfds);
        maxfd = escuchandofd;

        for (i = 0; i < MAX_CLIENTS; i++)
        {
            int sd = clients[i].sockfd;
            if (sd > 0)
                FD_SET(sd, &readfds);
            if (sd > maxfd)
                maxfd = sd;
        }

        activity = select(maxfd + 1, &readfds, NULL, NULL, NULL);

        if (activity < 0)
        {
            perror("select");
            continue;
        }

        if (FD_ISSET(escuchandofd, &readfds))
        {
            nueva_conexion(escuchandofd);
        }

        for (i = 0; i < MAX_CLIENTS; i++)
        {
            int sd = clients[i].sockfd;
            if (sd > 0 && FD_ISSET(sd, &readfds))
            {
                packet_t pkt;
                int n = read(sd, &pkt, sizeof(pkt));
                if (n <= 0)
                {
                    printf("Cliente %s desconectado\n", clients[i].username);
                    close(sd);
                    clients[i].sockfd = 0;
                    continue;
                }

                // Manejo del acuerdo de conexión
                if (clients[i].acuerdod == 0)
                {
                    if (pkt.code == SYN)
                    {
                        printf("Recibido SYN de %s\n", pkt.username);
                        strncpy(clients[i].username, pkt.username, 31);

                        packet_t synack;
                        synack.code = SYN;
                        strncpy(synack.username, "server", 31);
                        strncpy(synack.dest, pkt.username, 31);
                        synack.datalen = 0;
                        enviar_paquete(sd, &synack);
                    }
                    else if (pkt.code == ACK)
                    {
                        clients[i].acuerdod = 1;
                        printf("Cliente %s completó acuerdo\n", clients[i].username);
                    }
                    continue;
                }

                 // Lanzar hilo para manejar paquete
                pthread_t hilo;
                thread_args_t* args = malloc(sizeof(thread_args_t));
                args->client_idx = i;
                args->pkt = pkt;
                pthread_create(&hilo, NULL, manejar_cliente, args);
                pthread_detach(hilo);
            }
        }
    }
}