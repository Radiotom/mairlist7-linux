#!/usr/bin/env python3
"""
Patch für ftd2xx-wine (unixlib.c): korrekte Handle- und Struct-Übersetzung
für 32-Bit-Programme (WoW64), z.B. mAirList 7 (FTChipID.dll).

Problem im Original:
  * FT_Open/FT_OpenEx schreiben einen 64-Bit-Handle (Heap-Pointer > 4 GB)
    in ein 32-Bit-Feld -> Handle wird abgeschnitten, 4 Byte Speicher
    dahinter werden überschrieben.
  * FT_GetDeviceInfoList schreibt 64-Bit-Strukturen (104 Byte) in ein
    32-Bit-Array (100 Byte/Eintrag) -> Pufferüberlauf, falsche Einträge.
Lösung:
  * Handle-Tabelle: 32-Bit-Programme bekommen kleine IDs, die intern auf
    die echten 64-Bit-Handles abgebildet werden.
  * FT_GetDeviceInfoList/FT_GetDeviceInfoDetail werden in einen
    temporären 64-Bit-Puffer gelesen und ins 32-Bit-Layout umkopiert.
Aufruf: python3 patch-ftd2xx-wow64.py <pfad/zu/unixlib.c>
"""
import re
import sys

path = sys.argv[1]
src = open(path, encoding="utf-8").read()
if "h32_get(" in src:
    print("bereits gepatcht")
    sys.exit(0)

helpers = r'''
/* ---- WoW64-Handle-Tabelle (mAirList-Patch) ---- */
#include <pthread.h>
#include <stdlib.h>
#include <string.h>
#define H32_MAX  256
#define H32_BASE 0x1000u
static FT_HANDLE h32_table[H32_MAX];
static pthread_mutex_t h32_lock = PTHREAD_MUTEX_INITIALIZER;

static uint32_t h32_put(FT_HANDLE h)
{
    uint32_t i, ret = 0;
    if (!h) return 0;
    pthread_mutex_lock(&h32_lock);
    for (i = 0; i < H32_MAX; i++)
        if (h32_table[i] == h) { ret = H32_BASE + i; goto out; }
    for (i = 0; i < H32_MAX; i++)
        if (!h32_table[i]) { h32_table[i] = h; ret = H32_BASE + i; goto out; }
out:
    pthread_mutex_unlock(&h32_lock);
    return ret;
}

static FT_HANDLE h32_get(uint32_t v)
{
    FT_HANDLE h = NULL;
    if (v < H32_BASE || v >= H32_BASE + H32_MAX) return NULL;
    pthread_mutex_lock(&h32_lock);
    h = h32_table[v - H32_BASE];
    pthread_mutex_unlock(&h32_lock);
    return h;
}

static void h32_del(uint32_t v)
{
    if (v < H32_BASE || v >= H32_BASE + H32_MAX) return;
    pthread_mutex_lock(&h32_lock);
    h32_table[v - H32_BASE] = NULL;
    pthread_mutex_unlock(&h32_lock);
}

/* 32-Bit-Layout von FT_DEVICE_LIST_INFO_NODE */
typedef struct {
    DWORD Flags; DWORD Type; DWORD ID; DWORD LocId;
    char SerialNumber[16]; char Description[64];
    uint32_t ftHandle;
} FT_DEVICE_LIST_INFO_NODE32;
/* ---- Ende Handle-Tabelle ---- */
'''

anchor = "static inline void *ULongToPtr(uint32_t ul)\n{\n    return (void *)(uint64_t)ul;\n}\n"
assert anchor in src, "Anker ULongToPtr nicht gefunden"
src = src.replace(anchor, anchor + helpers, 1)

# Alle Handle-Argumente der 32-Bit-Thunks über die Tabelle auflösen
src = src.replace("(FT_HANDLE)ULongToPtr(a->ftHandle)", "h32_get(a->ftHandle)")


def replace_func(name, body):
    global src
    pat = re.compile(r"NTSTATUS wow64_wrap_%s\(void \*args\) \{.*?\n\}\n" % re.escape(name), re.S)
    assert pat.search(src), name
    src = pat.sub(lambda m: body, src, count=1)


