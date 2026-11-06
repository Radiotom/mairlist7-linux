#!/usr/bin/env bash
# =============================================================================
#  mAirList 7 unter Linux (CachyOS / Arch) mit FTDI-Dongle und USB-Audio
#  https://github.com/Radiotom/mairlist7-linux
#
#  Aufruf:  ./install.sh            (als normaler Benutzer, NICHT als root)
#  Optionen per Umgebungsvariable:
#     WINEPREFIX=~/.wine-mairlist   Wine-Umgebung für mAirList
#     MAIRLIST_VERSION=7.4.12       mAirList-Version (7.x)
# =============================================================================
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export WINEPREFIX="${WINEPREFIX:-$HOME/.wine-mairlist}"
MAIRLIST_VERSION="${MAIRLIST_VERSION:-7.4.12}"
MAIRLIST_URL="https://download.mairlist.com/current/mAirList/v7.4/mAirList-${MAIRLIST_VERSION}-setup.exe"
FTD2XX_WINE_REPO="https://github.com/aselafernando/ftd2xx-wine.git"
FTD2XX_WINE_COMMIT="206869c"           # getestete Version
BUILD_DIR="${BUILD_DIR:-$HOME/.cache/mairlist7-linux}"
WINELIB=/usr/lib/wine

say()  { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }
die()  { printf '\n\033[1;31mFEHLER: %s\033[0m\n' "$*" >&2; exit 1; }

[ "$(id -u)" -ne 0 ] || die "Bitte als normaler Benutzer starten (sudo wird bei Bedarf abgefragt)."
command -v pacman >/dev/null || die "Dieses Skript ist für Arch-basierte Systeme (CachyOS, Arch, EndeavourOS, Manjaro)."

# --- 1. Pakete ---------------------------------------------------------------
say "1/6 Installiere Wine, Winetricks und Build-Werkzeuge"
sudo pacman -S --needed --noconfirm \
    wine wine-mono wine-gecko winetricks cabextract \
    clang lld wget git make patch \
    pavucontrol alsa-utils usbutils

# --- 2. udev-Regel -----------------------------------------------------------
say "2/6 udev-Regel für den FTDI-Dongle installieren"
sudo install -m 644 "$REPO_DIR/udev/99-mairlist-ftdi.rules" /etc/udev/rules.d/99-mairlist-ftdi.rules
sudo udevadm control --reload-rules
# Bereits eingesteckten Dongle sofort vom ftdi_sio-Treiber lösen
for d in /sys/bus/usb/drivers/ftdi_sio/*:*; do
    [ -e "$d" ] || continue
    if [ "$(cat "$(readlink -f "$d/..")/product" 2>/dev/null)" = "FTDI USB-Key" ]; then
        echo -n "$(basename "$d")" | sudo tee /sys/bus/usb/drivers/ftdi_sio/unbind >/dev/null
        echo "   Dongle $(basename "$d") von ftdi_sio gelöst"
    fi
done

# --- 3. ftd2xx-wine bauen ----------------------------------------------------
say "3/6 FTDI-Brücke ftd2xx-wine bauen (mit WoW64-Patch)"
mkdir -p "$BUILD_DIR"
if [ ! -d "$BUILD_DIR/ftd2xx-wine/.git" ]; then
    git clone "$FTD2XX_WINE_REPO" "$BUILD_DIR/ftd2xx-wine"
fi
cd "$BUILD_DIR/ftd2xx-wine"
git fetch --quiet origin || true
git checkout --quiet --force "$FTD2XX_WINE_COMMIT"
git apply "$REPO_DIR/patches/ftd2xx-wine-wow64-handles.patch"
make libs
cd "$REPO_DIR"

# --- 4. Wine-Prefix + Brücke installieren -------------------------------------
say "4/6 Wine-Umgebung $WINEPREFIX anlegen und FTDI-Brücke installieren"
B="$BUILD_DIR/ftd2xx-wine"
sudo install -m 755 "$B/x86_64-unix/ftd2xx.so"     "$WINELIB/x86_64-unix/ftd2xx.so"
sudo install -m 644 "$B/i386-windows/ftd2xx.dll"   "$WINELIB/i386-windows/ftd2xx.dll"
sudo install -m 644 "$B/x86_64-windows/ftd2xx.dll" "$WINELIB/x86_64-windows/ftd2xx.dll"
WINEDEBUG=-all wineboot -i
install -m 644 "$B/i386-windows/ftd2xx.dll"   "$WINEPREFIX/drive_c/windows/syswow64/ftd2xx.dll"
install -m 644 "$B/x86_64-windows/ftd2xx.dll" "$WINEPREFIX/drive_c/windows/system32/ftd2xx.dll"

# --- 5. mAirList installieren -------------------------------------------------
say "5/6 mAirList $MAIRLIST_VERSION herunterladen und installieren"
SETUP="$BUILD_DIR/mAirList-${MAIRLIST_VERSION}-setup.exe"
[ -f "$SETUP" ] || wget -O "$SETUP" "$MAIRLIST_URL"
WINEDEBUG=-all wine "$SETUP" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-
wineserver -w

# --- 6. Dongle-Test ----------------------------------------------------------
say "6/6 Dongle-Testprogramm bauen"
winegcc --target=i686-windows "$REPO_DIR/tools/ftdi-dongle-test.c" \
    -o "$BUILD_DIR/ftdi-dongle-test.exe" -Wl,/safeseh:NO
echo "   Test starten mit:  WINEPREFIX=$WINEPREFIX wine $BUILD_DIR/ftdi-dongle-test.exe"

say "Fertig! mAirList 7 findest du im Startmenü unter Wine → Programs → mAirList 7"
echo "   oder: cd \"$WINEPREFIX/drive_c/Program Files (x86)/mAirList 7\" && WINEPREFIX=$WINEPREFIX wine mAirList.exe"
