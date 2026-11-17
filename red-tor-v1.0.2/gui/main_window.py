"""Red Tor - main application window.

Layout for Red Tor: a fixed left
sidebar (red onion logo, app navigation and footer) and a
large main content area (light bg with a faint world-map watermark). The
nav items switch between pages stacked in a QStackedWidget.
"""
import os
import sys
from PyQt5.QtCore import Qt, QSize, QTimer
from PyQt5.QtGui import QIcon, QFont, QPixmap, QPainter
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QFrame, QStackedWidget,
    QStatusBar, QMenuBar, QMenu, QAction, QMessageBox, QApplication, QLabel,
    QPushButton, QButtonGroup,
)

from gui.theme import (
    VIOLET, VIOLET_DARK, VIOLET_LIGHT, TEAL, RED_HARD, NIGHT, NIGHT_2, NIGHT_3,
    ICE, ICE_LIGHT, FROST, FROST_DIM, GLACIER, GREEN_OK, PURPLE_PALE,
)
from gui import ASSETS, ICONS
from gui.animations import AnimatedStack, PulsingDot, apply_depth_effects
from tor_core import TorManager
from .tor_panel import TorPanel
from .tabs.dashboard import DashboardTab
from .tabs.browse import BrowseTab
from .tabs.privacy_tools import PrivacyToolsTab
from .tabs.diagnostics import DiagnosticsTab
from .tabs.network_monitor import NetworkMonitorTab
from .tabs.transfer import TransferTab
from .tabs.terminal import TerminalTab
from .tabs.settings import SettingsTab
from .tabs.about import AboutTab


def _icon(name):
    p = os.path.join(ICONS, name)
    return QIcon(p) if os.path.exists(p) else QIcon()


# Sidebar nav items: (label, icon, page_widget_factory_method, tooltip)
_NAV = [
    ("Dashboard",       "home.png",     "dashboard",       "Verified Tor session state and app activity log"),
    ("Tor Connection",   "globe.png",    "tor_panel",        "Connect to Tor and view control-port circuit data when available"),
    ("Browse",           "browse.png",   "browse",           "Chromium browser using the local Tor SOCKS proxy; not Tor Browser"),
    ("Network Monitor",  "path.png",     "network_monitor",  "Tor daemon counters when available; otherwise app-only request counters"),
    ("Transfer Stats",   "path.png",     "transfer",         "Measured app-side transfer-rate chart"),
    ("Diagnostics",      "shield.png",   "diag",             "Tor-routed HTTPS check only; no direct-IP or DNS leak test"),
    ("Privacy Tools",    "shield.png",   "privacy_tools",             "Session wipe, new identity, port probe, exit-country control"),
    ("Terminal",         "send.png",     "terminal",         "Kali-style root terminal: commands run on this system as root"),
    ("Settings",         "settings.png", "settings",         "Exit-country and optional, approximate GeoIP preferences"),
    ("About Red Tor",    "about.png",    "about",            "Version, dependencies and security limitations"),
]


