#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <pthread.h>

#define PORT 5080
#define MAX_CLIENTS 128
#define BUFFER_SIZE 128

// Auth states
typedef enum {
    UNAUTHENTICATED,
    SLAVE,
    ADMIN,
    MASTER
} ClientState;

// Client data object
typedef struct {
    int socket_fd;
    char ip[INET_ADDRSTRLEN];
    ClientState state;
    int vote_value;
} Client;

Client clients[MAX_CLIENTS];

typedef struct {
    Client *clients;
    uint8_t *count;
    uint8_t self;
} Args;

uint8_t client_count = 0;

pthread_mutex_t client_mutex = PTHREAD_MUTEX_INITIALIZER;

void broadcast_message(const char *message) {
    pthread_mutex_lock(&client_mutex);
    for (int i = 0; i < client_count; i++) {
        send(clients[i].socket_fd, message, strlen(message), 0);
    }
    pthread_mutex_unlock(&client_mutex);
}

Client *get_client_by_ip(const char *ip) {
    for (int i = 0; i < client_count; i++) {
        if (strcmp(clients[i].ip, ip) == 0) {
            return &clients[i];
        }
    }
    return NULL;
}

void *handle_client(void *arg) {
    Args *args = (Args *)arg;
    Client *client = &(args->clients[args->self]);
    char buffer[BUFFER_SIZE];
    int bytes_received;

    printf("Client connected: %s\n", client->ip);

    while ((bytes_received = recv(client->socket_fd, buffer, BUFFER_SIZE - 1, 0)) > 0) {
        buffer[bytes_received] = '\0';
        printf("Received from %s: %s\n", client->ip, buffer);

        char target_ip[INET_ADDRSTRLEN], command[BUFFER_SIZE], data[BUFFER_SIZE];
        if (sscanf(buffer, "[%15[^]]] %s %[^\n]", target_ip, command, data) >= 2) {
            if (client->state == UNAUTHENTICATED) {
                if (strcmp(target_ip, "0.0.0.0") == 0 && strcmp(command, "slave") == 0) {
                    client->state = SLAVE;
                    printf("Client %s authenticated as SLAVE\n", client->ip);
                } else if (strcmp(target_ip, "0.0.0.0") == 0 && strcmp(command, "admin") == 0) {
                    client->state = ADMIN;
                    printf("Client %s authenticated as ADMIN\n", client->ip);
                    pthread_mutex_lock(&client_mutex);
                    pthread_mutex_unlock(&client_mutex);
                } else {
                    send(client->socket_fd, "[0.0.0.0] Authentication required\n", 34, 0);
                    continue;
                }
            } else if (strcmp(command, "vote") == 0) {
                printf("Vote initiated by %s\n", client->ip);
                broadcast_message("[0.0.0.0] vote\n");
                pthread_mutex_lock(&client_mutex);
                for (int i = 0; i < *args->count; i++) {
                    if (args->clients[i].state != ADMIN) {
                        args->clients[i].vote_value = 0;
                        args->clients[i].state = SLAVE;
                    }
                }
                pthread_mutex_unlock(&client_mutex);
            } else if (strcmp(command, "clients") == 0) {
                if (client->state == ADMIN || client->state == MASTER) {
                    uint8_t total_length = 0;
                    for (uint8_t i = 0; i < *args->count; i++) {
                        total_length += strlen(args->clients[i].ip) + (i > 0 ? 1 : 0);
                    }
                    total_length += strlen(client->ip) + 3;

                    char *message = (char *)malloc(total_length);

                    message[0] = '\0';
                    strcat(message, "[");
                    strcat(message, client->ip);
                    strcat(message, "]");
                    for (uint8_t i = 0; i < *args->count; i++) {
                        strcat(message, " ");
                        strcat(message, clients[i].ip);
                    }
                    pthread_mutex_unlock(&client_mutex);
                    broadcast_message(message);
                    pthread_mutex_unlock(&client_mutex);
                } else {
                    send(client->socket_fd, "[0.0.0.0] Unauthorized command\n", 32, 0);
                }
            } else if (strcmp(command, "move") == 0 || strcmp(command, "stop") == 0 || strcmp(command, "reset") == 0) {
                if (client->state == ADMIN || client->state == MASTER) {
                    broadcast_message(buffer);
                } else {
                    send(client->socket_fd, "[0.0.0.0] Unauthorized command\n", 32, 0);
                }
            } else if (client->state == SLAVE && strcmp(target_ip, "0.0.0.0") == 0) {
                int vote = atoi(command);
                if (vote >= 0 && vote <= 255) {
                    pthread_mutex_lock(&client_mutex);
                    client->vote_value = vote;
                    printf("Vote from SLAVE %s: %d\n", client->ip, vote);
                    int all_votes_received = 1;
                    for (int i = 0; i < *args->count; i++) {
                        if (args->clients[i].state == SLAVE && args->clients[i].vote_value == -1) {
                            all_votes_received = 0;
                            break;
                        }
                    }
                    if (all_votes_received) {
                        printf("Deciding on king (%d current clients)..\n", *args->count);
                        int max_vote = -1;
                        Client *winner = NULL;
                        for (int i = 0; i < *args->count; i++) {
                            if (args->clients[i].state == SLAVE) {
                                printf("Client %s has score %d, ", args->clients[i].ip, args->clients[i].vote_value);
                                if (args->clients[i].vote_value > max_vote) {
                                    if (max_vote == -1) {
                                        printf("setting the first score.\n");
                                    } else {
                                        printf("beating %s's score of %d.\n", winner->ip, winner->vote_value);
                                    }
                                    max_vote = args->clients[i].vote_value;
                                    winner = &args->clients[i];
                                } else {
                                    printf("not beating %s.\n", winner->ip);
                                }
                            }
                        }
                        if (max_vote != -1) {
                            winner->state = MASTER;
                            char message[BUFFER_SIZE];
                            snprintf(message, sizeof(message), "[%s] master\n", winner->ip);
                            pthread_mutex_unlock(&client_mutex);
                            broadcast_message(message);
                            pthread_mutex_lock(&client_mutex);
                            printf("Crowned: %s\n", winner->ip);
                        }
                    }
                    pthread_mutex_unlock(&client_mutex);
                }
            }
        }
    }

    printf("Client disconnected: %s. %d clients remain\n", client->ip, *args->count-1);
    close(client->socket_fd);

    pthread_mutex_lock(&client_mutex);
    for (int i = 0; i < *args->count; i++) {
        if (args->clients[i].socket_fd == client->socket_fd) {
            args->clients[i] = args->clients[*args->count-1];
            *args->count -= 1;
            break;
        }
    }
    pthread_mutex_unlock(&client_mutex);

    free(arg);
    return NULL;
}

