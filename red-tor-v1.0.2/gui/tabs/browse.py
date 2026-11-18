"""Red Tor - Browse tab with REAL web browser.

Uses PyQtWebEngine (Chromium) to render actual websites.
Traffic is routed through the Tor SOCKS proxy (port 9050) so the
website sees the Tor exit node's IP, not yours.

Features:
- Real Chromium-based web view
- URL bar with back / forward / refresh / home buttons
- Progress bar showing page load
- Status bar showing link hover
- Auto-detects Tor connection and warns if not connected
- Quick links to popular .onion services and clearnet sites
"""
import os
import re
import threading
from PyQt5.QtCore import Qt, QUrl, QTimer, QCoreApplication, QEvent
from PyQt5.QtGui import QFont, QIcon, QColor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QLineEdit, QProgressBar, QGroupBox, QMessageBox, QToolButton,
    QSizePolicy, QFrame, QMenu, QAction, QScrollArea,
)

# Try to import QtWebEngine - if it fails we fall back to text fetch mode
try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineProfile, QWebEnginePage
    from PyQt5.QtWebEngineCore import QWebEngineUrlRequestInterceptor
    WEBENGINE_AVAILABLE = True
except ImportError:
    WEBENGINE_AVAILABLE = False

if WEBENGINE_AVAILABLE:
    class TorConnectionGate(QWebEngineUrlRequestInterceptor):
        """Block browser requests whenever a verified live Tor session is absent."""
        def __init__(self, tor_manager, parent=None):
            super().__init__(parent)
            self.tor_manager = tor_manager

        def interceptRequest(self, info):
            if (not self.tor_manager.connected):
                info.block(True)

from gui.theme import (
    CREAM, CREAM_LIGHT, CREAM_DARK, TAN, TAN_DARK, DARK_TEXT, MUTED,
    PURPLE, PURPLE_DARK, PURPLE_LIGHT, PURPLE_PALE,
    GREEN_OK, AMBER, RED_OFF, TEAL,
)
from gui import ICONS


def _icon(name):
    p = os.path.join(ICONS, name)
    return QIcon(p) if os.path.exists(p) else QIcon()


