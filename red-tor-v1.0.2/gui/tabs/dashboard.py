"""Red Tor - Dashboard tab (Privacy Dashboard layout).

Matches the Red Tor Privacy Dashboard mockup:
  - 4 stat cards (Privacy Status / Tor Network / Your IP / Uptime)
  - Tor Connection hero card with red CTA + Quick Tools 2x2 grid
  - App Activity Log (the transfer-rate chart moved to its own Transfer
    Stats page; see gui/tabs/transfer.py)
"""
import os
import time
from datetime import datetime
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QIcon, QColor, QPainter, QPen, QBrush, QPixmap
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QGroupBox, QFrame, QSizePolicy, QScrollArea, QPlainTextEdit,
)

from gui.theme import (
    NIGHT, NIGHT_2, NIGHT_3, ICE, ICE_LIGHT, FROST, FROST_DIM, GLACIER,
    VIOLET, VIOLET_DARK, VIOLET_LIGHT, PURPLE_PALE,
    GREEN_OK, AMBER, RED_OFF, RED_HARD, BLUE_INFO, TEAL,
)

# Terminal prefix and color per Tor-manager event level.
_LEVEL_PREFIX = {"OK": "[+]", "INFO": "[i]", "WARN": "[!]", "ERROR": "[x]"}
_LEVEL_COLOR = {"OK": "#3FAE6E", "INFO": "#7BA7CC",
                "WARN": "#E89A0C", "ERROR": "#E01414"}
_DEFAULT_COLOR = "#6B6B73"


from gui import ICONS, ASSETS


def _icon(name):
    p = os.path.join(ICONS, name)
    return QIcon(p) if os.path.exists(p) else QIcon()


def _card(title, icon_name, value, value_color, subtitle):
    """Build a white stat card matching the mockup (red icon + big value)."""
    card = QFrame()
    card.setObjectName("card")
    card.setFixedHeight(110)
    h = QHBoxLayout(card)
    # Slim padding: four cards must fit side by side at the 1024 px minimum
    # window width without needing the horizontal scrollbar.
    h.setContentsMargins(10, 12, 10, 12)
    h.setSpacing(10)
    # Icon column
    icon_lbl = QLabel()
    icon_lbl.setPixmap(_icon(icon_name).pixmap(36, 36))
    icon_lbl.setFixedSize(40, 40)
    h.addWidget(icon_lbl)
    # Text column
    v = QVBoxLayout()
    v.setSpacing(2)
    t = QLabel(title)
    t.setStyleSheet(f"color: {FROST_DIM}; font-size: 9pt; font-weight: 600;")
    v.addWidget(t)
    val = QLabel(value)
    val.setStyleSheet(f"color: {value_color}; font-size: 22pt; font-weight: bold;")
    v.addWidget(val)
    sub = QLabel(subtitle)
    sub.setStyleSheet(f"color: {FROST_DIM}; font-size: 8pt;")
    v.addWidget(sub)
    v.addStretch(1)
    h.addLayout(v, 1)
    return card, val, sub


