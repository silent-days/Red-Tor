#!/usr/bin/env bash
# Permanent Debian-family installation for Red Tor.
set -Eeuo pipefail
[[ "$(id -u)" -eq 0 ]] || { echo "Run with sudo: sudo bash install.sh" >&2; exit 1; }
[[ "$(uname -s)" == Linux ]] || { echo "ERROR: Linux only." >&2; exit 1; }
command -v apt-get >/dev/null || { echo "ERROR: system installation supports Debian-family Linux; use bash install.sh for a per-user install elsewhere." >&2; exit 1; }
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEST="/opt/red-tor"
BIN="/usr/local/bin/red-tor"
STAGE="${DEST}.new.$$"
BACKUP="${DEST}.previous"

for item in red_tor.py tor_core.py requirements.txt run.sh gui assets README.md; do
    [[ -e "$SCRIPT_DIR/$item" ]] || { echo "ERROR: missing project item: $item" >&2; exit 1; }
done

printf '[1/5] Checking and installing Linux runtime dependencies...\n'
# Every requirement is installed automatically if missing; apt is idempotent,
# so already-satisfied packages are skipped and reported by apt itself.
DEPS="python3 python3-venv python3-pyqt5 python3-pyqt5.qtwebengine python3-pyqt5.qtsvg python3-matplotlib python3-stem python3-requests python3-socks tor"
MISSING=""
for dep in $DEPS; do
    if dpkg-query -W -f='${Status}' "$dep" 2>/dev/null | grep -q "install ok installed"; then
        printf '  OK         %s\n' "$dep"
    else
        printf '  MISSING    %s (will install)\n' "$dep"
        MISSING="$MISSING $dep"
    fi
done
apt-get update || {
    echo "WARNING: 'apt-get update' failed (network or repository trouble)."
    echo "         Continuing with cached package lists; already-cached"
    echo "         packages can still install."
}
if [[ -n "$MISSING" ]]; then
    DEBIAN_FRONTEND=noninteractive apt-get install -y $MISSING
fi
printf '  All requirements satisfied.\n'

# Add a loopback-only, cookie-authenticated control port only when absent.
# Existing administrator Tor settings are retained.
TORRC="/etc/tor/torrc"
TOR_DEFAULTS="/usr/share/tor/tor-service-defaults-torrc"
if [[ -f "$TORRC" ]]; then
    if [[ ! -e /etc/tor/torrc.red-tor.bak ]]; then
        cp -a "$TORRC" /etc/tor/torrc.red-tor.bak
    fi
    changed=0
    if ! grep -Eq '^[[:space:]]*ControlPort[[:space:]]+' "$TORRC"; then
        printf '\n# Red Tor: local desktop control access\nControlPort 127.0.0.1:9051\n' >> "$TORRC"
        changed=1
    fi
    if ! grep -Eq '^[[:space:]]*CookieAuthentication[[:space:]]+' "$TORRC" && \
       ! { [[ -r "$TOR_DEFAULTS" ]] && grep -Eq '^[[:space:]]*CookieAuthentication[[:space:]]+' "$TOR_DEFAULTS"; }; then
        printf 'CookieAuthentication 1\n' >> "$TORRC"
        changed=1
    fi
    if ! grep -Eq '^[[:space:]]*CookieAuthFileGroupReadable[[:space:]]+' "$TORRC" && \
       ! { [[ -r "$TOR_DEFAULTS" ]] && grep -Eq '^[[:space:]]*CookieAuthFileGroupReadable[[:space:]]+' "$TOR_DEFAULTS"; }; then
        printf 'CookieAuthFileGroupReadable 1\n' >> "$TORRC"
        changed=1
    fi
    if [[ -n "${SUDO_USER:-}" && "$SUDO_USER" != root ]] && getent group debian-tor >/dev/null; then
        usermod -aG debian-tor "$SUDO_USER"
    fi
    if [[ -r "$TOR_DEFAULTS" ]]; then
        tor --defaults-torrc "$TOR_DEFAULTS" -f "$TORRC" --RunAsDaemon 0 --verify-config
    else
        tor --verify-config -f "$TORRC"
    fi
    if (( changed )) && command -v systemctl >/dev/null 2>&1; then
        if systemctl is-active --quiet tor@default.service; then
            systemctl restart tor@default.service
        elif systemctl is-active --quiet tor.service; then
            systemctl restart tor.service
        fi
    fi
fi

printf '[2/5] Staging Red Tor in %s...\n' "$DEST"
rm -rf -- "$STAGE"
mkdir -p "$STAGE"
for item in red_tor.py tor_core.py requirements.txt run.sh gui assets README.md; do
    cp -a -- "$SCRIPT_DIR/$item" "$STAGE/"
done
chmod +x "$STAGE/run.sh" "$STAGE/red_tor.py"
chmod -R a+rX "$STAGE"
if [[ -e "$DEST" ]]; then
    rm -rf -- "$BACKUP"
    mv -- "$DEST" "$BACKUP"
fi
if ! mv -- "$STAGE" "$DEST"; then
    [[ ! -e "$BACKUP" ]] || mv -- "$BACKUP" "$DEST"
    echo "ERROR: staged installation failed; previous app restored." >&2
    exit 1
fi
rollback() {
    status=$?
    if (( status != 0 )); then
        rm -rf -- "$DEST"
        if [[ -e "$BACKUP" ]]; then
            mv -- "$BACKUP" "$DEST"
        else
            rm -f -- "$BIN" /usr/share/applications/red-tor.desktop
            if [[ -n "${SUDO_USER:-}" && "$SUDO_USER" != root ]]; then
                rollback_home="$(getent passwd "$SUDO_USER" | cut -d: -f6)"
                if [[ -n "$rollback_home" ]]; then
                    rm -f -- "$rollback_home/.local/share/applications/red-tor.desktop" \
                        "$rollback_home/.config/autostart/red-tor.desktop"
                fi
            fi
        fi
    fi
    exit "$status"
}
trap rollback EXIT

