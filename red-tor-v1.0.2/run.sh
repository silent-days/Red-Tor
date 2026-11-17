#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${RED_TOR_VENV:-${SILENT_TOR_VENV:-$SCRIPT_DIR/.venv}}/bin/python"

# Kali prints a harmless at-spi warning when the accessibility-bus socket
# is stale; silence it unless the bridge was enabled on purpose.
export NO_AT_BRIDGE="${NO_AT_BRIDGE:-1}"

if [[ "$(uname -s)" != Linux ]]; then
    echo "ERROR: Red Tor supports Linux only." >&2
    exit 1
fi
if [[ ! -x "$PYTHON" ]]; then
    echo "Dependencies are not installed for this Red Tor copy." >&2
    echo "Re-run sudo bash install.sh from the extracted project directory to repair the system install." >&2
    exit 1
fi
if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
    echo "ERROR: No graphical display found. Start Red Tor from a desktop session." >&2
    exit 1
fi
if ! "$PYTHON" -c 'import PyQt5.QtWidgets; import PyQt5.QtWebEngineWidgets; import PyQt5.QtSvg; from PyQt5.QtWebEngineCore import QWebEngineUrlRequestInterceptor; import matplotlib; import matplotlib.backends.backend_qt5agg; import stem; import requests; import socks' >/dev/null 2>&1; then
    echo "ERROR: Red Tor GUI dependencies are missing or incomplete." >&2
    echo "Re-run sudo bash install.sh from the extracted project directory to repair the system install." >&2
    echo "For a per-user install, run bash install.sh from the project directory." >&2
    exit 1
fi
if [[ "$(id -u)" -eq 0 ]]; then
    echo "Note: Red Tor is starting as root; the browser engine runs with its"
    echo "Chromium sandbox disabled under root (QtWebEngine requirement)."
fi
exec "$PYTHON" "$SCRIPT_DIR/red_tor.py" "$@"
