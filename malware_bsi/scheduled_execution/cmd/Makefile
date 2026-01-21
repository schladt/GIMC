# Compiler settings for task_cmd_bsi.c
CC = gcc
CFLAGS = -O2 -static -Wall -Wextra
LIBS = 

TARGET = task_cmd_bsi.exe
SOURCE = task_cmd_bsi.c

all: $(TARGET)

$(TARGET): $(SOURCE)
	$(CC) $(CFLAGS) $(SOURCE) -o $(TARGET) $(LIBS)

clean:
	rm -f $(TARGET) *.obj *.exe

run: $(TARGET)
	$(TARGET)

# MSVC alternative
msvc:
	cl /W3 /O2 $(SOURCE) /Fe$(TARGET)

.PHONY: all clean run msvc
