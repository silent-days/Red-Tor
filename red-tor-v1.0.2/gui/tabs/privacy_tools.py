"""Real app-session privacy controls; no system firewall changes."""
import socket

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QMessageBox, QComboBox, QApplication, QGroupBox,
)

from gui.theme import (
    CREAM_LIGHT, CREAM_DARK, DARK_TEXT, MUTED, TEAL, GREEN_OK, AMBER,
    RED_HARD, RED_OFF, PURPLE_PALE, TAN_DARK, VIOLET_DARK,
)
from tor_core import EXIT_COUNTRIES


class PrivacyToolsTab(QWidget):
    """App-scoped controls; does not control other programs or the firewall."""
    def __init__(self, main_win):
        super().__init__()
        self.main_win = main_win
        self.tor = main_win.tor
        self._build()
        self.refresh()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(2500)

    def _build(self):
        from gui.scroll_wrap import wrap_in_scroll
        content = wrap_in_scroll(self)
        outer = QVBoxLayout(content)
        outer.setContentsMargins(22, 20, 22, 20)
        outer.setSpacing(12)
        title = QLabel("Privacy Tools")
        title.setFont(QFont("Sans", 18, QFont.Bold))
        title.setStyleSheet(f"color: {TEAL};")
        outer.addWidget(title)
        note = QLabel("These controls affect only Red Tor. The app does not modify the system firewall or protect other applications.")
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {DARK_TEXT}; background: {CREAM_DARK}; padding: 10px 12px; border: 1px solid {TAN_DARK};")
        outer.addWidget(note)

        status = QFrame()
        status.setStyleSheet(f"background: {CREAM_LIGHT}; border: 1px solid {TAN_DARK}; border-radius: 5px;")
        grid = QVBoxLayout(status)
        self.tor_state = QLabel()
        self.browser_state = QLabel()
        self.gate_state = QLabel()
        for label in (self.tor_state, self.browser_state, self.gate_state):
            label.setStyleSheet(f"color: {DARK_TEXT}; padding: 5px;")
            grid.addWidget(label)
        outer.addWidget(status)

        # ---- App session controls ----
        controls = QFrame()
        controls.setStyleSheet(f"background: {CREAM_LIGHT}; border: 1px solid {TAN_DARK}; border-radius: 5px;")
        cv = QVBoxLayout(controls)
        heading = QLabel("App session controls")
        heading.setFont(QFont("Sans", 12, QFont.Bold))
        heading.setStyleSheet(f"color: {DARK_TEXT}; border: none;")
        cv.addWidget(heading)
        self.clear_btn = QPushButton("Clear browser session data")
        self.clear_btn.clicked.connect(self._clear_browser)
        cv.addWidget(self.clear_btn)
        row = QHBoxLayout()
        check = QPushButton("Verify Tor route")
        check.clicked.connect(lambda: self.main_win.go_to("diag"))
        row.addWidget(check)
        disconnect = QPushButton("Disconnect this app from Tor")
        disconnect.setStyleSheet(f"background: {PURPLE_PALE}; color: #111111; border: 1px solid {RED_OFF}; font-weight: 700; padding: 8px;")
        disconnect.clicked.connect(self.main_win._disconnect_app)
        row.addWidget(disconnect)
        cv.addLayout(row)
        outer.addWidget(controls)

        # ---- New identity: fresh circuit + wiped browser session ----
        ident = QGroupBox("New identity (this app)")
        iv = QVBoxLayout(ident)
        self.identity_btn = QPushButton("New Identity: wipe browser session + request new circuit")
        self.identity_btn.setStyleSheet(
            f"QPushButton {{ background: {PURPLE_PALE}; color: #111111; "
            f"border: 1px solid {VIOLET_DARK}; font-weight: 700; padding: 8px; }}")
        self.identity_btn.clicked.connect(self._new_identity)
        iv.addWidget(self.identity_btn)
        ident_note = QLabel("Combines two actions: the browser's page, history, cookies and cache are wiped, and Tor is asked to build a new circuit for future streams. The exit IP may stay the same; this is not a fingerprint reset.")
        ident_note.setWordWrap(True)
        ident_note.setStyleSheet(f"color: {MUTED}; font-size: 9pt;")
        iv.addWidget(ident_note)
        outer.addWidget(ident)

        # ---- Tor service ports probe (loopback only) ----
        ports = QGroupBox("Tor service ports (loopback probe)")
        pv = QVBoxLayout(ports)
        self.probe_btn = QPushButton("Probe SOCKS 9050 / control 9051")
        self.probe_btn.clicked.connect(self._probe_ports)
        pv.addWidget(self.probe_btn)
        self.ports_lbl = QLabel("Not probed yet.")
        self.ports_lbl.setWordWrap(True)
        self.ports_lbl.setStyleSheet(f"color: {MUTED}; font-size: 9pt;")
        pv.addWidget(self.ports_lbl)
        outer.addWidget(ports)

        # ---- Exit country quick control ----
        exitg = QGroupBox("Exit country (live)")
        ev = QVBoxLayout(exitg)
        erow = QHBoxLayout()
        self.exit_combo = QComboBox()
        self.exit_combo.addItem("Auto (any country)", "--")
        for code, name in EXIT_COUNTRIES:
            self.exit_combo.addItem(f"{name}  [{code.upper()}]", code)
        erow.addWidget(self.exit_combo, 1)
        self.exit_apply = QPushButton("Apply now")
        self.exit_apply.clicked.connect(self._apply_exit_country)
        erow.addWidget(self.exit_apply)
        ev.addLayout(erow)
        self.exit_note = QLabel("Applying a country needs an authenticated Tor control port (Settings page stores the default).")
        self.exit_note.setWordWrap(True)
        self.exit_note.setStyleSheet(f"color: {MUTED}; font-size: 9pt;")
        ev.addWidget(self.exit_note)
        outer.addWidget(exitg)

        # ---- Clipboard wipe ----
        clip = QGroupBox("Clipboard")
        clv = QVBoxLayout(clip)
        clip_btn = QPushButton("Wipe clipboard contents")
        clip_btn.clicked.connect(self._wipe_clipboard)
        clv.addWidget(clip_btn)
        clip_note = QLabel("Clears this desktop session's clipboard, so anything copied earlier (passwords, links, text) cannot be pasted later by mistake.")
        clip_note.setWordWrap(True)
        clip_note.setStyleSheet(f"color: {MUTED}; font-size: 9pt;")
        clv.addWidget(clip_note)
        outer.addWidget(clip)

        outer.addStretch(1)

    # ---- Actions ----
    def _clear_browser(self):
        browser = self.main_win.browse_tab
        if not browser.clear_session_data():
            QMessageBox.warning(self, "Clear failed", "The private browser profile is not available.")
            return
        QMessageBox.information(self, "Browser session cleared", "This app's current page, cookies and memory cache were cleared.")

    def _new_identity(self):
        browser = self.main_win.browse_tab
        wiped = browser.clear_session_data() if browser.web_view else False
        if not self.tor.connected:
            QMessageBox.warning(
                self, "Tor Not Connected",
                "Browser session "
                + ("wiped" if wiped else "not available")
                + ", but a new Tor circuit needs a connected session. Connect to Tor first.")
            return
        self.main_win.tor_panel.new_circuit()
        QMessageBox.information(
            self, "New Identity Requested",
            "Browser session "
            + ("wiped" if wiped else "unavailable (engine not installed)")
            + " and Tor was asked to build a new circuit for future streams.\n\n"
            "The same exit IP may be selected; this is not a fingerprint reset.")

    def _probe_ports(self):
        results = []
        for label, port in (("SOCKS (127.0.0.1:9050)", 9050),
                            ("Control (127.0.0.1:9051)", 9051)):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1.5):
                    results.append(f"{label}: OPEN")
            except OSError:
                results.append(f"{label}: closed / no service")
        text = " · ".join(results)
        open_count = text.count("OPEN")
        self.ports_lbl.setText(text + (
            "  — local probe only; nothing was sent to the internet."
            if open_count else
            "  — if both are closed, your Linux Tor service is not running (Terminal: systemctl status tor@default)."))
        self.ports_lbl.setStyleSheet(
            f"color: {GREEN_OK if open_count else AMBER}; font-size: 9pt; font-weight: 600;")

    def _apply_exit_country(self):
        if not self.tor.connected:
            QMessageBox.warning(self, "Tor Not Connected",
                                "Connect to Tor first; the preference cannot be applied live.")
            return
        code = self.exit_combo.currentData() or "--"
        ok, detail = self.tor.set_exit_country(code)
        if not ok:
            QMessageBox.warning(
                self, "Exit Country Not Applied",
                f"Tor rejected the live setting:\n{detail}\n\n"
                "This needs an authenticated Tor control port (run sudo bash install.sh on a SOCKS-only service).")
            return
        self.main_win.tor_panel.new_circuit()
        self.tor.exit_country = code
        QMessageBox.information(
            self, "Exit Country Applied",
            ("Tor will prefer the selected country for new circuits"
             if code != "--" else "Tor returned to automatic exit selection")
            + "; a new circuit was requested.")

    def _wipe_clipboard(self):
        QApplication.clipboard().clear()
        QMessageBox.information(self, "Clipboard wiped",
                                "The clipboard is now empty.")

    def refresh(self):
        if self.tor.connected:
            mode = "SOCKS-only" if self.tor.socks_only else "control-port managed"
            self.tor_state.setText(f"Tor app session: CONNECTED ({mode})")
            self.tor_state.setStyleSheet(f"color: {GREEN_OK}; font-weight: 700; padding: 5px;")
        else:
            self.tor_state.setText("Tor app session: DISCONNECTED")
            self.tor_state.setStyleSheet(f"color: {RED_HARD}; font-weight: 700; padding: 5px;")

        browser = self.main_win.browse_tab
        profile = getattr(browser, "_profile", None)
        gate = getattr(browser, "_connection_gate", None)
        if profile is not None:
            self.browser_state.setText("Browser storage: off-the-record profile; memory cache; non-persistent cookies")
            self.browser_state.setStyleSheet(f"color: {GREEN_OK}; padding: 5px;")
        else:
            self.browser_state.setText("Browser storage: WebEngine profile unavailable")
            self.browser_state.setStyleSheet(f"color: {AMBER}; padding: 5px;")
        self.gate_state.setText("Browser request gate: installed" if gate else "Browser request gate: unavailable")
        self.gate_state.setStyleSheet(f"color: {GREEN_OK if gate else AMBER}; padding: 5px;")
