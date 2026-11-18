#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
VENV="${RED_TOR_VENV:-${SILENT_TOR_VENV:-$SCRIPT_DIR/.venv}}"
PYTHON="${PYTHON:-python3}"
if [[ "$(uname -s)" != Linux ]]; then
    echo "ERROR: Red Tor currently supports Linux only." >&2
    exit 1
fi
command -v "$PYTHON" >/dev/null || { echo "ERROR: python3 is required." >&2; exit 1; }
echo "Checking Python requirements for Red Tor..."
"$PYTHON" - <<'PY' || true
import importlib
CHECKS = [
    ("PyQt5", "PyQt5.QtWidgets"),
    ("PyQtWebEngine (browser)", "PyQt5.QtWebEngineWidgets"),
    ("QtSvg", "PyQt5.QtSvg"),
    ("Matplotlib", "matplotlib"),
    ("Stem", "stem"),
    ("Requests", "requests"),
    ("PySocks", "socks"),
]
for label, module in CHECKS:
    try:
        importlib.import_module(module)
        print(f"  OK         {label}")
    except Exception:
        print(f"  MISSING    {label} (will install)")
PY
"$PYTHON" -m venv "$VENV" || {
    echo "ERROR: Python venv support is missing. Install your distribution's python3-venv package, then retry." >&2
    exit 1
}
"$VENV/bin/python" -m pip install --upgrade pip wheel
if ! "$VENV/bin/python" -m pip install 'stem>=1.8'; then
    if [[ "${RED_TOR_DISABLE_PYPI_FALLBACK:-${SILENT_TOR_DISABLE_PYPI_FALLBACK:-0}}" == "1" ]]; then
        echo "ERROR: Stem is unavailable from the configured package index and PyPI fallback is disabled." >&2
        exit 1
    fi
    echo "Stem was not available from the configured package index; retrying this pure-Python package from https://pypi.org/simple ..." >&2
    if ! "$VENV/bin/python" -m pip install --index-url https://pypi.org/simple 'stem>=1.8'; then
        echo "ERROR: Stem could not be installed from either package source. Check network/index access." >&2
        exit 1
    fi
fi
if ! "$VENV/bin/python" -m pip install \
    --only-binary=PyQt5,PyQt5-sip,PyQt5-Qt5,PyQtWebEngine,PyQtWebEngine-Qt5,matplotlib,numpy \
    -r "$SCRIPT_DIR/requirements.txt"; then
    echo "ERROR: Python dependency installation failed; review pip output above." >&2
    echo "Qt/PyQt and map-rendering packages were restricted to binary wheels; fragile source builds were intentionally not attempted." >&2
    exit 1
fi
"$VENV/bin/python" - <<'PY'
import PyQt5
import PyQt5.QtWebEngineWidgets
from PyQt5.QtWebEngineCore import QWebEngineUrlRequestInterceptor
import matplotlib
import matplotlib.backends.backend_qt5agg
import stem
import requests
import socks
print("Dependency import check: OK")
PY
echo "Dependencies installed in: $VENV"
