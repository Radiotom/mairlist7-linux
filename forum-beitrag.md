# [Linux] mAirList 7 unter Wine – inkl. FTDI-Dongle-Lizenz und USB-Audio (Anleitung)

Hallo zusammen,

hier ist eine Anleitung, wie ich **mAirList 7.4.12** unter **Linux (CachyOS, Arch-basiert)** mit **Wine** zum Laufen gebracht habe. Die **Lizenzaktivierung per FTDI-USB-Dongle** funktioniert, ebenso **USB-Audiogeräte**.

In früheren Threads (z. B. [Demo in wine](https://community.mairlist.com/t/demo-in-wine/17787)) lief mAirList zwar teilweise in Wine/Bottles, aber am FTDI-Dongle war Schluss. Genau dafür gibt es jetzt eine Lösung.

> **Hinweis:** Das ist ein inoffizieller Community-Weg und wird vom mAirList-Support nicht unterstützt. Bitte erst gründlich testen, bevor ihr damit on air geht.

---

## Was getestet wurde

| Komponente | Getestet mit | Ergebnis |
|---|---|---|
| Betriebssystem | CachyOS, Kernel 7.3, KDE Plasma 6.8 (Wayland) | ✅ |
| Wine | 11.21 (Arch-Paket `wine`, WoW64-Modus) | ✅ |
| mAirList | 7.4.12 (offizieller Setup-Installer) | ✅ Installation und Start ohne Fehler |
| Lizenz-Dongle | „FTDI USB-Key“ (FT232R, `0403:6001`) | ✅ Im Lizenzmanager unter *Dongles → FTDI* erkannt, **Lizenz erfolgreich aktiviert** |
| USB-Audio | Yamaha AG06/AG03 | ✅ Wird in mAirList als Audiogerät angezeigt |
| Audiotreiber in mAirList | DirectSound / WASAPI (über Wine → PipeWire) | ✅ Geräte auswählbar |
| Datenbank | mAirList-Datenbank, Verbindung als Internet-Client | ✅ Erfolgreich getestet |
| Lokale Datenbank | Neue lokale Datenbank (`*.mldb`) anlegen | ✅ Funktioniert |
| Musikimport | Import von Musik in die Datenbank | ✅ Funktioniert |
| Mikrofoneingang | Aufnahme über den USB-Eingang (Yamaha AG06) | ✅ Funktioniert |
| Voice Tracking | Mikrofoneingang im VT-Editor | ✅ Funktioniert |
| Rechner-Neustart | Dongle wird nach dem Booten automatisch freigegeben | ✅ Funktioniert (mit der korrigierten udev-Regel, siehe unten) |
| Neustart | mAirList beenden und neu starten | ✅ Lizenz bleibt aktiv, Audioeinstellungen bleiben erhalten |

**Noch nicht getestet:**

- andere Distributionen (Ubuntu, Debian, Fedora …); das Installationsskript ist derzeit nur für Arch-basierte Systeme gedacht
- andere Dongles als den „FTDI USB-Key“ (z. B. FT485R)
- ASIO (wineasio)
- Dauerbetrieb über viele Stunden/Tage, Encoder/Streaming, PostgreSQL-Datenbank, Fernsteuerung und Skripte
- vollständiger Durchlauf des Installationsskripts auf einem frischen System (die einzelnen Schritte wurden aber alle getestet)

Rückmeldungen zu diesen Punkten sind sehr willkommen!

---

## Was benötigt wird

**Hardware**
- PC mit Linux (x86_64)
- mAirList-FTDI-Dongle (FT232R / FT485R), sofern ihr eine Dongle-Lizenz nutzt
- USB-Audiogerät nach Wahl (alles, was unter Linux/PipeWire als Audiogerät erscheint)

**Software / Zusatzprogramme**

| Programm | Wofür |
|---|---|
| **Wine** ≥ 9.0 (getestet: 11.21), WoW64-Modus | Läuft mAirList unter Linux |
| **wine-mono**, **wine-gecko** | Standard-Komponenten für Wine |
| **winetricks**, **cabextract** | Optional, für spätere Ergänzungen |
| **PipeWire** (mit `pipewire-pulse`) | Audio-System; reicht die USB-Geräte an Wine weiter |
| **pavucontrol** | Pegel und Zuordnung der Audiogeräte |
| **clang**, **lld**, **make**, **git**, **wget** | Zum Bauen der FTDI-Brücke |
| **[ftd2xx-wine](https://github.com/aselafernando/ftd2xx-wine)** (GPLv2) + Patch | Brücken-DLL: stellt mAirList den FTDI-Treiber `FTD2XX.dll` unter Wine bereit |
| **libftd2xx 1.4.34** (offizieller FTDI-Linux-Treiber) | Wird beim Bau automatisch von ftdichip.com geladen |
| **udev-Regel** | Gibt den Dongle für Benutzer frei und löst ihn vom Linux-Seriell-Treiber |

---

## Wie es funktioniert (Kurzfassung)

mAirList greift über `FTChipID.dll` auf den FTDI-Treiber `FTD2XX.dll` zu. Unter Windows hängt der an einem Kernel-Treiber, den es unter Wine nicht gibt. Die Lösung besteht aus drei Teilen:

1. **ftd2xx-wine** ersetzt `FTD2XX.dll` durch eine Wine-DLL, die die Aufrufe an den offiziellen **Linux-Treiber von FTDI** weiterreicht.
2. **Patch für 32 Bit:** mAirList ist ein 32-Bit-Programm. Im Original-ftd2xx-wine wurden dabei die Geräte-Handles abgeschnitten und die Geräteliste im falschen Format zurückgegeben. Mein Patch behebt das mit einer Handle-Tabelle und einer Umrechnung der Geräteliste.
3. **udev-Regel:** Linux bindet FTDI-Chips automatisch als serielle Schnittstelle (`/dev/ttyUSB0`), dann ist der Dongle für den FTDI-Treiber „belegt“. Die Regel löst **nur** Geräte mit dem Namen „FTDI USB-Key“ davon. Andere USB-Seriell-Adapter bleiben unberührt.

Audio braucht keine Extras: Wine gibt alle PipeWire-Geräte als DirectSound/WASAPI-Geräte an mAirList weiter.

---

## Installation

Alles steckt in einem Skript auf GitHub (Arch / CachyOS / EndeavourOS / Manjaro):

```bash
git clone https://github.com/Radiotom/mairlist7-linux.git
cd mairlist7-linux
./install.sh
```

Das Skript installiert die Pakete, richtet die udev-Regel ein, baut und installiert die FTDI-Brücke, legt eine eigene Wine-Umgebung (`~/.wine-mairlist`) an und installiert mAirList 7.4.12 vom offiziellen Download-Server.

**Ausführliche Anleitung, manuelle Schritte und Fehlersuche:** https://github.com/Radiotom/mairlist7-linux

### Dongle prüfen

Im Repository ist ein kleines Testprogramm enthalten, das genau die FTDI-Funktionen aufruft, die auch mAirList nutzt:

```bash
WINEPREFIX=~/.wine-mairlist wine ~/.cache/mairlist7-linux/ftdi-dongle-test.exe
```

Erwartete Ausgabe (Seriennummer variiert):

```
FT_CreateDeviceInfoList: 0, Geraete: 1
  [0] Typ=5 ID=04036001 SN='FT2XXXXX' Beschreibung='FTDI USB-Key' Flags=0
FT_OpenEx('FT2XXXXX'): 0 Handle=00001000
FT_Close: 0
```

Steht dort `Flags=1` und `FT_OpenEx … 2`, hält der Linux-Seriell-Treiber den Dongle noch fest. Dann den Dongle einmal ab- und wieder anstecken.

### Lizenz aktivieren

Wie unter Windows: *Lizenzmanager → erweiterte Ansicht → Dongles → FTDI → Reload*. Neuer Dongle: *Initialize*, den Code an den Support schicken und danach die Lizenzdatei neu herunterladen. Bereits initialisierter Dongle: nur die Lizenzdatei neu herunterladen.

### Audio einrichten

*Konfiguration → Audiogeräte* → **DirectSound** oder **WASAPI** wählen. USB-Geräte erscheinen dort mit ihrem Namen. Tipps:
- Gerät und mAirList auf dieselbe Abtastrate stellen (z. B. 48 kHz).
- Bei Aussetzern den Puffer in mAirList erhöhen oder mAirList mit `PULSE_LATENCY_MSEC=60` starten.

---

## Bekannte Punkte

- **udev-Regel auf `bind`, nicht auf `add`:** Beim Hochfahren wird der Dongle erkannt, bevor `ftdi_sio` geladen ist. Der Treiber bindet ihn erst danach. Eine Regel auf `ACTION=="add"` greift daher nur beim Einstecken im laufenden Betrieb, nicht nach einem Neustart. Die Regel im Repository nutzt deshalb `ACTION=="bind"`.
- **Nach einem Wine-Update** `install.sh` erneut ausführen, damit die FTDI-Brücke gegen die neue Wine-Version neu gebaut wird.
- Unter Arch/CachyOS kollidiert `pipewire-jack` mit `jack2`. Es wird für diesen Aufbau nicht benötigt.
- Im Wine-Log tauchen zwei harmlose Meldungen auf (`listview … unknown msg`, `ImageList_Replace`); sie haben keine sichtbaren Auswirkungen.

---

Fragen, Erfahrungsberichte mit anderen Distributionen, Dongles oder Audiohardware gerne hier im Thread. Fehlerberichte und Verbesserungen auch gern direkt als Issue oder Pull Request auf GitHub.

Viele Grüße
