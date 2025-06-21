CC=gcc
CFLAGS=-Wall -Werror -g -pthread 
BIN=./bin

PROGS=server-chat server-chat-prueba

.PHONY: all
all: $(PROGS)

LIST=$(addprefix $(BIN)/, $(PROGS))

server-chat: server-chat.c 
	$(CC) -o bin/$@ $^ $(CFLAGS)

server-chat-prueba: server-chat-prueba.c 
	$(CC) -o bin/$@ $^ $(CFLAGS)

.PHONY: clean
clean:
	rm -f $(LIST)