int main() {
    int server_fd;
    struct sockaddr_in server_addr, client_addr;
    socklen_t client_len = sizeof(client_addr);

    if ((server_fd = socket(AF_INET, SOCK_STREAM, 0)) < 0) {
        perror("Socket creation failed");
        exit(EXIT_FAILURE);
    }

    int opt = 1;
    if (setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt)) < 0) {
        perror("Setsockopt failed");
        close(server_fd);
        exit(EXIT_FAILURE);
    }

    server_addr.sin_family = AF_INET;
    server_addr.sin_addr.s_addr = INADDR_ANY;
    server_addr.sin_port = htons(PORT);

    if (bind(server_fd, (struct sockaddr *)&server_addr, sizeof(server_addr)) < 0) {
        perror("Bind failed");
        close(server_fd);
        exit(EXIT_FAILURE);
    }

    if (listen(server_fd, MAX_CLIENTS) < 0) {
        perror("Listen failed");
        close(server_fd);
        exit(EXIT_FAILURE);
    }

    printf("Server listening on port %d\n", PORT);

    while (1) {
        int client_fd = accept(server_fd, (struct sockaddr *)&client_addr, &client_len);
        if (client_fd < 0) {
            perror("Accept failed");
            continue;
        }

        char client_ip[INET_ADDRSTRLEN];
        inet_ntop(AF_INET, &client_addr.sin_addr, client_ip, INET_ADDRSTRLEN);

        Client *new_client = malloc(sizeof(Client));
        new_client->socket_fd = client_fd;
        strncpy(new_client->ip, client_ip, INET_ADDRSTRLEN);
        new_client->state = UNAUTHENTICATED;
        new_client->vote_value = -1;

        pthread_mutex_lock(&client_mutex);
        if (client_count < MAX_CLIENTS) {
            clients[client_count++] = *new_client;
            pthread_mutex_unlock(&client_mutex);

            pthread_t client_thread;
            Args *new_args = malloc(sizeof(Args));
            new_args->clients = clients;
            new_args->count = &client_count;
            new_args->self = client_count - 1;
            pthread_create(&client_thread, NULL, handle_client, new_args);
            pthread_detach(client_thread);
        } else {
            pthread_mutex_unlock(&client_mutex);
            printf("Max clients reached. Connection from %s refused.\n", client_ip);
            close(client_fd);
            free(new_client);
        }
    }

    close(server_fd);
    return 0;
}
