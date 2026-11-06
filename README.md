# mAirList 7 unter Linux – mit FTDI-Dongle und USB-Audio

Anleitung und Skripte, um die Radio-Automationssoftware **mAirList 7** unter
Linux (getestet auf **CachyOS**, funktioniert auf allen Arch-basierten
Distributionen) mit **Wine** zu betreiben – inklusive **Lizenzaktivierung per
FTDI-USB-Dongle** und **USB-Audiogeräten**.

> Dies ist ein Community-Projekt und steht in keiner Verbindung zu mAirList.
> mAirList selbst ist kommerzielle Software und wird hier **nicht**
> mitgeliefert – das Skript lädt den offiziellen Installer herunter.

## Getestete Konfiguration

| Komponente     | Version / Gerät                                         | Status |
| -------------- | ------------------------------------------------------- | ------ |
| Distribution   | CachyOS (Kernel 7.3), KDE Plasma 6.8 (Wayland)          | ✅ |
| Wine           | 11.21 (Arch-Paket `wine`, reiner WoW64-Modus)           | ✅ |
| mAirList       | 7.4.12 (32-Bit)                                         | ✅ startet, läuft |
| Lizenz-Dongle  | „FTDI USB-Key“ (FT232R, VID:PID `0403:6001`)            | ✅ erkannt, Lizenz aktiviert |
| Audio          | Yamaha AG06/AG03 (USB) über PipeWire                    | ✅ in mAirList sichtbar |
| Audio-Ausgabe  | DirectSound / WASAPI über Wine → PipeWire               | ✅ |
| Datenbank      | mAirList-Datenbank als Internet-Client                  | ✅ erfolgreich getestet |
| Lokale DB      | neue lokale Datenbank (`*.mldb`) anlegen                | ✅ funktioniert |
| Musikimport    | Import von Musik in die Datenbank                       | ✅ funktioniert |
| Mikrofon       | Aufnahme über den USB-Eingang (Yamaha AG06)             | ✅ funktioniert |
| Voice Tracking | Mikrofoneingang im VT-Editor                            | ✅ funktioniert |
| Rechner-Neustart | Dongle nach dem Booten automatisch freigegeben        | ✅ funktioniert (`ACTION=="bind"`) |
| Neustart       | mAirList beenden und neu starten                        | ✅ Lizenz aktiv, Audioeinstellungen bleiben erhalten |

## Schnellstart

```bash
git clone https://github.com/Radiotom/mairlist7-linux.git
cd mairlist7-linux
./install.sh
```