replace_func("FT_Open", '''NTSTATUS wow64_wrap_FT_Open(void *args) {
    struct p32_FT_Open *a = args;
    FT_HANDLE h = NULL;
    a->ret = FT_Open(a->deviceNumber, &h);
    if (a->ret == FT_OK) {
        uint32_t id = h32_put(h);
        if (!id) { FT_Close(h); a->ret = FT_INSUFFICIENT_RESOURCES; }
        else if (a->pHandle) *(uint32_t *)ULongToPtr(a->pHandle) = id;
    }
    return STATUS_SUCCESS;
}
''')

replace_func("FT_OpenEx", '''NTSTATUS wow64_wrap_FT_OpenEx(void *args) {
    struct p32_FT_OpenEx *a = args;
    FT_HANDLE h = NULL;
    a->ret = FT_OpenEx((PVOID)ULongToPtr(a->pvArg1), a->dwFlags, &h);
    if (a->ret == FT_OK) {
        uint32_t id = h32_put(h);
        if (!id) { FT_Close(h); a->ret = FT_INSUFFICIENT_RESOURCES; }
        else if (a->pHandle) *(uint32_t *)ULongToPtr(a->pHandle) = id;
    }
    return STATUS_SUCCESS;
}
''')

replace_func("FT_Close", '''NTSTATUS wow64_wrap_FT_Close(void *args) {
    struct p32_FT_Close *a = args;
    a->ret = FT_Close(h32_get(a->ftHandle));
    if (a->ret == FT_OK) h32_del(a->ftHandle);
    return STATUS_SUCCESS;
}
''')

replace_func("FT_GetDeviceInfoList", '''NTSTATUS wow64_wrap_FT_GetDeviceInfoList(void *args) {
    struct p32_FT_GetDeviceInfoList *a = args;
    FT_DEVICE_LIST_INFO_NODE32 *dst = ULongToPtr(a->pDest);
    FT_DEVICE_LIST_INFO_NODE *tmp;
    DWORD n = 0, i;
    tmp = calloc(128, sizeof(*tmp));
    if (!tmp) { a->ret = FT_INSUFFICIENT_RESOURCES; return STATUS_SUCCESS; }
    a->ret = FT_GetDeviceInfoList(tmp, &n);
    if (a->ret == FT_OK && dst) {
        for (i = 0; i < n && i < 128; i++) {
            dst[i].Flags = tmp[i].Flags;
            dst[i].Type  = tmp[i].Type;
            dst[i].ID    = tmp[i].ID;
            dst[i].LocId = tmp[i].LocId;
            memcpy(dst[i].SerialNumber, tmp[i].SerialNumber, 16);
            memcpy(dst[i].Description,  tmp[i].Description, 64);
            dst[i].ftHandle = h32_put(tmp[i].ftHandle);
        }
    }
    if (a->lpdwNumDevs) *(DWORD *)ULongToPtr(a->lpdwNumDevs) = n;
    free(tmp);
    return STATUS_SUCCESS;
}
''')

replace_func("FT_GetDeviceInfoDetail", '''NTSTATUS wow64_wrap_FT_GetDeviceInfoDetail(void *args) {
    struct p32_FT_GetDeviceInfoDetail *a = args;
    FT_HANDLE h = NULL;
    a->ret = FT_GetDeviceInfoDetail(a->dwIndex, (LPDWORD)ULongToPtr(a->lpdwFlags), (LPDWORD)ULongToPtr(a->lpdwType), (LPDWORD)ULongToPtr(a->lpdwID), (LPDWORD)ULongToPtr(a->lpdwLocId), (LPVOID)ULongToPtr(a->lpSerialNumber), (LPVOID)ULongToPtr(a->lpDescription), &h);
    if (a->ret == FT_OK && a->pftHandle) *(uint32_t *)ULongToPtr(a->pftHandle) = h32_put(h);
    return STATUS_SUCCESS;
}
''')

open(path, "w", encoding="utf-8").write(src)
print("unixlib.c gepatcht")
