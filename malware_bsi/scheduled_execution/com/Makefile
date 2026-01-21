# Compiler settings for task_com_bsi.cpp
CXX = g++
CXXFLAGS = -O2 -static -Wall -Wextra
LIBS = -lole32 -loleaut32 -ltaskschd

TARGET = task_com_bsi.exe
SOURCE = task_com_bsi.cpp

all: $(TARGET)

$(TARGET): $(SOURCE)
	$(CXX) $(CXXFLAGS) $(SOURCE) -o $(TARGET) $(LIBS)

clean:
	rm -f $(TARGET) *.obj *.exe

run: $(TARGET)
	$(TARGET)

# MSVC alternative
msvc:
	cl /EHsc /W3 /O2 $(SOURCE) /Fe$(TARGET) /link ole32.lib oleaut32.lib taskschd.lib

.PHONY: all clean run msvc