class DashboardTab(QWidget):
    """Privacy Dashboard - the screenshot's main page."""

    activityUpdated = pyqtSignal(str, str)

    def __init__(self, main_win):
        super().__init__()
        self.main_win = main_win
        self.tor = main_win.tor
        self._connect_time = None
        self._exit_ip = None
        self._connect_time = None
        self._build()
        self.refresh()
        self.main_win.tor_panel.connectedEvent.connect(self._on_connect_result)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(2000)

        self.tor.add_listener(self._on_activity)
        self.activityUpdated.connect(self._append_activity)

    # ---- UI build ----
    def _build(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        # Horizontal scrollbar when the window is narrow: the fourth stat
        # card and Quick Tools buttons were silently clipped before.
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        inner = QWidget()
        outer = QVBoxLayout(inner)
        outer.setContentsMargins(22, 20, 22, 20)
        outer.setSpacing(16)

        # ---- Row 1: 4 stat cards ----
        cards_row = QHBoxLayout()
        cards_row.setSpacing(10)
        self.privacy_card, self.privacy_val, self.privacy_sub = _card(
            "Tor Status", "shield.png", "Not connected", RED_OFF, "Tor check has not passed")
        self.tor_card, self.tor_val, self.tor_sub = _card(
            "Tor Network", "globe.png", "Offline", RED_OFF, "Not connected")
        self.ip_card, self.ip_val, self.ip_sub = _card(
            "IP Check", "shield.png", "Not tested", FROST, "No direct-IP probe was made")
        self.uptime_card, self.uptime_val, self.uptime_sub = _card(
            "Session time", "path.png", "00:00:00", FROST, "No verified app session")
        for c in (self.privacy_card, self.tor_card, self.ip_card, self.uptime_card):
            cards_row.addWidget(c, 1)
        outer.addLayout(cards_row)

        # ---- Row 2: Tor Connection hero + Quick Tools (2:1 ratio) ----
        mid_row = QHBoxLayout()
        mid_row.setSpacing(14)

        # Hero card
        self.hero = self._build_hero()
        mid_row.addWidget(self.hero, 2)

        # Quick tools 2x2
        qt = self._build_quick_tools()
        mid_row.addWidget(qt, 1)
        outer.addLayout(mid_row)

        # ---- Row 3: App Activity Log (full width; the rate chart lives on
        # its own Transfer Stats page now) ----
        bot_row = QHBoxLayout()
        bot_row.setSpacing(14)
        self.terminal = self._build_terminal()
        bot_row.addWidget(self.terminal, 1)
        outer.addLayout(bot_row, 1)

        scroll.setWidget(inner)
        wrapper = QVBoxLayout(self)
        wrapper.setContentsMargins(0, 0, 0, 0)
        wrapper.addWidget(scroll)

    def _build_hero(self):
        card = QFrame()
        card.setObjectName("card")
        h = QHBoxLayout(card)
        h.setContentsMargins(20, 20, 20, 20)
        h.setSpacing(20)

        # Onion illustration (left)
        onion = QLabel()
        onion.setFixedSize(120, 120)
        onion_path = os.path.join(ASSETS, "logo.png")
        if os.path.exists(onion_path):
            from PyQt5.QtGui import QPixmap
            pix = QPixmap(onion_path).scaled(
                110, 110, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            onion.setPixmap(pix)
        onion.setAlignment(Qt.AlignCenter)
        h.addWidget(onion)

        # Vertical separator
        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setStyleSheet(f"background: {ICE_LIGHT};")
        h.addWidget(sep)

        # Text + CTA (right)
        v = QVBoxLayout()
        v.setSpacing(6)
        title = QLabel("Tor Connection")
        title.setStyleSheet(f"color: {FROST}; font-size: 16pt; font-weight: bold;")
        v.addWidget(title)
        desc = QLabel(
            "Connect to a verified local Tor service. This affects this app's "
            "configured browser only; it does not protect other applications.")
        desc.setStyleSheet(f"color: {FROST_DIM}; font-size: 10pt;")
        desc.setWordWrap(True)
        v.addWidget(desc)
        v.addSpacing(8)
        self.connect_btn = QPushButton("▶  Connect to Tor")
        self.connect_btn.setObjectName("primaryBtn")
        self.connect_btn.setIcon(_icon("power.png"))
        self.connect_btn.clicked.connect(self._connect_tor)
        v.addWidget(self.connect_btn)
        v.addStretch(1)
        h.addLayout(v, 1)
        return card

    def _build_quick_tools(self):
        card = QFrame()
        card.setObjectName("card")
        v = QVBoxLayout(card)
        v.setContentsMargins(16, 16, 16, 16)
        v.setSpacing(12)
        head = QLabel("⚡  Quick Tools")
        head.setStyleSheet(f"color: {VIOLET_DARK}; font-size: 11pt; font-weight: bold;")
        v.addWidget(head)

        grid = QGridLayout()
        grid.setSpacing(10)
        tools = [
            ("New Circuit",     "shield.png",       self._new_circuit),
            ("Network Monitor", "path.png",         lambda: self.main_win.go_to("network_monitor")),
            ("Open Terminal",   "send.png",         lambda: self.main_win.go_to("terminal")),
            ("Tor Check",       "shield.png",       lambda: self.main_win.go_to("diag")),
        ]
        for i, (label, icon_name, slot) in enumerate(tools):
            b = QPushButton(f" {label}")
            b.setIcon(_icon(icon_name))
            b.setStyleSheet(f"""
                QPushButton {{
                    background: {NIGHT_2}; color: {FROST};
                    border: 1px solid {ICE_LIGHT}; border-radius: 8px;
                    padding: 14px 10px; text-align: left;
                    font-weight: 500; font-size: 10pt;
                }}
                QPushButton:hover {{
                    background: {PURPLE_PALE}; color: {VIOLET_DARK};
                    border-color: {VIOLET_LIGHT};
                }}
            """)
            b.clicked.connect(slot)
            grid.addWidget(b, i // 2, i % 2)
        v.addLayout(grid, 1)
        return card

    def _build_terminal(self):
        card = QFrame()
        card.setObjectName("card")
        outer = QVBoxLayout(card)
        outer.setContentsMargins(14, 12, 14, 14)
        outer.setSpacing(8)
        # Header
        hh = QHBoxLayout()
        title = QLabel(">_  App Activity Log")
        title.setStyleSheet(f"color: {VIOLET_DARK}; font-size: 11pt; font-weight: bold;")
        hh.addWidget(title)
        hh.addStretch(1)
        clear_btn = QPushButton("🗑  Clear")
        clear_btn.setStyleSheet(
            f"background: {NIGHT_3}; color: {FROST_DIM}; border: none; "
            f"border-radius: 10px; padding: 4px 12px; font-size: 9pt;")
        clear_btn.clicked.connect(self._clear_terminal)
        hh.addWidget(clear_btn)
        outer.addLayout(hh)
        # Terminal text
        self.term_edit = QPlainTextEdit()
        self.term_edit.setReadOnly(True)
        self.term_edit.setStyleSheet(f"""
            QPlainTextEdit {{
                background: #FFFFFF;
                color: #111111;
                border: 1px solid #D8D8DD;
                border-radius: 8px;
                padding: 10px;
                font-family: 'DejaVu Sans Mono', 'Liberation Mono', monospace;
                font-size: 10pt;
            }}
        """)
        outer.addWidget(self.term_edit, 1)
        # Initial boot lines
        self._append_terminal_line("INFO", "Red Tor interface started.")
        self._append_terminal_line("INFO", "Connect only when you want this app to use a verified Tor service.")
        return card


    # ---- Activity feed ----
    def _on_activity(self, level, msg):
        self.activityUpdated.emit(level, msg)

    def _append_activity(self, level, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        prefix = _LEVEL_PREFIX.get(level, "[*]")
        self._append_terminal_line(level, f"{prefix} [{ts}] {msg}")

    def _append_terminal_line(self, level, line):
        color = _LEVEL_COLOR.get(level, _DEFAULT_COLOR)
        self.term_edit.appendHtml(
            f"<span style='color:{color};'>{line}</span>")
        # Keep last 200 lines
        if self.term_edit.blockCount() > 200:
            self.term_edit.setMaximumBlockCount(200)

    def _clear_terminal(self):
        self.term_edit.clear()

    # ---- Quick actions ----
    def _connect_tor(self):
        if self.tor.connected:
            self.main_win.go_to("browse")
            return
        if not self.connect_btn.isEnabled():
            return
        self.connect_btn.setEnabled(False)
        self.connect_btn.setText("⏳  Connecting...")
        self.main_win.tor_panel.start_tor()

    def _on_connect_result(self, ok, msg, ip):
        self.connect_btn.setEnabled(True)
        self._exit_ip = ip if ok and self.tor.connected else None
        self.refresh()
        if ok and self.tor.connected:
            self.connect_btn.setText("Open Browse")
        else:
            self.connect_btn.setText("▶  Connect to Tor")

    def _new_circuit(self):
        if not self.tor.connected:
            self._append_terminal_line("WARN", "[!] Connect to Tor first.")
            return
        self.main_win.tor_panel.new_circuit()
        self._append_terminal_line("OK", "[+] Requesting a new Tor circuit (NEWNYM)...")

    # ---- Refresh ----
    def refresh(self):
        if self.connect_btn.isEnabled():
            self.connect_btn.setText(
                "Open Browse" if self.tor.connected
                else "▶  Connect to Tor")
        # Stat cards
        if self.tor.connected:
            mode = "SOCKS only" if self.tor.socks_only else "Control port"
            self.privacy_val.setText("Tor verified")
            self.privacy_val.setStyleSheet(f"color: {GREEN_OK}; font-size: 20pt; font-weight: bold;")
            self.privacy_sub.setText(f"App connection only ({mode})")
            self.tor_val.setText("Online")
            self.tor_val.setStyleSheet(f"color: {GREEN_OK}; font-size: 22pt; font-weight: bold;")
            self.tor_sub.setText(mode)
            self.ip_val.setText(self._exit_ip or "Not checked")
            self.ip_val.setStyleSheet(f"color: {VIOLET}; font-size: 13pt; font-weight: bold;")
            self.ip_sub.setText("Tor exit IP only · direct IP not queried")
            if self._connect_time is None:
                self._connect_time = time.time()
            up = int(time.time() - self._connect_time)
            hh, mm, ss = up // 3600, (up % 3600) // 60, up % 60
            self.uptime_val.setText(f"{hh:02d}:{mm:02d}:{ss:02d}")
            self.uptime_sub.setText("Since this app session connected")
        else:
            self._exit_ip = None
            self._connect_time = None
            self.privacy_val.setText("Idle")
            self.privacy_val.setStyleSheet(f"color: {FROST}; font-size: 22pt; font-weight: bold;")
            self.privacy_sub.setText("Tor is not connected")
            self.tor_val.setText("Offline")
            self.tor_val.setStyleSheet(f"color: {RED_OFF}; font-size: 22pt; font-weight: bold;")
            self.tor_sub.setText("Not connected")
            self.ip_val.setText("Unverified")
            self.ip_val.setStyleSheet(f"color: {RED_OFF}; font-size: 22pt; font-weight: bold;")
            self.ip_sub.setText("No Tor exit check is available")
            self.uptime_val.setText("00:00:00")
            self.uptime_sub.setText("No verified app session")
        # Transfer-rate sampling moved to the Transfer Stats page.
