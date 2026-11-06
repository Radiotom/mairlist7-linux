/*
 * ftdi-dongle-test.c – prüft den FTDI-Dongle unter Wine so, wie mAirList
 * (FTChipID.dll) es tut: Geräteliste, Öffnen per Seriennummer,
 * GetDeviceInfo, EEPROM lesen, Schließen.
 * Bau (32 Bit, wie mAirList):
 *   winegcc --target=i686-windows ftdi-dongle-test.c -o ftdi-dongle-test.exe
 */
#include <windows.h>
#include <stdio.h>

typedef ULONG FT_STATUS;
typedef PVOID FT_HANDLE;
typedef struct {
    ULONG Flags, Type, ID;
    DWORD LocId;
    char SerialNumber[16];
    char Description[64];
    FT_HANDLE ftHandle;
} NODE;

typedef FT_STATUS (WINAPI *pCreate)(LPDWORD);
typedef FT_STATUS (WINAPI *pGetList)(NODE *, LPDWORD);
typedef FT_STATUS (WINAPI *pOpenEx)(PVOID, DWORD, FT_HANDLE *);
typedef FT_STATUS (WINAPI *pGetInfo)(FT_HANDLE, ULONG *, LPDWORD, PCHAR, PCHAR, LPVOID);
typedef FT_STATUS (WINAPI *pReadEE)(FT_HANDLE, DWORD, LPWORD);
typedef FT_STATUS (WINAPI *pClose)(FT_HANDLE);

int main(void)
{
    HMODULE m = LoadLibraryA("ftd2xx.dll");
    DWORD n = 0, i;
    NODE list[16];
    if (!m) { printf("FEHLER: ftd2xx.dll nicht ladbar\n"); return 1; }
    /* Import per Ordinal – genau wie FTChipID.dll */
    pCreate  Create  = (pCreate) GetProcAddress(m, (LPCSTR)70);
    pGetList GetList = (pGetList)GetProcAddress(m, (LPCSTR)71);
    pOpenEx  OpenEx  = (pOpenEx) GetProcAddress(m, (LPCSTR)27);
    pGetInfo GetInfo = (pGetInfo)GetProcAddress(m, (LPCSTR)61);
    pReadEE  ReadEE  = (pReadEE) GetProcAddress(m, (LPCSTR)35);
    pClose   Close   = (pClose)  GetProcAddress(m, (LPCSTR)2);
    if (!Create || !GetList || !OpenEx || !GetInfo || !ReadEE || !Close) {
        printf("FEHLER: Ordinals fehlen\n"); return 1;
    }
    { FT_STATUS s0 = Create(&n); printf("FT_CreateDeviceInfoList: %lu, Geraete: %lu\n", s0, n); }
    if (n == 0) { printf("Kein FTDI-Geraet gefunden.\n"); return 2; }
    if (n > 16) n = 16;
    printf("FT_GetDeviceInfoList: %lu\n", GetList(list, &n));
    for (i = 0; i < n; i++)
        printf("  [%lu] Typ=%lu ID=%08lx SN='%s' Beschreibung='%s' Flags=%lu\n",
               i, list[i].Type, list[i].ID, list[i].SerialNumber,
               list[i].Description, list[i].Flags);

    for (i = 0; i < n; i++) {
        FT_HANDLE h = NULL;
        ULONG type; DWORD id; char sn[16] = {0}, desc[64] = {0};
        WORD w; DWORD off; int ok = 1;
        FT_STATUS s = OpenEx(list[i].SerialNumber, 1 /* FT_OPEN_BY_SERIAL_NUMBER */, &h);
        printf("FT_OpenEx('%s'): %lu Handle=%p\n", list[i].SerialNumber, s, h);
        if (s) { printf("  -> Oeffnen fehlgeschlagen (ftdi_sio gebunden? Rechte?)\n"); continue; }
        s = GetInfo(h, &type, &id, sn, desc, NULL);
        printf("FT_GetDeviceInfo: %lu Typ=%lu ID=%08lx SN='%s' '%s'\n", s, type, id, sn, desc);
        printf("EEPROM (erste 16 Worte):");
        for (off = 0; off < 16; off++) {
            if (ReadEE(h, off, &w)) { ok = 0; break; }
            printf(" %04x", w);
        }
        printf(ok ? "\n" : " FEHLER beim Lesen\n");
        printf("FT_Close: %lu\n", Close(h));
    }
    printf("TEST FERTIG\n");
    return 0;
}
