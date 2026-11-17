#!/usr/bin/env bash
# Stop Red Tor from launching automatically at login (login autostart).
# The app itself, your notes and settings are not touched.
set -euo pipefail

AUTOSTART_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
TARGET="$AUTOSTART_DIR/red-tor.desktop"
removed=0

if [[ -f "$TARGET" ]]; then
    rm -f -- "$TARGET"
    echo "Removed: $TARGET"
    removed=1
fi

if (( removed )); then
    echo "Red Tor will no longer start automatically at login."
    echo "Start it any time from the menu (Internet -> Red Tor) or with the 'red-tor' command."
    echo "Re-enable login autostart by reinstalling: bash install.sh (per-user) or sudo bash install-system.sh."
else
    echo "No Red Tor login autostart entry was found. Nothing changed."
fi
