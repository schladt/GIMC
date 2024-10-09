#include <stdio.h>
#include <time.h>
#include <windows.h>

int main() {
    // Get the current system time
    SYSTEMTIME st;
    GetSystemTime(&st);

    // Open file for writing
    FILE *file = fopen("current_time.txt", "w");
    if (file == NULL) {
        perror("Error opening file");
        return 1;
    }

    // Write the current time to the file
    fprintf(file, "Current system time: %02d-%02d-%04d %02d:%02d:%02d\n",
            st.wDay, st.wMonth, st.wYear, st.wHour, st.wMinute, st.wSecond);

    // Close the file
    fclose(file);

    printf("File written successfully.\n");

    return 0;
}