class RedTorWindow(QMainWindow):
    """Top-level Red Tor desktop window."""

    def __init__(self, startup_progress=None):
        super().__init__()
        self._startup_progress = startup_progress
        self._report_startup(4, "Preparing the Red Tor window")
        self.setWindowTitle("Red Tor")
        self.setGeometry(60, 40, 1280, 740)
        self.setMinimumSize(1024, 640)

        icon_path = os.path.join(ASSETS, "logo_icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Tor manager (core)
        self.tor = TorManager()
        self._report_startup(14, "Tor manager initialized; no Tor connection started")

        self._build_ui()
        self._build_menu()
        self._build_statusbar()
        self._build_brand_watermark()
        self._report_startup(100, "Interface ready; Tor remains disconnected until you connect")

    def _report_startup(self, percent, message):
        if self._startup_progress is not None:
            self._startup_progress(percent, message)

    # ---- UI build ----------------------------------------------------------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ---- Sidebar ----
        self.sidebar = self._build_sidebar()
        layout.addWidget(self.sidebar)

        # ---- Main content area ----
        content = QFrame()
        content.setObjectName("content")
        content.setStyleSheet(f"QFrame#content {{ background-color: {NIGHT}; }}")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)

        # Header row
        header = self._build_header()
        cl.addWidget(header)

        # Stacked pages (page switches animate with a fade + slide lift)
        self.stack = AnimatedStack()
        self.stack.setContentsMargins(0, 0, 0, 0)

        # Build each page once; no hidden demo, inbox, or experimental routing pages.
        self._report_startup(20, "Main window shell created")
        self.tor_panel = TorPanel(self)
        self._report_startup(28, "Tor connection page initialized")
        self.dashboard_tab = DashboardTab(self)
        self._report_startup(36, "Dashboard initialized")
        self.transfer_tab = TransferTab(self)
        self._report_startup(44, "Transfer stats initialized")
        self.browse_tab = BrowseTab(self)
        self._report_startup(52, "Browser profile and request gate initialized")
        self.network_monitor_tab = NetworkMonitorTab(self)
        self._report_startup(60, "Network Monitor initialized")
        self.diag_tab = DiagnosticsTab(self)
        self._report_startup(68, "Tor diagnostics initialized")
        self.privacy_tools_tab = PrivacyToolsTab(self)
        self._report_startup(76, "Privacy controls initialized")
        self.terminal_tab = TerminalTab(self)
        self._report_startup(88, "Root terminal initialized")
        self.settings_tab = SettingsTab(self)
        self._report_startup(94, "Settings loaded")
        self.about_tab = AboutTab(self)
        self._report_startup(96, "About page loaded")

        self._pages = {
            "dashboard": self.dashboard_tab,
            "tor_panel": self.tor_panel,
            "browse": self.browse_tab,
            "network_monitor": self.network_monitor_tab,
            "transfer": self.transfer_tab,
            "diag": self.diag_tab,
            "privacy_tools": self.privacy_tools_tab,
            "terminal": self.terminal_tab,
            "settings": self.settings_tab,
            "about": self.about_tab,
        }
        for _label, _icon_name, key, _tip in _NAV:
            self.stack.addWidget(self._pages[key])

        cl.addWidget(self.stack, 1)
        layout.addWidget(content, 1)

        # 3D depth: soft card shadows + red glow under primary buttons
        apply_depth_effects(self)

        # Connect signals
        self.tor_panel.circuitUpdated.connect(self._on_circuit_updated)
        self._select_nav("dashboard")

    def _build_sidebar(self):
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(252)
        side.setStyleSheet(f"""
            QFrame#sidebar {{
                background-color: {NIGHT_2};
                border-right: 1px solid {ICE_LIGHT};
            }}
        """)
        v = QVBoxLayout(side)
        v.setContentsMargins(18, 22, 18, 22)
        v.setSpacing(10)

        # Top: user-provided red logo + Red Tor wordmark + tagline
        logo_lbl = QLabel()
        logo_lbl.setAlignment(Qt.AlignCenter)
        logo_path = os.path.join(ASSETS, "logo.png")
        if os.path.exists(logo_path):
            pix = QPixmap(logo_path).scaled(
                78, 78, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_lbl.setPixmap(pix)
        v.addWidget(logo_lbl)

        brand = QLabel(
            f"<div style='text-align:center;'>"
            f"<span style='color:{RED_HARD}; font-size:22px; font-weight:bold; "
            f"letter-spacing:2px;'>RED TOR</span></div>")
        brand.setTextFormat(Qt.RichText)
        brand.setAlignment(Qt.AlignCenter)
        v.addWidget(brand)

        tagline = QLabel("Local Tor client interface")
        tagline.setAlignment(Qt.AlignCenter)
        tagline.setStyleSheet(f"color: {FROST}; font-size: 8pt; font-weight: 600;")
        v.addWidget(tagline)

        v.addSpacing(10)

        # Nav items (checkable QPushButtons in a button group)
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons = {}
        for label, icon_name, key, tooltip in _NAV:
            btn = QPushButton(f"  {_icon(icon_name).isNull() and '' or ''}{label}")
            btn.setObjectName("navBtn")
            btn.setText(label)
            btn.setIcon(_icon(icon_name))
            btn.setIconSize(QSize(18, 18))
            btn.setCheckable(True)
            btn.setToolTip(tooltip)
            btn.setStatusTip(tooltip)
            btn.clicked.connect(lambda _=False, k=key: self._select_nav(k))
            self.nav_group.addButton(btn)
            self.nav_buttons[key] = btn
            v.addWidget(btn)
        # Default selection
        self.nav_buttons["dashboard"].setChecked(True)

        v.addStretch(1)

        # Decorative red divider
        sep = QFrame()
        sep.setFixedHeight(2)
        sep.setStyleSheet(f"background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
                         f"stop:0 transparent, stop:0.5 {VIOLET}, stop:1 transparent);")
        v.addWidget(sep)

        # Footer brand
        sd = QLabel("Red Tor")
        sd.setAlignment(Qt.AlignCenter)
        sd.setStyleSheet(f"color: {RED_HARD}; font-size: 10pt; font-weight: bold;")
        v.addWidget(sd)
        sd_sub = QLabel("Local Tor interface")
        sd_sub.setAlignment(Qt.AlignCenter)
        sd_sub.setStyleSheet(f"color: {FROST_DIM}; font-size: 8pt;")
        v.addWidget(sd_sub)
        return side

    def _build_header(self):
        header = QFrame()
        header.setFixedHeight(70)
        header.setStyleSheet(f"background-color: {NIGHT_2}; "
                             f"border-bottom: 1px solid {ICE_LIGHT};")
        h = QHBoxLayout(header)
        h.setContentsMargins(28, 10, 28, 10)
        h.setSpacing(14)

        title = QLabel(
            f"<span style='color:{RED_HARD}; font-size:30px; font-weight:bold;'>"
            f"RED TOR</span>")
        title.setTextFormat(Qt.RichText)
        h.addWidget(title)

        sub = QLabel("Linux desktop client for a local Tor service")
        sub.setStyleSheet(f"color: {FROST_DIM}; font-size: 10pt; font-weight: 500;")
        h.addWidget(sub)

        h.addStretch(1)

        # Pulsing status light: red (off) / amber (connecting) / green (ok)
        self.header_dot = PulsingDot("off", header)
        h.addWidget(self.header_dot)

        # Connection badge starts idle; this app does not secure the whole system.
        self.header_badge = QLabel("Tor not connected")
        self.header_badge.setStyleSheet(
            f"background: {PURPLE_PALE}; color: {VIOLET_DARK}; "
            f"padding: 6px 14px; border-radius: 14px; "
            f"font-weight: 600; font-size: 9pt; "
            f"border: 1px solid {ICE_LIGHT};")
        h.addWidget(self.header_badge)
        return header

    # ---- Navigation --------------------------------------------------------
    def _select_nav(self, key):
        page = self._pages.get(key)
        if page is None:
            return
        idx = self.stack.indexOf(page)
        if idx >= 0:
            self.stack.setCurrentIndex(idx)
        # sync button highlight
        for k, b in self.nav_buttons.items():
            b.setChecked(k == key)
        # refresh certain pages
        if key == "dashboard":
            self.dashboard_tab.refresh()
        elif key == "network_monitor":
            self.network_monitor_tab.refresh()
        elif key == "terminal":
            self.terminal_tab.refresh()
        elif key == "browse":
            # Focus the URL bar when the user opens the Browse tab
            if hasattr(self.browse_tab, "url_input"):
                try:
                    self.browse_tab.url_input.setFocus()
                    self.browse_tab.url_input.selectAll()
                except Exception:
                    pass

    def go_to(self, key):
        """Public: navigate to a page (e.g. dashboard 'Connect to Tor' button)."""
        self._select_nav(key)

    # ---- Menu / statusbar --------------------------------------------------
    def _build_brand_watermark(self):
        wm = QLabel(" Red Tor · local Tor interface ")
        wm.setStyleSheet(
            f"color: {VIOLET_DARK}; background: {NIGHT_3}; "
            f"padding: 2px 8px; border-radius: 3px; "
            f"font-weight: 600; font-size: 8pt; "
            f"border: 1px solid {ICE_LIGHT};")
        self.status_bar.addPermanentWidget(wm, 0)

    def _build_menu(self):
        mb = self.menuBar()
        m_file = mb.addMenu("File")
        a_exit = QAction("Exit", self); a_exit.setShortcut("Ctrl+Q")
        a_exit.triggered.connect(self.close); m_file.addAction(a_exit)

        m_tor = mb.addMenu("Tor")
        a_start = QAction("Start Tor", self); a_start.setShortcut("Ctrl+T")
        a_start.triggered.connect(self.tor_panel.start_tor); m_tor.addAction(a_start)
        a_stop = QAction("Stop Tor", self); a_stop.setShortcut("Ctrl+Shift+T")
        a_stop.triggered.connect(self.tor_panel.stop_tor); m_tor.addAction(a_stop)
        m_tor.addSeparator()
        a_new = QAction("New Circuit", self); a_new.setShortcut("Ctrl+N")
        a_new.triggered.connect(self.tor_panel.new_circuit); m_tor.addAction(a_new)
        a_ref = QAction("Refresh Circuit View", self); a_ref.setShortcut("F5")
        a_ref.triggered.connect(self.tor_panel.refresh_circuit_async); m_tor.addAction(a_ref)
        m_tor.addSeparator()
        a_disconnect = QAction("Disconnect Red Tor Session", self)
        a_disconnect.setShortcut("Ctrl+Shift+K")
        a_disconnect.triggered.connect(self._disconnect_app); m_tor.addAction(a_disconnect)

        m_view = mb.addMenu("View")
        for label, _, key, _tip in _NAV:
            a = QAction(label, self)
            a.setStatusTip(_tip)
            a.triggered.connect(lambda _=False, k=key: self._select_nav(k))
            m_view.addAction(a)

        m_help = mb.addMenu("Help")
        a_about = QAction("About Red Tor", self)
        a_about.triggered.connect(lambda: self._select_nav("about"))
        m_help.addAction(a_about)
        a_about_qt = QAction("About Qt", self)
        a_about_qt.triggered.connect(QApplication.aboutQt)
        m_help.addAction(a_about_qt)

    def _build_statusbar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_conn = QLabel(" Disconnected ")
        self.status_conn.setStyleSheet(
            f"color: #111111; background: {PURPLE_PALE}; padding: 2px 8px; "
            f"font-weight: bold; border-radius: 3px;")
        self.status_bar.addPermanentWidget(self.status_conn)
        self.status_bar.showMessage(
            "Red Tor ready. Tor is not connected; connect when you choose.", 5000)

    # ---- Cross-page events -------------------------------------------------
    def set_conn_state(self, state):
        """Pulse the header light: 'off', 'busy' or 'ok' (green)."""
        dot = getattr(self, "header_dot", None)
        if dot is not None:
            try:
                dot.set_state(state)
            except Exception:
                pass

    def _on_circuit_updated(self, circ):
        self.dashboard_tab.refresh()
        self.browse_tab._on_tor_updated(circ)
        if self.tor.connected:
            mode = "SOCKS only" if self.tor.socks_only else "Control port"
            self.status_conn.setText(f" Tor connected ({mode}) ")
            self.status_conn.setStyleSheet(
                f"color: #111111; background: #E8F5E9; "
                f"padding: 2px 8px; font-weight: bold; border-radius: 3px;")
            self.header_badge.setText("Tor verified for this app only")
            self.header_badge.setStyleSheet(
                f"background: {PURPLE_PALE}; color: {VIOLET_DARK}; "
                f"padding: 6px 14px; border-radius: 14px; "
                f"font-weight: 600; font-size: 9pt; "
                f"border: 1px solid {VIOLET_LIGHT};")
            self.set_conn_state("ok")
            QTimer.singleShot(500, self.browse_tab.navigate_home_if_empty)
        else:
            self.status_conn.setText(" Disconnected ")
            self.status_conn.setStyleSheet(
                f"color: #111111; background: {PURPLE_PALE}; "
                f"padding: 2px 8px; font-weight: bold; border-radius: 3px;")
            self.header_badge.setText("Tor not connected")
            self.header_badge.setStyleSheet(
                f"background: {NIGHT_3}; color: {FROST_DIM}; "
                f"padding: 6px 14px; border-radius: 14px; "
                f"font-weight: 600; font-size: 9pt; "
                f"border: 1px solid {ICE_LIGHT};")
            self.set_conn_state("off")

    def _disconnect_app(self):
        reply = QMessageBox.warning(
            self, "Disconnect App Tor",
            "This disconnects the app's Tor session. It does not block all system traffic; other applications may continue using your normal network.\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.Cancel)
        if reply != QMessageBox.Yes:
            return
        self.tor_panel.stop_tor()
        self.privacy_tools_tab.refresh()
        QMessageBox.information(self, "Tor Disconnected",
                                "Red Tor's session was disconnected. Other applications were not blocked.")

    def closeEvent(self, ev):
        # Stop the circuit-retry timer first so no queued refresh spawns a
        # worker thread against widgets that are about to be destroyed.
        self.tor_panel.shutdown()
        self.browse_tab.shutdown()
        self.terminal_tab.shutdown()
        if self.tor.connected:
            self.tor.disconnect()
        super().closeEvent(ev)
