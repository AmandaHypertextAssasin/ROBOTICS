#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <pthread.h>

// Static definitions
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

typedef struct {
    Client *clients;  // Pointer to store all connected client objects
    uint8_t *count;   // Pointer to client count
    uint8_t self;     // Our current client id
} Args;

Client *clients;
uint8_t client_count = 0;     // Current number of connected clients

pthread_mutex_t client_mutex = PTHREAD_MUTEX_INITIALIZER;  // Mutex to protect shared data

// Function to broadcast a message to all clients
void broadcast_message(const char *message) {
    pthread_mutex_lock(&client_mutex);  // Locking before iterating through clients
    for (int i = 0; i < client_count; i++) {
        send(clients[i].socket_fd, message, strlen(message), 0);  // Send to each client
    }
    pthread_mutex_unlock(&client_mutex);  // Unlocking after sending the message
}

// Function to find a client by IP address
Client *get_client_by_ip(const char *ip) {
    for (int i = 0; i < client_count; i++) {
        if (strcmp(clients[i].ip, ip) == 0) {
            return &clients[i];
        }
    }
    return NULL;
}

// Function to handle client commands in a separate thread
void *handle_client(void *arg) {
    Args *args = (Args *)arg;
    Client *client = &(args->clients[args->self]);  // Get the client data
    char buffer[BUFFER_SIZE];
    int bytes_received;

    printf("Client connected: %s\n", client->ip);

    // Main loop to process received messages
    while ((bytes_received = recv(client->socket_fd, buffer, BUFFER_SIZE - 1, 0)) > 0) {
        buffer[bytes_received] = '\0';  // Null-terminate the received buffer
        // Lazily sanitize buffer for printing later on.
        if (buffer[bytes_received-1] == '\n') buffer[bytes_received-1] = '\0';
        if (buffer[bytes_received-1] == '\r') buffer[bytes_received-1] = '\0';
        if (buffer[bytes_received-2] == '\n') buffer[bytes_received-2] = '\0';

        printf("Received from %s: %s\n", client->ip, buffer);

        char target_ip[INET_ADDRSTRLEN], command[BUFFER_SIZE], data[BUFFER_SIZE];

        // Parse the message and handle accordingly
        if (sscanf(buffer, "[%15[^]]] %s %[^\n]", target_ip, command, data) >= 2) {
            if (client->state == UNAUTHENTICATED) {
                // Handle authentication
                if (strcmp(target_ip, "0.0.0.0") == 0) {
                    if (strcmp(command, "slave") == 0) {
                        pthread_mutex_lock(&client_mutex);
                        client->state = SLAVE;
                        pthread_mutex_unlock(&client_mutex);
                        printf("Client %s authenticated as a slave\n", client->ip);
                    } else if (strcmp(command, "admin") == 0) {
                        pthread_mutex_lock(&client_mutex);
                        client->state = ADMIN;
                        pthread_mutex_unlock(&client_mutex);
                        printf("Client %s authenticated as an admin\n", client->ip);
                    } else {
                        send(client->socket_fd, "[0.0.0.0] Authentication required\n", 34, 0);
                    }
                }
            } else if (strcmp(command, "vote") == 0) {
                // Handle vote command
                printf("Vote initiated by %s\n", client->ip);
                broadcast_message("[0.0.0.0] vote\n");
                for (int i = 0; i < *args->count; i++) {
                    if (args->clients[i].state != ADMIN) {
                        pthread_mutex_lock(&client_mutex);
                        args->clients[i].vote_value = -1;  // Reset vote for slaves
                        args->clients[i].state = SLAVE; // Revert back to slave
                        pthread_mutex_unlock(&client_mutex);
                    }
                }
            } else if (strcmp(command, "clients") == 0) {
                // Handle clients listing command
                if (client->state == ADMIN || client->state == MASTER) {
                    uint8_t total_length = 0;
                    pthread_mutex_lock(&client_mutex);
                    for (uint8_t i = 0; i < *args->count; i++) {
                        total_length += strlen(args->clients[i].ip) + (i > 0 ? 1 : 0);
                    }
                    pthread_mutex_unlock(&client_mutex);
                    total_length += strlen(client->ip) + 5;

                    char *message = (char *)malloc(total_length);

                    message[0] = '\0';
                    strcat(message, "[");
                    strcat(message, client->ip);
                    strcat(message, "]");
                    for (uint8_t i = 0; i < *args->count; i++) {
                        strcat(message, " ");
                        strcat(message, clients[i].ip);
                    }
                    strcat(message, "\n");
                    broadcast_message(message);
                    free(message);
                } else {
                    send(client->socket_fd, "[0.0.0.0] Unauthorized command\n", 32, 0);
                }
            } else if (strcmp(command, "move") == 0 || strcmp(command, "stop") == 0 || strcmp(command, "reset") == 0) {
                // Handle move, stop, and reset commands
                if (client->state == ADMIN || client->state == MASTER) {
                    broadcast_message(buffer);  // Broadcast the command to all clients
                } else {
                    send(client->socket_fd, "[0.0.0.0] Unauthorized command\n", 32, 0);
                }
            } else if (client->state == SLAVE && strcmp(target_ip, "0.0.0.0") == 0) {
                // Handle vote submission by slave clients
                int vote = atoi(command);
                if (vote >= 0 && vote <= 255) {
                    pthread_mutex_lock(&client_mutex);
                    client->vote_value = vote;  // Set the vote value for the slave client
                    pthread_mutex_unlock(&client_mutex);
                    printf("Vote from slave %s: %d\n", client->ip, vote);

                    // Check if all votes are received
                    int all_votes_received = 1;
                    pthread_mutex_lock(&client_mutex);
                    for (int i = 0; i < *args->count; i++) {
                        if (args->clients[i].state == SLAVE && args->clients[i].vote_value == -1) {
                            all_votes_received = 0;
                            break;
                        }
                    }
                    pthread_mutex_unlock(&client_mutex);

                    if (all_votes_received) {
                        // All votes received, decide on the master (king)
                        int max_vote = -1;
                        Client *winner = NULL;
                        for (int i = 0; i < *args->count; i++) {
                            if (args->clients[i].state == SLAVE) {
                                printf("Client %s has score %d, ", args->clients[i].ip, args->clients[i].vote_value);
                                if (args->clients[i].vote_value > max_vote) {
                                    if (max_vote == -1) {
                                        // From NULL
                                        printf("setting the first score.\n");
                                    } else {
                                        // > max
                                        printf("beating %s's score of %d.\n", winner->ip, winner->vote_value);
                                    }
                                    max_vote = args->clients[i].vote_value;
                                    winner = &args->clients[i];
                                } else {
                                    // <max
                                    printf("not beating %s.\n", winner->ip);
                                }
                            }
                        }
                        if (winner) {
                            // Crown the winner as the master
                            pthread_mutex_lock(&client_mutex);
                            winner->state = MASTER;
                            char message[BUFFER_SIZE];
                            snprintf(message, sizeof(message), "[%s] master\n", winner->ip);
                            pthread_mutex_unlock(&client_mutex);
                            broadcast_message(message);
                            printf("Crowned: %s\n", winner->ip);
                        }
                    }
                }
            }
        }
    }

    printf("Client disconnected: %s. %d clients remain\n", client->ip, *args->count - 1);
    close(client->socket_fd);

    // Remove client from the list
    pthread_mutex_lock(&client_mutex);
    for (int i = 0; i < *args->count; i++) {
        if (args->clients[i].socket_fd == client->socket_fd) {
            args->clients[i] = args->clients[*args->count - 1];  // Replace with the last client
            (*args->count)--;  // Decrease client count
            break;
        }
    }
    pthread_mutex_unlock(&client_mutex);

    free(arg);  // Free the argument passed to the thread
    return NULL;
}

int main() {
    int server_fd;
    struct sockaddr_in server_addr, client_addr;
    socklen_t client_len = sizeof(client_addr);

    // Create server socket
    if ((server_fd = socket(AF_INET, SOCK_STREAM, 0)) < 0) {
        perror("Socket creation failed");
        exit(EXIT_FAILURE);
    }

    // Set socket options to reuse address
    int opt = 1;
    if (setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt)) < 0) {
        perror("Setsockopt failed");
        close(server_fd);
        exit(EXIT_FAILURE);
    }

    server_addr.sin_family = AF_INET;
    server_addr.sin_addr.s_addr = INADDR_ANY;
    server_addr.sin_port = htons(PORT);

    // Bind the socket
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

    // Allocate all client storage
    clients = malloc(sizeof(Client)*MAX_CLIENTS);

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
    free(clients);
    return 0;
}