Das Skript fragt einmal nach deinem `sudo`-Passwort und erledigt dann alles
(siehe [Was das Skript macht](#was-das-skript-macht)). Danach:

1. Dongle und Audiogeräte einstecken.
2. Dongle prüfen (optional):
   ```bash
   WINEPREFIX=~/.wine-mairlist wine ~/.cache/mairlist7-linux/ftdi-dongle-test.exe
   ```
   Erwartete Ausgabe (Seriennummer variiert):
   ```
   FT_CreateDeviceInfoList: 0, Geraete: 1
     [0] Typ=5 ID=04036001 SN='FT2XXXXX' Beschreibung='FTDI USB-Key' Flags=0
   FT_OpenEx('FT2XXXXX'): 0 Handle=00001000
   EEPROM (erste 16 Worte): 4008 0403 6001 ...
   FT_Close: 0
   ```
3. mAirList über das Startmenü starten (*Wine → Programs → mAirList 7*).
4. Lizenz aktivieren (siehe unten).

## ⚠️ Wichtig: nach Systemupdates

Die FTDI-Brücke (`ftd2xx.so` / `ftd2xx.dll`) wird gegen die installierte
Wine-Version gebaut. Wenn nach einem Systemupdate (`sudo pacman -Syu`) mit
einer **neuen Wine-Version** die Lizenz nicht mehr erkannt wird (mAirList
startet im Demo-Modus, der Dongle fehlt im Lizenzmanager), muss die Brücke
**neu gebaut** werden. Dafür einfach das Installationsskript erneut ausführen:

```bash
cd mairlist7-linux
git pull
./install.sh
```

Deine mAirList-Einstellungen, die Lizenz und die Datenbanken bleiben dabei
erhalten. Das Skript baut die Brücke neu und installiert mAirList über die
bestehende Installation.

Die installierte Wine-Version zeigt `wine --version` an. Wer Überraschungen
vermeiden will, prüft nach jedem Update kurz mit dem Dongle-Test (siehe oben),
ob der Dongle noch erkannt wird.

## Wie es funktioniert

### Das Dongle-Problem

mAirList nutzt für die Dongle-Aktivierung FTDI-USB-Chips (FT232R/FT485R). Der
Zugriff läuft über die mitgelieferte `FTChipID.dll`, die wiederum den
**FTDI-D2XX-Treiber** `FTD2XX.dll` aufruft – und zwar **per Ordinalnummer**
(`FT_Close`=2, `FT_OpenEx`=27, `FT_ReadEE`=35, `FT_GetDeviceInfo`=61,
`FT_CreateDeviceInfoList`=70, `FT_GetDeviceInfoList`=71, außerdem
`FT_EE_UARead`).

Unter Windows spricht `FTD2XX.dll` mit einem Kernel-Treiber. Den gibt es unter
Wine nicht. Deshalb wird hier eine **Brücken-DLL** eingesetzt:

```
mAirList.exe (32 Bit)
  └─ FTChipID.dll
       └─ ftd2xx.dll   ← Wine-Builtin aus ftd2xx-wine (PE, 32 Bit)
            └─ WoW64-Thunk
                 └─ ftd2xx.so  ← Unix-Seite, gelinkt gegen libftd2xx (FTDI, Linux)
                      └─ libusb → USB-Dongle
```

Grundlage ist das Projekt
[aselafernando/ftd2xx-wine](https://github.com/aselafernando/ftd2xx-wine)
(GPLv2), das genau für moderne Wine-Versionen im WoW64-Modus gebaut ist.

### Der WoW64-Patch (wichtig!)

Im Original funktioniert ftd2xx-wine nur für **64-Bit**-Programme zuverlässig.
mAirList ist aber ein **32-Bit**-Programm. Zwei Fehler verhindern dort den
Betrieb:

1. **Handles:** `FT_Open`/`FT_OpenEx` liefern einen 64-Bit-Zeiger der
   Linux-Bibliothek zurück. Der wurde in das 4-Byte-Feld des 32-Bit-Programms
   geschrieben – abgeschnitten, und 4 Byte Nachbarspeicher wurden überschrieben.
2. **Geräteliste:** `FT_DEVICE_LIST_INFO_NODE` ist in 64 Bit 104 Byte groß,
   in 32 Bit nur 100 Byte. Die Liste wurde ungeprüft in den 32-Bit-Puffer
   geschrieben (Pufferüberlauf, verschobene Einträge).

Der Patch [`patches/ftd2xx-wine-wow64-handles.patch`](patches/ftd2xx-wine-wow64-handles.patch)
behebt das:

* eine **Handle-Tabelle**: 32-Bit-Programme bekommen kleine IDs
  (`0x1000`, `0x1001`, …), die intern auf die echten 64-Bit-Handles zeigen;
* `FT_GetDeviceInfoList` und `FT_GetDeviceInfoDetail` lesen in einen
  64-Bit-Puffer und kopieren ins 32-Bit-Layout um.

(Der Patch wird von [`tools/patch-ftd2xx-wow64.py`](tools/patch-ftd2xx-wow64.py)
erzeugt, falls du ihn auf eine neuere ftd2xx-wine-Version anwenden willst.)

### Der Kernel-Treiber `ftdi_sio`

Linux bindet FTDI-Chips automatisch an den seriellen Treiber `ftdi_sio`
(`/dev/ttyUSB0`). Solange das passiert, meldet der D2XX-Treiber das Gerät als
„belegt“ (`Flags=1`, `FT_OpenEx` → Fehler 2 / `FT_DEVICE_NOT_FOUND`).

Die udev-Regel [`udev/99-mairlist-ftdi.rules`](udev/99-mairlist-ftdi.rules)

* gibt normalen Benutzern Zugriff auf FTDI-USB-Geräte (`MODE="0666"`, `uaccess`),
* löst **nur Geräte mit dem Produktnamen „FTDI USB-Key“** (der von mAirList
  empfohlene Dongle) automatisch von `ftdi_sio`. Andere USB-Seriell-Adapter
  bleiben unberührt.

> **Wichtig: `ACTION=="bind"`, nicht `"add"`.** Beim Hochfahren meldet der
> Kernel den Dongle (`add`), *bevor* das Modul `ftdi_sio` geladen ist. Der
> Treiber bindet erst Sekunden später, und das löst ein eigenes
> `bind`-Ereignis aus. Eine Regel auf `add` greift deshalb nur beim Einstecken
> im laufenden Betrieb, nach einem Neustart aber nicht.

Hat dein Dongle einen anderen Produktnamen, findest du ihn mit
`journalctl -k | grep -A3 "idVendor=0403"` und passt `ATTRS{product}` an –
oder du nutzt stattdessen die Seriennummer: `ATTRS{serial}=="FT2XXXXX"`.

### Audio

Wine gibt alle PipeWire/PulseAudio-Geräte an Windows-Programme weiter. In
mAirList unter *Konfiguration → Audiogeräte* einfach **DirectSound** oder
**WASAPI** wählen – USB-Interfaces erscheinen dort mit ihrem Namen (z. B.
„AG06/AG03“). Für Ein-/Ausgänge und Pegel hilft `pavucontrol`.

Tipps:

* Das Gerät in PipeWire auf **48 kHz** lassen und in mAirList dieselbe Rate
  wählen, dann wird nicht resampelt.
* Bei Aussetzern die Puffergröße in mAirList erhöhen oder Wine eine höhere
  Latenz geben: `PULSE_LATENCY_MSEC=60 wine mAirList.exe`.
* Mehrere USB-Geräte werden als getrennte Geräte angezeigt und können in
  mAirList unterschiedlichen Playern/Kanälen zugewiesen werden.

## Lizenz per Dongle aktivieren

1. mAirList starten → **Lizenzmanager** öffnen → erweiterte Ansicht.
2. Reiter **Dongles → FTDI** → **Reload**. Der Dongle erscheint mit
   Seriennummer und Beschreibung.
3. Neuer Dongle: auswählen → **Initialize** → Code kopieren → an den
   mAirList-Support senden. Nach Bestätigung im Lizenzmanager die Lizenzdatei
   neu herunterladen.
   Bereits initialisierter Dongle: Lizenzdatei neu herunterladen.

Details: [offizielle Lizenz-Dokumentation](https://mairlist.docs.mairlist.com/licensing/).

## Was das Skript macht

| Schritt | Aktion |
| ------- | ------ |
| 1 | `pacman`: `wine`, `wine-mono`, `wine-gecko`, `winetricks`, `clang`, `lld`, `git`, `wget`, `make`, `pavucontrol` … |
| 2 | udev-Regel nach `/etc/udev/rules.d/` und eingesteckten Dongle von `ftdi_sio` lösen |
| 3 | `ftd2xx-wine` klonen (Commit `206869c`), Patch anwenden, bauen (lädt `libftd2xx 1.4.34` von ftdichip.com) |
| 4 | `ftd2xx.so`/`ftd2xx.dll` nach `/usr/lib/wine/…` und in den Prefix `~/.wine-mairlist` kopieren |
| 5 | offiziellen mAirList-7-Installer laden und still installieren |
| 6 | Dongle-Testprogramm `ftdi-dongle-test.exe` bauen |

### Manuelle Installation

Wer lieber Schritt für Schritt vorgeht:

```bash
sudo pacman -S --needed wine wine-mono wine-gecko winetricks clang lld git wget make
sudo cp udev/99-mairlist-ftdi.rules /etc/udev/rules.d/ && sudo udevadm control --reload-rules

git clone https://github.com/aselafernando/ftd2xx-wine.git && cd ftd2xx-wine
git checkout 206869c && git apply ../patches/ftd2xx-wine-wow64-handles.patch
make libs
sudo install -m755 x86_64-unix/ftd2xx.so     /usr/lib/wine/x86_64-unix/
sudo install -m644 i386-windows/ftd2xx.dll   /usr/lib/wine/i386-windows/
sudo install -m644 x86_64-windows/ftd2xx.dll /usr/lib/wine/x86_64-windows/

export WINEPREFIX=~/.wine-mairlist
wineboot -i
cp i386-windows/ftd2xx.dll   $WINEPREFIX/drive_c/windows/syswow64/
cp x86_64-windows/ftd2xx.dll $WINEPREFIX/drive_c/windows/system32/

wget https://download.mairlist.com/current/mAirList/v7.4/mAirList-7.4.12-setup.exe
wine mAirList-7.4.12-setup.exe
```

## Fehlersuche

| Symptom | Ursache / Lösung |
| ------- | ---------------- |
| Dongle-Test: `Geraete: 0` | Dongle nicht eingesteckt oder keine Rechte → `lsusb \| grep 0403`, udev-Regel prüfen, Dongle neu einstecken |
| `Flags=1`, `FT_OpenEx … 2` | `ftdi_sio` hat das Gerät noch → `ls /dev/ttyUSB*`; udev-Regel/Produktnamen prüfen, Dongle neu einstecken |
| Dongle nur nach Neustart nicht erkannt | Alte Regel mit `ACTION=="add"` → aktuelle `udev/99-mairlist-ftdi.rules` (mit `ACTION=="bind"`) installieren |
| Lizenzmanager zeigt keinen FTDI-Dongle | `ftd2xx.dll` fehlt in `syswow64` des Prefix, oder Prefix ohne Brücke → Schritt 4 wiederholen |
| Protokoll der FTDI-Aufrufe | `WINEDEBUG=+ftd2xx wine mAirList.exe 2>&1 \| grep ftd2xx` |
| Nach Wine-Update geht der Dongle nicht mehr | `install.sh` erneut ausführen (baut die Brücke gegen die neue Wine-Version) |
| `pipewire-jack` kollidiert mit `jack2` | Wird nicht benötigt – das Skript installiert es nicht |
| Kein Ton / falsches Gerät | `pavucontrol` → Reiter *Wiedergabe*: mAirList dem USB-Gerät zuordnen |

## Deinstallation

```bash
rm -rf ~/.wine-mairlist ~/.cache/mairlist7-linux
rm -rf ~/.local/share/applications/wine/Programs/mAirList\ 7
sudo rm /etc/udev/rules.d/99-mairlist-ftdi.rules
sudo rm /usr/lib/wine/x86_64-unix/ftd2xx.so /usr/lib/wine/{i386,x86_64}-windows/ftd2xx.dll
```

## Rechtliches

* **mAirList** © mAirList GmbH – kommerzielle Software, eigene Lizenz.
* **libftd2xx** © Future Technology Devices International (FTDI) – wird beim
  Bau von ftdichip.com geladen und nicht weiterverteilt.
* **ftd2xx-wine** © Asela Fernando, GPLv2. Der Patch in `patches/` ist eine
  Ableitung davon und steht ebenfalls unter **GPLv2**.
* Alle übrigen Skripte und Dokumente dieses Repos stehen ebenfalls unter **GPLv2** (siehe [`LICENSE`](LICENSE)).