class BrowseTab(QWidget):
    """Browse tab - REAL web browser routed through Tor."""

    HOME_URL = "https://check.torproject.org/"

    QUICK_LINKS = [
        ("check.torproject.org", "https://check.torproject.org/",
         "Verify you're using Tor"),
        ("Tor Project", "https://torproject.org/",
         "Official Tor Project website"),
        ("Wikipedia", "https://wikipedia.org/",
         "Free encyclopedia"),
        ("DuckDuckGo", "https://duckduckgo.com/",
         "Privacy-focused search"),
        ("BBC News", "https://www.bbc.com/news",
         "World news"),
        ("ProPublica", "https://propublica.org/",
         "Investigative journalism"),
    ]

    def __init__(self, main_win):
        super().__init__()
        self.main_win = main_win
        self._build()

    def _build(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # ----- Top toolbar -----
        toolbar = QFrame()
        toolbar.setStyleSheet(f"""
            QFrame {{
                background: {CREAM_DARK};
                border-bottom: 1px solid {TAN_DARK};
            }}
            QPushButton {{
                background: {CREAM_LIGHT};
                border: 1px solid {TAN_DARK};
                padding: 6px 10px;
                border-radius: 3px;
            }}
            QPushButton:hover {{
                background: {PURPLE_PALE};
                border-color: {PURPLE};
            }}
            QPushButton:pressed {{
                background: {PURPLE};
                color: #111111;
            }}
            QLineEdit {{
                background: {CREAM_LIGHT};
                border: 1px solid {TAN_DARK};
                padding: 6px 10px;
                border-radius: 3px;
            }}
            QLineEdit:focus {{
                border: 1px solid {PURPLE};
            }}
        """)
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(8, 6, 8, 6)
        tb_layout.setSpacing(6)

        # Back button
        self.back_btn = QPushButton("  Back")
        self.back_btn.setIcon(_icon("path.png"))
        self.back_btn.setToolTip("Go back")
        self.back_btn.clicked.connect(lambda: self.web_view and self.web_view.back())
        tb_layout.addWidget(self.back_btn)

        # Forward button
        self.forward_btn = QPushButton("  Forward")
        self.forward_btn.setIcon(_icon("path.png"))
        self.forward_btn.setToolTip("Go forward")
        self.forward_btn.clicked.connect(lambda: self.web_view and self.web_view.forward())
        tb_layout.addWidget(self.forward_btn)

        # Refresh button
        self.refresh_btn = QPushButton("  Reload")
        self.refresh_btn.setIcon(_icon("new_circuit.png"))
        self.refresh_btn.setToolTip("Reload current page")
        self.refresh_btn.clicked.connect(self._reload)
        tb_layout.addWidget(self.refresh_btn)

        # Home button
        self.home_btn = QPushButton("  Home")
        self.home_btn.setIcon(_icon("home.png"))
        self.home_btn.setToolTip("Go to Tor check page")
        self.home_btn.clicked.connect(self._go_home)
        tb_layout.addWidget(self.home_btn)

        # URL bar
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Enter URL or search...")
        self.url_input.returnPressed.connect(self._navigate_to_url)
        tb_layout.addWidget(self.url_input, 1)

        # Go button
        self.go_btn = QPushButton("  Go")
        self.go_btn.setIcon(_icon("globe.png"))
        self.go_btn.setToolTip("Navigate to URL")
        self.go_btn.clicked.connect(self._navigate_to_url)
        tb_layout.addWidget(self.go_btn)

        # Request a new Tor circuit without promising a new exit IP.
        self.identity_btn = QPushButton("  New Circuit")
        self.identity_btn.setIcon(_icon("shield.png"))
        self.identity_btn.setToolTip("Request a new Tor circuit (NEWNYM); the exit IP may remain the same")
        self.identity_btn.clicked.connect(self._new_identity)
        tb_layout.addWidget(self.identity_btn)

        v.addWidget(toolbar)

        # ----- Quick links bar -----
        ql_bar = QFrame()
        ql_bar.setStyleSheet(f"""
            QFrame {{ background: {CREAM}; border-bottom: 1px solid {TAN}; }}
            QPushButton {{
                background: {CREAM_LIGHT};
                border: 1px solid {TAN};
                padding: 4px 10px;
                border-radius: 3px;
                font-size: 9pt;
            }}
            QPushButton:hover {{
                background: {PURPLE_PALE};
                border-color: {PURPLE};
            }}
        """)
        ql_layout = QHBoxLayout(ql_bar)
        ql_layout.setContentsMargins(8, 4, 8, 4)
        ql_layout.setSpacing(4)
        ql_layout.addWidget(QLabel("Quick:"))
        for name, url, tip in self.QUICK_LINKS:
            btn = QPushButton(name)
            btn.setToolTip(tip)
            btn.clicked.connect(lambda checked=False, u=url: self._navigate(u))
            ql_layout.addWidget(btn)
        ql_layout.addStretch()

        # Connection status
        self.conn_status = QLabel("Tor: Disconnected")
        self.conn_status.setStyleSheet(
            f"color: {RED_OFF}; font-weight: bold; padding: 0 8px;")
        ql_layout.addWidget(self.conn_status)

        v.addWidget(ql_bar)

        # ----- Offline banner -----
        # The request gate blocks EVERY page while Tor is offline, so spell
        # that out here with a one-click Connect button; otherwise users read
        # the blocked browser as "the tool is broken".
        self.offline_banner = QFrame()
        self.offline_banner.setStyleSheet(f"""
            QFrame {{
                background: {PURPLE_PALE};
                border: 1px solid {PURPLE_LIGHT};
                border-radius: 6px;
            }}
            QLabel {{ background: transparent; border: none; color: {PURPLE_DARK}; }}
            QPushButton {{
                background: {PURPLE};
                color: #FFFFFF;
                border: 1px solid {PURPLE_DARK};
                border-radius: 4px;
                padding: 6px 14px;
                font-weight: 700;
            }}
            QPushButton:hover {{ background: {PURPLE_LIGHT}; }}
        """)
        ob = QHBoxLayout(self.offline_banner)
        ob.setContentsMargins(14, 8, 14, 8)
        ob.setSpacing(10)
        ob_msg = QLabel(
            "Tor is not connected — every page stays blocked to protect your "
            "real IP. Connect Tor first, then browse.")
        ob_msg.setWordWrap(True)
        ob_msg.setStyleSheet(f"color: {PURPLE_DARK}; font-weight: 600;")
        ob.addWidget(ob_msg, 1)
        self.connect_btn = QPushButton("Connect Tor")
        self.connect_btn.setToolTip("Start Tor from here (same as the Dashboard button)")
        self.connect_btn.clicked.connect(self._connect_tor_from_browse)
        ob.addWidget(self.connect_btn)
        v.addWidget(self.offline_banner)

        # ----- Progress bar -----
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFixedHeight(4)
        self.progress.setTextVisible(False)
        self.progress.setVisible(False)
        v.addWidget(self.progress)

        # ----- Main web view or fallback -----
        if WEBENGINE_AVAILABLE:
            # Configure Tor SOCKS proxy for the web engine profile
            self._setup_tor_proxy()

            self.web_view = QWebEngineView()
            try:
                self.web_view.setPage(QWebEnginePage(self._profile, self.web_view))
            except Exception as e:
                print(f"Private browser page setup warning: {e}")
            self.web_view.urlChanged.connect(self._on_url_changed)
            self.web_view.loadStarted.connect(self._on_load_started)
            self.web_view.loadFinished.connect(self._on_load_finished)
            self.web_view.loadProgress.connect(self._on_load_progress)
            self.web_view.titleChanged.connect(self._on_title_changed)
            # statusBarMessage moved from QWebEngineView to QWebEnginePage in
            # newer QtWebEngine builds. Hook the page signal if present.
            try:
                page = self.web_view.page()
                if hasattr(page, "statusBarMessage"):
                    page.statusBarMessage.connect(self._on_status_message)
                elif hasattr(page, "linkHovered"):
                    page.linkHovered.connect(self._on_link_hovered)
            except Exception:
                pass
            self.web_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            v.addWidget(self.web_view, 1)

            # Status bar at bottom
            self.status_bar_lbl = QLabel("Ready")
            self.status_bar_lbl.setStyleSheet(
                f"background: {CREAM_DARK}; color: {DARK_TEXT}; "
                f"padding: 4px 10px; border-top: 1px solid {TAN_DARK};")
            self.status_bar_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            v.addWidget(self.status_bar_lbl)
        else:
            self.web_view = None
            self._build_missing_engine_view(v)

        # Connect to Tor connection events
        if hasattr(self.main_win, 'tor_panel'):
            self.main_win.tor_panel.circuitUpdated.connect(self._on_tor_updated)

    def _build_missing_engine_view(self, v):
        """Fallback view when QtWebEngine is missing, with a one-click fix.

        The installer (install.sh) checks and installs every requirement, so
        the button simply elevates and runs it; after it finishes the app must
        be restarted because Chromium must load before QApplication starts.
        """
        import shutil
        import subprocess
        from gui.requirements_check import (
            check_requirements, missing_names,
        )

        # Scroll INSIDE the existing layout (never a second top-level layout):
        # the requirement listing is taller than short windows and compressed
        # labels overlap.
        content = QWidget()
        bv = QVBoxLayout(content)
        bv.setContentsMargins(40, 28, 40, 28)
        bv.setSpacing(12)
        bv.addStretch(2)

        warn = QLabel("<center><b>The web browser engine is not installed.</b></center>")
        warn.setTextFormat(Qt.RichText)
        warn.setAlignment(Qt.AlignCenter)
        warn.setStyleSheet(f"color: {RED_OFF}; font-size: 14pt; font-weight: bold;")
        bv.addWidget(warn)

        missing = missing_names()
        if missing:
            listing = QLabel(
                "<center>Missing: " + ", ".join(missing) +
                "<br>The installer checks and installs every requirement.</center>")
        else:
            listing = QLabel("<center>PyQtWebEngine could not be loaded.</center>")
        listing.setTextFormat(Qt.RichText)
        listing.setWordWrap(True)
        listing.setAlignment(Qt.AlignCenter)
        listing.setStyleSheet(f"color: {DARK_TEXT}; font-size: 10pt;")
        bv.addWidget(listing)

        cmd = QLabel("<center><code>sudo bash install.sh</code></center>")
        cmd.setTextFormat(Qt.RichText)
        cmd.setWordWrap(True)
        cmd.setAlignment(Qt.AlignCenter)
        cmd.setStyleSheet(f"color: {MUTED}; font-size: 10pt;")
        bv.addWidget(cmd)
        bv.addSpacing(8)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        def _run_installer():
            here = os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))))
            script = os.path.join(here, "install.sh")
            if not os.path.exists(script):
                QMessageBox.warning(
                    self, "Installer Not Found",
                    "install.sh was not found next to the app files.\n\n"
                    "Run it manually from the extracted project directory:\n"
                    "sudo bash install.sh")
                return
            if os.geteuid() == 0:
                # Already root (Kali users often are): no elevation dialog.
                subprocess.Popen(["bash", script])
                QMessageBox.information(
                    self, "Installer Started",
                    "The installer is running.\n\nWhen it finishes, close and "
                    "reopen Red Tor, then return to this page.")
                return
            if shutil.which("pkexec"):
                try:
                    subprocess.Popen(["pkexec", "bash", script])
                    QMessageBox.information(
                        self, "Installer Started",
                        "The installer is running with administrator rights.\n\n"
                        "When it finishes, close and reopen Red Tor, then "
                        "return to this page.")
                    return
                except Exception as exc:
                    print(f"pkexec installer failed: {exc}")
            QMessageBox.information(
                self, "Run the Installer",
                "Run this command in a terminal (it checks and installs every "
                "missing requirement automatically):\n\n"
                "sudo bash install.sh\n\n"
                "Then restart Red Tor.")

        def _recheck():
            try:
                import importlib
                importlib.import_module("PyQt5.QtWebEngineWidgets")
                QMessageBox.information(
                    self, "Engine Available",
                    "QtWebEngine is now installed.\n\nRestart Red Tor to "
                    "enable the browser (Chromium must load before the "
                    "application window starts).")
            except Exception:
                QMessageBox.warning(
                    self, "Still Missing",
                    "QtWebEngine is still not installed.\n\n"
                    "Run: sudo bash install.sh")

        install_btn = QPushButton("  Run installer (fixes everything)")
        install_btn.setIcon(_icon("settings.png"))
        install_btn.setMinimumHeight(38)
        install_btn.setStyleSheet(
            f"QPushButton {{ background: {RED_OFF}; color: #FFFFFF; "
            f"font-weight: 700; padding: 8px 16px; border-radius: 4px; }}")
        install_btn.clicked.connect(_run_installer)
        btn_row.addWidget(install_btn)

        recheck_btn = QPushButton("  Check again")
        recheck_btn.setMinimumHeight(38)
        recheck_btn.clicked.connect(_recheck)
        btn_row.addWidget(recheck_btn)
        btn_row.addStretch(1)
        bv.addLayout(btn_row)
        bv.addStretch(3)

        req_lbl = QLabel(
            "Requirement status — anything in red needs installing:")
        req_lbl.setStyleSheet(f"color: {MUTED}; font-size: 9pt;")
        bv.addWidget(req_lbl)
        for label, ok, detail in check_requirements():
            row_lbl = QLabel(f"{'✔' if ok else '✘'}  {label}  —  {detail}")
            row_lbl.setWordWrap(True)
            row_lbl.setStyleSheet(
                f"color: {'#3FAE6E' if ok else RED_OFF}; font-size: 9pt; "
                f"font-family: monospace;")
            bv.addWidget(row_lbl)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setWidget(content)
        v.addWidget(scroll, 1)

    def _setup_tor_proxy(self):
        """Create a session-only profile with conservative web permissions.

        Chromium SOCKS routing is configured before QApplication starts in
        red_tor.py. This profile is not Tor Browser and offers no strong
        fingerprint-resistance guarantee.
        """
        try:
            # Parent-only profile constructor creates a private, off-the-record
            # profile. Keep it owned by the main window so it outlives the page.
            self._profile = QWebEngineProfile(self.main_win)
            profile = self._profile
        except Exception as e:
            print(f"Private browser profile unavailable: {e}")
            return

        try:
            profile.setPersistentCookiesPolicy(QWebEngineProfile.NoPersistentCookies)
        except Exception:
            pass
        try:
            profile.setHttpCacheType(QWebEngineProfile.MemoryHttpCache)
        except Exception:
            pass
        try:
            profile.setCookieBehavior(QWebEngineProfile.NoThirdPartyCookies)
        except Exception:
            pass
        try:
            gate = TorConnectionGate(self.main_win.tor, profile)
            profile.setUrlRequestInterceptor(gate)
            self._connection_gate = gate
        except Exception as e:
            print(f"Browser connection gate unavailable: {e}")
        try:
            settings = profile.settings()
            for attr, value in (
                ("HyperlinkAuditingEnabled", False),
                ("AllowRunningInsecureContent", False),
                ("JavascriptCanAccessClipboard", False),
                ("JavascriptCanOpenWindows", False),
            ):
                enum_value = getattr(settings, attr, None)
                if enum_value is not None:
                    settings.setAttribute(enum_value, value)
        except Exception as e:
            print(f"WebEngine security settings warning: {e}")

        # Fingerprint and compatibility: the stock QtWebEngine user agent
        # carries a "QtWebEngine/x.y" token that many CDNs bot-check or
        # outright block, which is one reason pages fail in this browser.
        # Strip the token and keep the real Chrome engine version so the
        # advertised feature set still matches the actual renderer.
        try:
            default_ua = profile.httpUserAgent() or ""
        except Exception:
            default_ua = ""
        cleaned = re.sub(r"QtWebEngine/[\d.]+\s*", "", default_ua)
        cleaned = cleaned.strip()
        if "Chrome/" not in cleaned:
            cleaned = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/83.0.4103.122 Safari/537.36")
        try:
            profile.setHttpUserAgent(cleaned)
        except Exception as e:
            print(f"User-agent override warning: {e}")
        # Fixed accept-language like Tor Browser, so the locale does not
        # leak through content negotiation either.
        try:
            profile.setHttpAcceptLanguage("en-US,en;q=0.5")
        except Exception:
            pass

    # ----- Navigation -----
    def _navigate_to_url(self):
        url = self.url_input.text().strip()
        if not url:
            return
        # If it looks like a URL, navigate to it; otherwise search
        if ("://" in url or "." in url
                or url.startswith("localhost") or url.startswith("127.0.0.1")):
            if not url.startswith("http://") and not url.startswith("https://"):
                url = "https://" + url
            self._navigate(url)
        else:
            # DuckDuckGo search through Tor
            self._navigate(f"https://duckduckgo.com/?q={url.replace(' ', '+')}")

    def _navigate(self, url):
        if not self.web_view or not getattr(self, "_connection_gate", None):
            QMessageBox.warning(
                self, "Browser Unavailable",
                "The private browser profile or Tor request gate could not be initialized. Browsing is disabled.")
            return
        if not self.main_win.tor.connected:
            QMessageBox.warning(
                self, "Tor Not Connected",
                "Please connect to a verified Tor service first.\n\n"
                "The browser request gate blocks this navigation while Tor is unavailable; no page request was sent.")
            return
        if self.web_view:
            self.web_view.setUrl(QUrl(url))
            self.url_input.setText(url)

    def _reload(self):
        if not self.web_view:
            return
        # While a page is loading, the Reload button doubles as Stop.
        if self.refresh_btn.text().strip() == "Stop":
            self.web_view.stop()
        else:
            self.web_view.reload()

    def _go_home(self):
        self._navigate(self.HOME_URL)

    def _new_identity(self):
        """Request a Tor circuit change and reload without promising a new IP."""
        if not self.main_win.tor.connected:
            QMessageBox.warning(self, "Tor Not Connected",
                                "Start Tor first.")
            return
        if not self.main_win.tor.controller:
            QMessageBox.information(
                self, "Tor Control Port Unavailable",
                "This Tor service provides SOCKS browsing only. Circuit rotation requires an accessible Tor control port.")
            return
        reply = QMessageBox.information(
            self, "Request New Circuit",
            "Request Tor to build a new circuit for future streams.\n\n"
            "The same exit IP may be selected, and this is not an identity or fingerprint reset.\n"
            "The current page will reload.",
            QMessageBox.Ok | QMessageBox.Cancel)
        if reply == QMessageBox.Ok:
            self.main_win.tor_panel.new_circuit()
            # Reload after a short delay
            QTimer.singleShot(1500, self._reload)

    # ----- Web view event handlers -----
    def _on_url_changed(self, url):
        # Do not clobber the address bar while the user is typing a URL.
        if not self.url_input.hasFocus():
            self.url_input.setText(url.toString())

    def _on_load_started(self):
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.status_bar_lbl.setText("Loading...")
        self.refresh_btn.setText("  Stop")

    def _on_load_progress(self, pct):
        self.progress.setValue(pct)

    def _on_load_finished(self, ok):
        self.progress.setVisible(False)
        self.refresh_btn.setText("  Reload")
        if ok:
            self.status_bar_lbl.setText(
                f"Loaded: {self.web_view.title() if self.web_view else ''}")
            if self.main_win.tor.controller is not None:
                self.main_win.tor_panel.refresh_circuit_async()
        else:
            self.status_bar_lbl.setText("Failed to load page")

    def _on_title_changed(self, title):
        self.status_bar_lbl.setText(f"Loaded: {title}")

    def _on_status_message(self, msg):
        if msg:
            self.status_bar_lbl.setText(msg)

    def _on_link_hovered(self, url):
        """Show the URL the mouse is hovering over in the status bar."""
        if url:
            self.status_bar_lbl.setText(str(url))

    def _connect_tor_from_browse(self):
        """Start Tor directly from the Browse page (same flow as Dashboard)."""
        panel = getattr(self.main_win, "tor_panel", None)
        if panel is not None and hasattr(panel, "start_tor"):
            panel.start_tor()

    def _on_tor_updated(self, circ):
        """Called when Tor circuit updates."""
        banner = getattr(self, "offline_banner", None)
        if banner is not None:
            banner.setVisible(not self.main_win.tor.connected)
        if self.main_win.tor.connected:
            mode = "LIVE"
            self.conn_status.setText(f"Tor: Connected ({mode})")
            self.conn_status.setStyleSheet(
                f"color: {GREEN_OK}; font-weight: bold; padding: 0 8px;")
        else:
            self.conn_status.setText("Tor: Disconnected")
            self.conn_status.setStyleSheet(
                f"color: {RED_OFF}; font-weight: bold; padding: 0 8px;")

    def clear_session_data(self):
        """Clear this off-the-record browser's current page and transient data."""
        profile = getattr(self, "_profile", None)
        if not self.web_view or profile is None or not getattr(self, "_connection_gate", None):
            return False
        try:
            self.web_view.stop()
            self.web_view.setUrl(QUrl("about:blank"))
            self.web_view.page().history().clear()
            profile.cookieStore().deleteAllCookies()
            profile.clearHttpCache()
            self.url_input.clear()
            self.status_bar_lbl.setText("Private browser session cleared")
            return True
        except Exception as exc:
            print(f"Browser session clear warning: {exc}")
            return False

    def shutdown(self):
        """Delete the active page before releasing its off-the-record profile."""
        if not self.web_view or not WEBENGINE_AVAILABLE:
            return
        try:
            view = self.web_view
            profile = getattr(self, "_profile", None)
            view.stop()
            # The page is owned by the view. Destroy that pair first; replacing
            # it with a default-profile page can itself outlive QApplication.
            view.deleteLater()
            QCoreApplication.sendPostedEvents(view, QEvent.DeferredDelete)
            QCoreApplication.processEvents()
            self.web_view = None
            self._connection_gate = None
            if profile is not None:
                profile.deleteLater()
                QCoreApplication.sendPostedEvents(profile, QEvent.DeferredDelete)
                self._profile = None
                QCoreApplication.processEvents()
        except Exception as e:
            print(f"Browser shutdown cleanup warning: {e}")

    def showEvent(self, ev):
        super().showEvent(ev)
        self._on_tor_updated({})

    def navigate_home_if_empty(self):
        """Auto-navigate to check.torproject.org if view is empty."""
        if self.web_view and self.web_view.url().isEmpty():
            if self.main_win.tor.connected:
                self._navigate(self.HOME_URL)