printf '[3/5] Creating isolated Python environment using distro GUI packages...\n'
/usr/bin/python3 -m venv --system-site-packages "$DEST/.venv"
IMPORT_CHECK='import PyQt5.QtWidgets, PyQt5.QtWebEngineWidgets, PyQt5.QtSvg; from PyQt5.QtWebEngineCore import QWebEngineUrlRequestInterceptor; import matplotlib.backends.backend_qt5agg; import stem, requests, socks'
if "$DEST/.venv/bin/python" -c "$IMPORT_CHECK"; then
    echo "Dependency import check: OK"
else
    echo "The QtWebEngine package is still missing; installing the official"
    echo "PyQtWebEngine wheel from PyPI as a fallback..."
    "$DEST/.venv/bin/python" -m pip install --only-binary=:all: PyQtWebEngine PyQtWebEngine-Qt5 \
        || echo "WARNING: PyQtWebEngine wheel fallback failed."
    if "$DEST/.venv/bin/python" -c "$IMPORT_CHECK"; then
        echo "Dependency import check: OK (after PyQtWebEngine fallback)"
    else
        echo "ERROR: required Python dependencies are still missing." >&2
        echo "Check network access and run: sudo bash install.sh" >&2
        exit 1
    fi
fi

printf '[4/5] Creating launcher and desktop entry...\n'
cat > "$BIN" <<EOF
#!/usr/bin/env bash
exec "$DEST/run.sh" "\$@"
EOF
chmod 755 "$BIN"
DESKTOP="/usr/share/applications/red-tor.desktop"
cat > "$DESKTOP" <<EOF
[Desktop Entry]
Type=Application
Name=Red Tor
GenericName=Tor desktop client
Comment=Desktop interface for a local Tor service
Exec=$BIN
Icon=$DEST/assets/logo_icon.png
Terminal=false
Categories=Network;Security;Internet;
StartupNotify=true
EOF
chmod 644 "$DESKTOP"
TARGET_USER="${SUDO_USER:-}"
if [[ -n "$TARGET_USER" && "$TARGET_USER" != root ]]; then
    USER_HOME="$(getent passwd "$TARGET_USER" | cut -d: -f6)"
    [[ -n "$USER_HOME" && -d "$USER_HOME" ]] || { echo "ERROR: cannot determine invoking user's home directory." >&2; exit 1; }
    USER_GROUP="$(id -gn "$TARGET_USER")"
    AUTOSTART_DIR="$USER_HOME/.config/autostart"
    USER_APPS_DIR="$USER_HOME/.local/share/applications"
    install -d -o "$TARGET_USER" -g "$USER_GROUP" "$AUTOSTART_DIR" "$USER_APPS_DIR"
    # Remove only obsolete launch metadata; user settings and Tor state are retained.
    rm -f -- "$USER_HOME/.config/autostart/silent-tor.desktop" \
        "$USER_APPS_DIR/silent-tor.desktop" "$USER_APPS_DIR/red-tor.desktop" \
        "$AUTOSTART_DIR/silent-tor.desktop" "$AUTOSTART_DIR/red-tor.desktop" \
        "$USER_HOME/.local/bin/silent-tor" "$USER_HOME/.local/bin/silent-tor-uninstall" \
        "$USER_HOME/.local/bin/red-tor" "$USER_HOME/.local/bin/red-tor-uninstall"
    install -o "$TARGET_USER" -g "$USER_GROUP" -m 644 "$DESKTOP" "$USER_APPS_DIR/red-tor.desktop"
    install -o "$TARGET_USER" -g "$USER_GROUP" -m 644 "$DESKTOP" "$AUTOSTART_DIR/red-tor.desktop"
fi

printf '[5/5] Installation complete.\n'
echo "Application: $DEST"
echo "Command: red-tor"
echo "Menu entry: Internet -> Red Tor"
echo ""
echo "===================================================="
echo " HOW TO OPEN RED TOR:"
echo "   Menu entry : Internet -> Red Tor"
echo "   Terminal   : red-tor"
echo ""
echo " RULES THAT MATTER:"
echo "   1. The APP runs WITHOUT sudo: just type 'red-tor'."
echo "      (sudo red-tor also works now, but is not needed.)"
echo "   2. Requirements install / repair (correct command):"
echo "        sudo bash install.sh"
echo "      'sudo apt install.sh' is WRONG - apt tries to install a"
echo "      package named 'install.sh' and downloads NOTHING."
echo "   3. First open: press Connect in Red Tor before browsing;"
echo "      pages stay blocked until Tor is connected (by design)."
echo "===================================================="
if [[ -n "$TARGET_USER" && "$TARGET_USER" != root ]]; then
    echo "Login autostart enabled for $TARGET_USER. Log out and back in once if the debian-tor group was newly added."
else
    echo "Login autostart was not added because no invoking desktop user was detected."
fi
echo "Tor system state and prior ~/.silent-tor notes/settings are preserved. Red Tor does not enable system-wide firewall protection."
# Clean previous system app code only after the new install has passed checks.
rm -rf -- /opt/silent-tor /opt/silent-tor.previous
rm -f -- /usr/local/bin/silent-tor /usr/share/applications/silent-tor.desktop
rm -rf -- "$BACKUP"
trap - EXIT
