#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}"
DEST="$DATA_HOME/red-tor"
BIN_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
STAGE="$DATA_HOME/.red-tor-stage.$$"
BACKUP="$DATA_HOME/red-tor.previous"
AUTOSTART=0
for arg in "$@"; do
    [[ "$arg" == "--autostart" ]] && AUTOSTART=1
done

[[ "$(uname -s)" == Linux ]] || { echo "ERROR: Linux only." >&2; exit 1; }
[[ "$DATA_HOME" == /* && "$STATE_HOME" == /* && "$BIN_DIR" == /* ]] || {
    echo "ERROR: XDG data/state/bin paths must be absolute." >&2
    exit 1
}
command -v python3 >/dev/null || { echo "ERROR: python3 is required." >&2; exit 1; }
for item in red_tor.py tor_core.py requirements.txt install-deps.sh run.sh uninstall-user.sh gui assets README.md; do
    [[ -e "$SCRIPT_DIR/$item" ]] || { echo "ERROR: missing project item: $item" >&2; exit 1; }
done
mkdir -p "$DATA_HOME" "$STATE_HOME" "$BIN_DIR"
rm -rf -- "$STAGE"
mkdir -p "$STAGE"
for item in red_tor.py tor_core.py requirements.txt install-deps.sh run.sh uninstall-user.sh gui assets README.md; do
    cp -a -- "$SCRIPT_DIR/$item" "$STAGE/"
done
chmod +x "$STAGE/run.sh" "$STAGE/red_tor.py"

if [[ -e "$DEST" ]]; then
    rm -rf -- "$BACKUP"
    mv -- "$DEST" "$BACKUP"
fi
if ! mv -- "$STAGE" "$DEST"; then
    [[ ! -e "$BACKUP" ]] || mv -- "$BACKUP" "$DEST"
    echo "ERROR: Could not install app files; previous installation restored." >&2
    exit 1
fi
if ! "$DEST/install-deps.sh"; then
    rm -rf -- "$DEST"
    [[ ! -e "$BACKUP" ]] || mv -- "$BACKUP" "$DEST"
    echo "ERROR: Dependencies failed to install. Previous app restored." >&2
    exit 1
fi

# Preserve/migrate Tor's private runtime state from the old install directory.
LEGACY_APP="$DATA_HOME/silent-tor"
NEW_STATE="$STATE_HOME/red-tor"
mkdir -p "$NEW_STATE"
if [[ -d "$LEGACY_APP/tor-data" && ! -e "$NEW_STATE/tor-data" ]]; then
    cp -a -- "$LEGACY_APP/tor-data" "$NEW_STATE/tor-data"
    chmod 700 "$NEW_STATE/tor-data"
fi
if [[ -f "$STATE_HOME/silent-tor/tor.log" && ! -e "$NEW_STATE/tor.log" ]]; then
    cp -a -- "$STATE_HOME/silent-tor/tor.log" "$NEW_STATE/tor.log"
    chmod 600 "$NEW_STATE/tor.log"
fi
# The prior per-user install directory is app code, not the settings folder.
if [[ -f "$LEGACY_APP/silent_tor.py" ]]; then
    rm -rf -- "$LEGACY_APP"
fi
rm -rf -- "$BACKUP"

cat > "$BIN_DIR/red-tor" <<EOF
#!/usr/bin/env bash
exec "$DEST/run.sh" "\$@"
EOF
chmod 755 "$BIN_DIR/red-tor"
cat > "$BIN_DIR/red-tor-uninstall" <<EOF
#!/usr/bin/env bash
exec "$DEST/uninstall-user.sh" "\$@"
EOF
chmod 755 "$BIN_DIR/red-tor-uninstall"
APP_DIR="$DATA_HOME/applications"
mkdir -p "$APP_DIR"
cat > "$APP_DIR/red-tor.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Red Tor
GenericName=Tor desktop client
Comment=Desktop interface for a local Tor service
Exec="$BIN_DIR/red-tor"
Icon="$DEST/assets/logo_icon.png"
Terminal=false
Categories=Network;Security;Internet;
StartupNotify=true
EOF
chmod 644 "$APP_DIR/red-tor.desktop"
if (( AUTOSTART )); then
    AUTOSTART_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
    mkdir -p "$AUTOSTART_DIR"
    cp "$APP_DIR/red-tor.desktop" "$AUTOSTART_DIR/red-tor.desktop"
fi
# Remove obsolete launch metadata only; the user's .silent-tor notes/settings stay intact.
rm -f -- "$BIN_DIR/silent-tor" "$BIN_DIR/silent-tor-uninstall" \
    "$APP_DIR/silent-tor.desktop" "${XDG_CONFIG_HOME:-$HOME/.config}/autostart/silent-tor.desktop"

echo "Installed for current user: $DEST"
echo "Command: $BIN_DIR/red-tor"
echo "Menu entry: $APP_DIR/red-tor.desktop"
echo ""
echo "===================================================="
echo " HOW TO OPEN RED TOR:"
echo "   Menu entry : Internet -> Red Tor"
echo "   Terminal   : $BIN_DIR/red-tor"
echo ""
echo " RULES THAT MATTER:"
echo "   1. The APP runs WITHOUT sudo: just run 'red-tor'."
echo "   2. Requirements install / repair (correct command):"
echo "        sudo bash install.sh"
echo "      'sudo apt install.sh' is WRONG - apt tries to install a"
echo "      package named 'install.sh' and downloads NOTHING."
echo "   3. First open: press Connect in Red Tor before browsing;"
echo "      pages stay blocked until Tor is connected (by design)."
echo "===================================================="
echo "Tor runtime state is in $NEW_STATE; ~/.silent-tor notes/settings were preserved."
if (( ! AUTOSTART )); then
    echo "Optional login autostart: rerun with --autostart"
fi
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo "NOTE: Add $BIN_DIR to PATH to run 'red-tor' from a new terminal."
fi
