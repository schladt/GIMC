# Name of the source file
SRC = persistence.c

# Name of the output file
OUT = test_persistence.exe

# Compiler
CC = gcc

# Compiler Flags
CFLAGS = -Wall -Wextra

# Libraries to link against
LIBS = -lws2_32

all: $(OUT)

$(OUT): $(SRC)
	$(CC) $(CFLAGS) $^ -o $@ $(LIBS)

clean:
	rm -f $(OUT)