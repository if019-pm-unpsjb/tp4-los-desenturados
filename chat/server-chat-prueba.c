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
#define MAX_MENSAJES 100
#define MAX_MSG_LEN 512

enum
{
    SYN = 0,
    ACK = 1,
    MSG = 2,
    FILE_CODE = 3,
    FIN = 4,
    ACEPTADO = 5,
    RECHAZADO = 6,
    ERROR = 7
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
    time_t timestamp;
    char bloqueador[MAX_NAME_LEN];
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

/* typedef struct {
    int client_idx;
    packet_t pkt;
} thread_args_t; */

typedef struct {
    char usuario1[MAX_NAME_LEN];
    char usuario2[MAX_NAME_LEN];
    char mensajes[MAX_MENSAJES][MAX_MSG_LEN];
    int cantidad;
} Historial;

Historial historiales[MAX_CONEXIONES];
int num_historiales = 0;

typedef struct
{
    int client_idx;
} thread_args_t;

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
    conexiones[num_conexiones].timestamp = time(NULL); // ahora
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
void enviar_paquete(int sockfd, packet_t *pkt)
{
    write(sockfd, pkt, sizeof(*pkt));
}

void eliminar_conexiones_de_usuario(const char *username) {
    for (int i = 0; i < num_conexiones; i++) {
        if (!strcmp(conexiones[i].usuario1, username) || !strcmp(conexiones[i].usuario2, username)) {
            const char *otro_usuario = strcmp(conexiones[i].usuario1, username) == 0
                                       ? conexiones[i].usuario2
                                       : conexiones[i].usuario1;

            printf("Eliminando conexión entre %s y %s\n", conexiones[i].usuario1, conexiones[i].usuario2);

            int idx_otro = encontrar_cliente_por_nombre(otro_usuario);
            if (idx_otro >= 0) {
                packet_t aviso = {.code = ERROR}; // O podés definir un nuevo código como DESCONECTADO
                strncpy(aviso.username, "server", MAX_NAME_LEN);
                strncpy(aviso.dest, otro_usuario, MAX_NAME_LEN);
                aviso.datalen = snprintf(aviso.data, sizeof(aviso.data),
                                         "El usuario %s se ha desconectado. La conexión fue cerrada.",
                                         username);
                enviar_paquete(clients[idx_otro].sockfd, &aviso);
            }

            for (int j = 0; j < num_historiales; j++) {
                if (!strcmp(historiales[j].usuario1, username) || !strcmp(historiales[j].usuario2, username)) {
                    for (int k = j; k < num_historiales - 1; k++) {
                        historiales[k] = historiales[k + 1];
                    }
                    num_historiales--;
                    j--;
                }
            }

            // Eliminar conexión
            for (int k = i; k < num_conexiones - 1; k++) {
                conexiones[k] = conexiones[k + 1];
            }
            num_conexiones--;
            i--;
        }
    }
}


int obtener_o_crear_historial(const char* u1, const char* u2) {
    for (int i = 0; i < num_historiales; i++) {
        if ((strcmp(historiales[i].usuario1, u1) == 0 && strcmp(historiales[i].usuario2, u2) == 0) ||
            (strcmp(historiales[i].usuario1, u2) == 0 && strcmp(historiales[i].usuario2, u1) == 0)) {
            return i;
        }
    }
    if (num_historiales >= MAX_CONEXIONES) return -1;
    strncpy(historiales[num_historiales].usuario1, u1, MAX_NAME_LEN);
    strncpy(historiales[num_historiales].usuario2, u2, MAX_NAME_LEN);
    historiales[num_historiales].cantidad = 0;
    return num_historiales++;
}


void guardar_mensaje_historial(const char* u1, const char* u2, const char* mensaje) {
    int idx = obtener_o_crear_historial(u1, u2);
    if (idx < 0 || historiales[idx].cantidad >= MAX_MENSAJES) return;

    snprintf(historiales[idx].mensajes[historiales[idx].cantidad], MAX_MSG_LEN, "%s: %s", u1, mensaje);
    historiales[idx].cantidad++;
}


void imprimir_estado_conexiones()
{
    printf("\n=== Estado actual de conexiones ===\n");
    for (int i = 0; i < MAX_CONEXIONES; i++)
    {
        if (strlen(conexiones[i].usuario1) == 0 && strlen(conexiones[i].usuario2) == 0)
        {
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
        time_t ahora = time(NULL);
        double minutos = difftime(ahora, conexiones[i].timestamp) / 60.0;
        printf("Conexión %d: '%s' <-> '%s' | Estado: %s | Tiempo: %.1f min\n",
               i, conexiones[i].usuario1, conexiones[i].usuario2, estado_str, minutos);
    }
    printf("===================================\n\n");
}

void *manejar_cliente(void *args)
{
    thread_args_t *targs = (thread_args_t *)args;
    int client_idx = targs->client_idx;
    free(targs);

    printf("[DEBUG] ENTRE AL MANEJAR CLIENTE");
    int sd = clients[client_idx].sockfd;
    packet_t pkt;
    while (1)
    {
        int n = read(sd, &pkt, sizeof(pkt));
        if (n <= 0)
        {
            printf("Cliente %s desconectado\n", clients[client_idx].username);
            close(sd);
            clients[client_idx].sockfd = 0;
            eliminar_conexiones_de_usuario(clients[client_idx].username);
            break;
        }
        printf("[DEBUG] INICIAL Recibido código %d de %s -> %s\n", pkt.code, pkt.username, pkt.dest);
        // Manejo de handshake inicial
        if (clients[client_idx].acuerdod == 0)
        {
            int idx = encontrar_cliente_por_nombre(pkt.dest);

            if (encontrar_cliente_por_nombre(pkt.username)<0){
                if (pkt.code == SYN)
                {
                    printf("Recibido SYN de %s\n", pkt.username);
                    strncpy(clients[client_idx].username, pkt.username, MAX_NAME_LEN);
                    packet_t synack = {.code = SYN};
                    strncpy(synack.username, "server", MAX_NAME_LEN);
                    strncpy(synack.dest, pkt.username, MAX_NAME_LEN);
                    synack.datalen = 0;
                    enviar_paquete(sd, &synack);
                }
                else if (pkt.code == ACK)
                {
                    clients[client_idx].acuerdod = 1;
                    printf("Cliente %s completó acuerdo\n", clients[client_idx].username);
                }
                continue;
            }
            else{
                packet_t error_pkt = {.code = ERROR};
                strncpy(error_pkt.username, "server", MAX_NAME_LEN);
                strncpy(error_pkt.dest, pkt.username, MAX_NAME_LEN);
                const char* msg = "El nombre de usuario ya está en uso.";
                error_pkt.datalen = snprintf(error_pkt.data, sizeof(error_pkt.data), "%s", msg);
                enviar_paquete(sd, &error_pkt);
                }
            }

        // Procesar paquetes
        switch (pkt.code)
        {
        case MSG:
        {
            int idx = encontrar_cliente_por_nombre(pkt.dest);
            if (idx >= 0)
            {
                int conn_idx = buscar_conexion(pkt.username, pkt.dest);
                if (conn_idx < 0)
                {
                    // No hay conexión previa: crear una nueva
                    agregar_conexion(pkt.username, pkt.dest, PENDIENTE);
                    printf("Solicitud de conexión de %s a %s\n", pkt.username, pkt.dest);
                    enviar_paquete(clients[idx].sockfd, &pkt);
                    guardar_mensaje_historial(pkt.username, pkt.dest, pkt.data);
                }
                else
                {
                    EstadoConexion estado = conexiones[conn_idx].estado;

                    if (estado == CONECTADO)
                    {
                        enviar_paquete(clients[idx].sockfd, &pkt);
                    }
                    else if (estado == BLOQUEADO)
                    {
                        if (strcmp(conexiones[conn_idx].bloqueador, pkt.username) == 0)
                        {
                            // El bloqueador quiere retomar: permitir
                            conexiones[conn_idx].estado = PENDIENTE;
                            conexiones[conn_idx].timestamp = time(NULL);
                            printf("El bloqueador %s reinició conexión con %s\n", pkt.username, pkt.dest);
                            enviar_paquete(clients[idx].sockfd, &pkt);
                        }
                        else
                        {
                            printf("Conexión bloqueada: %s no puede iniciar con %s\n", pkt.username, pkt.dest);
                        }
                    }
                    else
                    {
                        printf("Mensaje descartado (%s -> %s) por estado PENDIENTE\n", pkt.username, pkt.dest);
                    }
                }
            }else{
                packet_t error_pkt = {.code = ERROR};
                strncpy(error_pkt.username, "server", MAX_NAME_LEN);
                strncpy(error_pkt.dest, pkt.username, MAX_NAME_LEN);
                error_pkt.datalen = snprintf(error_pkt.data, sizeof(error_pkt.data), "El usuario %s no esta en linea", pkt.dest);
                enviar_paquete(sd, &error_pkt);
            }
            break;
        }

        case ACEPTADO:
        {
            printf("Recibido paquete ACEPTADO\n");

            int conn_idx = buscar_conexion(pkt.username, pkt.dest);
            if (conn_idx >= 0)
            {
                // Acepta si hay una conexión pendiente donde el otro usuario fue el solicitante
                if (conexiones[conn_idx].estado == PENDIENTE)
                {
                    conexiones[conn_idx].estado = CONECTADO;
                    conexiones[conn_idx].timestamp = time(NULL);

                    const char *otro_usuario = (strcmp(conexiones[conn_idx].usuario1, pkt.username) == 0)
                                                   ? conexiones[conn_idx].usuario2
                                                   : conexiones[conn_idx].usuario1;

                    printf("Conexión aceptada entre %s y %s\n",
                           conexiones[conn_idx].usuario1, conexiones[conn_idx].usuario2);
                    imprimir_estado_conexiones();

                    // Notificar a quien envió la solicitud
                    int idx_otro = encontrar_cliente_por_nombre(otro_usuario);
                    if (idx_otro >= 0)
                    {
                        packet_t confirm = {.code = ACEPTADO};
                        strncpy(confirm.username, pkt.username, MAX_NAME_LEN);
                        strncpy(confirm.dest, otro_usuario, MAX_NAME_LEN);
                        confirm.datalen = snprintf(confirm.data, sizeof(confirm.data), "Conexión aceptada por %s", pkt.username);
                        enviar_paquete(clients[idx_otro].sockfd, &confirm);
                    }

                    // Confirmación opcional para quien aceptó
                    int idx_yo = encontrar_cliente_por_nombre(pkt.username);
                    if (idx_yo >= 0)
                    {
                        packet_t conf = {.code = ACEPTADO};
                        strncpy(conf.username, otro_usuario, MAX_NAME_LEN);
                        strncpy(conf.dest, pkt.username, MAX_NAME_LEN);
                        conf.datalen = snprintf(conf.data, sizeof(conf.data),
                                                "Conexión con %s establecida correctamente", otro_usuario);
                        enviar_paquete(clients[idx_yo].sockfd, &conf);
                    }
                }
                else
                {
                    printf("La conexión ya no está en estado PENDIENTE\n");
                }
            }
            else
            {
                printf("No se encontró conexión entre %s y %s\n", pkt.username, pkt.dest);
            }
            break;
        }

        case RECHAZADO:
        {
            int conn_idx = buscar_conexion(pkt.dest, pkt.username);
            if (conn_idx >= 0 && conexiones[conn_idx].estado == PENDIENTE)
            {
                conexiones[conn_idx].estado = BLOQUEADO;
                conexiones[conn_idx].timestamp = time(NULL);
                strncpy(conexiones[conn_idx].bloqueador, pkt.username, MAX_NAME_LEN); // quien rechazó
                printf("Conexión rechazada (marcada como BLOQUEADO) entre %s y %s\n", pkt.dest, pkt.username);
                imprimir_estado_conexiones();
            }
            break;
        }

        case FILE_CODE:
        {
            int idx = encontrar_cliente_por_nombre(pkt.dest);
            if (idx >= 0)
            {
                int conn_idx = buscar_conexion(pkt.username, pkt.dest);
                if (conn_idx >= 0 && conexiones[conn_idx].estado == CONECTADO)
                {
                    printf("Enviando archivo de %s a %s\n", pkt.username, pkt.dest);
                    enviar_paquete(clients[idx].sockfd, &pkt);
                }
                else
                {
                    printf("Archivo descartado (%s -> %s) por estado no válido\n",
                           pkt.username, pkt.dest);
                }
            }
            break;
        }

        case FIN:
        {
            printf("Cliente %s pidió FIN\n", pkt.username);
            close(sd);
            clients[client_idx].sockfd = 0;
            eliminar_conexiones_de_usuario(pkt.username);
            pthread_exit(NULL);
        }
        }
    }

    return NULL;
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

            thread_args_t *args = malloc(sizeof(thread_args_t));
            args->client_idx = i;

            pthread_t hilo;
            pthread_create(&hilo, NULL, manejar_cliente, args);
            pthread_detach(hilo);
            break;
        }
    }
}
int main()
{
    int escuchandofd, maxfd, activity;
    struct sockaddr_in serv_addr;
    fd_set readfds;

    escuchandofd = socket(AF_INET, SOCK_STREAM, 0);
    serv_addr.sin_family = AF_INET;
    serv_addr.sin_addr.s_addr = INADDR_ANY;
    serv_addr.sin_port = htons(PORT);

    bind(escuchandofd, (struct sockaddr *)&serv_addr, sizeof(serv_addr));
    listen(escuchandofd, 5);

    for (int i = 0; i < MAX_CLIENTS; i++)
        clients[i].sockfd = 0;

    while (1)
    {
        FD_ZERO(&readfds);
        FD_SET(escuchandofd, &readfds);
        maxfd = escuchandofd;

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
    }

    return 0;
}
