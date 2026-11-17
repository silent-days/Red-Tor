#!/usr/bin/env python3
"""Red Tor: Linux desktop interface for a local Tor service.

Chromium is configured for the local SOCKS proxy. This is not Tor Browser
and the app does not protect system-wide traffic.
"""
import os
import signal as _signal
import sys

if not sys.platform.startswith("linux"):
    print("Red Tor is a Linux-only tool.", file=sys.stderr)
    sys.exit(1)

# While the heavy imports below run, Ctrl+C should kill the process
# instantly like any native program. The Python default instead raises
# KeyboardInterrupt mid-import: traceback printed, interpreter torn down
# while Chromium threads are alive -> "zsh: abort" (SIGABRT) on exit.
_signal.signal(_signal.SIGINT, _signal.SIG_DFL)

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

# Pin Chromium to the local Tor SOCKS proxy before QtWebEngine initializes.
#
# --host-resolver-rules disables ALL local DNS (the ISP resolver never sees a
# hostname); the SOCKS5 proxy performs remote DNS inside Tor instead. Without
# it, Chromium resolves names through the system resolver, which is exactly
# why ISP-blocked or DNS-poisoned sites fail to load. The other flags stop
# Chromium components from phoning home outside the proxy (QUIC/UDP, DoH,
# sync, pings, crash reporting, media router).
def build_chromium_flags(running_as_root: bool) -> str:
    """Chromium flags for the Tor-routed browser engine.

    Root launches (Kali users often run everything as root, or start the app
    with sudo) need --no-sandbox: Chromium refuses to initialize its own
    sandbox as uid 0 and QtWebEngine aborts with
    "Running as root without --no-sandbox is not supported". The flag is
    added ONLY for root launches; normal users keep the full sandbox.
    """
    flags = [
        "--proxy-server=socks5://127.0.0.1:9050",
        "--host-resolver-rules=\"MAP * ~NOTFOUND , EXCLUDE 127.0.0.1\"",
        "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
        "--disable-quic",
        "--disable-background-networking",
        "--disable-component-update",
        "--disable-default-apps",
        "--disable-sync",
        "--no-pings",
        "--disable-breakpad",
        "--media-router=0",
        "--disable-features=DnsOverHttps,Translate,TranslateUI",
    ]
    if running_as_root:
        flags.append("--no-sandbox")
    return " ".join(flags)


_RUNNING_AS_ROOT = (os.geteuid() == 0) if hasattr(os, "geteuid") else False
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = build_chromium_flags(_RUNNING_AS_ROOT)
if _RUNNING_AS_ROOT:
    print("Red Tor: running as root — Chromium starts with its own sandbox "
          "disabled (required by QtWebEngine under root).")
if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
    os.environ["QT_QPA_PLATFORM"] = os.environ.get("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QCoreApplication, Qt, QTimer

# Qt requires AA_ShareOpenGLContexts to be decided BEFORE the application
# object exists (Chromium shares GL contexts across its processes). On
# Kali's distro PyQt5 build, importing QtWebEngineWidgets AFTER a
# QApplication was constructed without this attribute aborts the module
# init with ImportError — the Browse page then claims the engine is
# "not installed" even though python3-pyqt5.qtwebengine is present and
# the launcher probe passed. Set the attribute first, then pre-load the
# engine before QtWidgets/QApplication so it is ready on every build
# (strict distro builds and the pip wheels alike).
QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
try:
    import PyQt5.QtWebEngineWidgets  # noqa: F401  (must precede QApplication)
except ImportError:
    pass  # engine genuinely missing; the Browse page shows its repair view

from PyQt5.QtWidgets import QApplication, QDesktopWidget
from PyQt5.QtGui import QIcon
from gui.theme import apply_classic_theme
from gui.splash import SplashScreen
from gui import ASSETS


def _install_signal_quit(app, window_ref):
    """Ctrl+C / SIGTERM quit the app cleanly instead of crashing.

    Qt's C++ event loop blocks Python signal delivery, so the handler
    would never run without a periodic no-op timer that returns control
    to the interpreter. The handler closes the window on the GUI thread:
    its closeEvent runs the full tab cleanup (root shell, browser
    profile) and the process exits 0 — no KeyboardInterrupt traceback,
    no SIGABRT from Chromium during interpreter teardown.
    """
    state = {"closing": False}

    def _graceful_shutdown():
        if state["closing"]:
            return
        state["closing"] = True
        win = window_ref[0] if window_ref else None
        if win is not None:
            win.close()  # closeEvent cleans up, then the event loop exits
        else:
            app.quit()

    def _on_signal(signum, _frame):
        QTimer.singleShot(0, _graceful_shutdown)

    for sig in (_signal.SIGINT, _signal.SIGTERM):
        try:
            _signal.signal(sig, _on_signal)
        except (ValueError, OSError):
            pass  # signal handlers only work in the process main thread
    wake = QTimer()
    wake.timeout.connect(lambda: None)  # periodic no-op wakes the interpreter
    wake.start(200)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Red Tor")
    app.setApplicationVersion("1.0.2")
    app.setOrganizationName("RedTor")
    window_ref = []
    _install_signal_quit(app, window_ref)
    icon_path = os.path.join(ASSETS, "logo_icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    apply_classic_theme(app)

    splash = SplashScreen()
    screen = QDesktopWidget().screenGeometry()
    splash.move((screen.width() - splash.width()) // 2,
                (screen.height() - splash.height()) // 2)
    splash.show()
    app.processEvents()

    def report_progress(percent, message):
        splash.set_progress(percent, message)
        app.processEvents()

    # The heavy import chain (QtWebEngine inside the Browse tab) now runs
    # while the splash is already on screen, so the boot feels immediate
    # (~2 s to the interactive window instead of a long blank wait).
    report_progress(2, "Preparing the Red Tor window")
    from gui.main_window import RedTorWindow

    window = RedTorWindow(startup_progress=report_progress)
    window_ref.append(window)
    window.move((screen.width() - window.width()) // 2,
                (screen.height() - window.height()) // 2)
    window.show()
    window.raise_()
    window.activateWindow()
    report_progress(100, "Interface ready. Tor is still disconnected until you connect.")
    splash.fade_out_and_close()
    app.processEvents()

    print("Red Tor v1.0.2 started. Tor is not connected until you choose.")
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
