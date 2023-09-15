// Test program for persistence written in C
// NOTE: Although this program is completely benign, it is detected as a threat by most antivirus software

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <winsock2.h>
#include <windows.h>
#include <shlobj.h>

#define PORT 4444
#define BUFF_SIZE 1024

void copy_to_appdata() {
    char path[MAX_PATH];
    char currentPath[MAX_PATH];
    
    GetModuleFileName(NULL, currentPath, sizeof(currentPath));
    SHGetFolderPath(NULL, CSIDL_APPDATA, NULL, 0, path);
    strcat(path, "\\test_program.exe");

    CopyFile(currentPath, path, FALSE);
}

void set_registry_run() {
    HKEY hKey;
    char path[MAX_PATH];

    SHGetFolderPath(NULL, CSIDL_APPDATA, NULL, 0, path);
    strcat(path, "\\test_program.exe");

    RegOpenKeyEx(HKEY_CURRENT_USER, "Software\\Microsoft\\Windows\\CurrentVersion\\Run", 0, KEY_SET_VALUE, &hKey);
    RegSetValueEx(hKey, "TestProgram", 0, REG_SZ, (BYTE*)path, strlen(path) + 1);
    RegCloseKey(hKey);
}

void start_listener() {
    WSADATA wsaData;
    SOCKET serverSocket, clientSocket;
    struct sockaddr_in server, client;
    char buffer[BUFF_SIZE] = "hello";
    int c;

    WSAStartup(MAKEWORD(2,2), &wsaData);
    serverSocket = socket(AF_INET, SOCK_STREAM, 0);

    server.sin_family = AF_INET;
    server.sin_addr.s_addr = INADDR_ANY;
    server.sin_port = htons(PORT);

    bind(serverSocket, (struct sockaddr*)&server, sizeof(server));
    listen(serverSocket, 5);

    puts("Listening for connections...");
    c = sizeof(struct sockaddr_in);
    clientSocket = accept(serverSocket, (struct sockaddr*)&client, &c);
    send(clientSocket, buffer, strlen(buffer), 0);

    closesocket(clientSocket);
    closesocket(serverSocket);
    WSACleanup();
}

int main(int argc, char *argv[]) {
    // command line option to uninstall
    if (argc > 1 && strcmp(argv[1], "-u") == 0) {
        HKEY hKey;
        char path[MAX_PATH];

        SHGetFolderPath(NULL, CSIDL_APPDATA, NULL, 0, path);
        strcat(path, "\\test_program.exe");

        RegOpenKeyEx(HKEY_CURRENT_USER, "Software\\Microsoft\\Windows\\CurrentVersion\\Run", 0, KEY_SET_VALUE, &hKey);
        RegDeleteValue(hKey, "TestProgram");
        RegCloseKey(hKey);

        remove(path);
        return 0;
    }

    copy_to_appdata();
    set_registry_run();
    start_listener();

    return 0;
}