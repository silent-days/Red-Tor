"""Red Tor - runtime requirement checks.

Every capability the tool needs is probed here, so the app can tell the user
exactly what is missing and point at the one command that fixes it:

    sudo bash install.sh

Each check returns (label, ok, detail). The Browse page shows a one-click
"Run installer" button when something is missing; Diagnostics lists every
item with its status.
"""
import importlib
import os
import shutil


def _import_ok(module):
    try:
        importlib.import_module(module)
        return True
    except Exception:
        return False


def check_requirements():
    """Return a list of (label, ok, detail) for every runtime requirement."""
    results = []
    results.append(("Python 3 (>=3.8)", _python_ok(), _python_version()))
    results.append(("PyQt5 (GUI)", _import_ok("PyQt5.QtWidgets"),
                    "python3-pyqt5 or pip PyQt5"))
    results.append(("QtWebEngine (browser)", _import_ok("PyQt5.QtWebEngineWidgets"),
                    "python3-pyqt5.qtwebengine or pip PyQtWebEngine"))
    results.append(("QtSvg (icons)", _import_ok("PyQt5.QtSvg"),
                    "python3-pyqt5 or pip PyQt5"))
    results.append(("Matplotlib (charts)", _import_ok("matplotlib.backends.backend_qt5agg"),
                    "python3-matplotlib or pip matplotlib"))
    results.append(("Stem (Tor controller)", _import_ok("stem"),
                    "python3-stem or pip stem"))
    results.append(("Requests", _import_ok("requests"),
                    "python3-requests or pip requests"))
    results.append(("PySocks (SOCKS proxy)", _import_ok("socks"),
                    "python3-socks or pip PySocks"))
    tor_bin = shutil.which("tor")
    results.append(("Tor binary", tor_bin is not None,
                    tor_bin or "not found on PATH — sudo apt install tor"))
    return results


def missing_count():
    return sum(1 for _label, ok, _d in check_requirements() if not ok)


def missing_names():
    return [label for label, ok, _d in check_requirements() if not ok]


def installer_command():
    """The command that repairs a broken/missing install."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script = os.path.join(here, "install.sh")
    if os.path.exists(script):
        return f"sudo bash {script}"
    return "sudo bash install.sh"


def _python_ok():
    import sys
    return sys.version_info >= (3, 8)


def _python_version():
    import sys
    return sys.version.split()[0]
