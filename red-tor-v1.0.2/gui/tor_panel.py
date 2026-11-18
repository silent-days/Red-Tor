"""Red Tor - Left panel: Tor status, circuit, path controls, map, activity log."""
import os
import threading
import time

from PyQt5.QtCore import Qt, QTimer, QSize, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap, QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QGroupBox, QComboBox, QMessageBox, QFrame, QSizePolicy, QToolButton,
    QSplitter, QScrollArea,
)

from gui.theme import (
    CREAM, CREAM_LIGHT, CREAM_DARK, TAN, TAN_DARK, DARK_TEXT, MUTED,
    PURPLE, PURPLE_DARK, PURPLE_LIGHT, PURPLE_PALE,
    GREEN_OK, AMBER, RED_OFF, TEAL, RED_HARD,
)
from tor_core import (
    TorManager, EXIT_COUNTRIES,
    load_settings, save_settings,
)
from .circuit_view import CircuitView
from .world_map import WorldMapWidget
from .activity_log import ActivityLog
from .full_map_dialog import FullMapDialog
from .animations import SpinnerLabel, fade_in_widget


def _load_icon(name):
    """Load an icon by name from assets/icons."""
    from gui import ASSETS, ICONS
    p = os.path.join(ICONS, name)
    return QIcon(p) if os.path.exists(p) else QIcon()


class TrafficStatsBar(QWidget):
    """Compact bar showing traffic + circuit stats."""

    def __init__(self, tor: TorManager, parent=None):
        super().__init__(parent)
        self.tor = tor
        self._build()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1500)

    def _build(self):
        h = QHBoxLayout(self)
        h.setContentsMargins(8, 4, 8, 4)
        h.setSpacing(12)
        self.lbl_sent = QLabel("Tracked sent: 0 B")
        self.lbl_recv = QLabel("Tracked received: 0 B")
        self.lbl_req  = QLabel("Tracked requests: 0")
        self.lbl_circ = QLabel("Circuits: 0")
        for lbl in [self.lbl_sent, self.lbl_recv, self.lbl_req, self.lbl_circ]:
            lbl.setFont(QFont("Sans", 9))
            lbl.setStyleSheet(f"color: {DARK_TEXT};")
        h.addWidget(self.lbl_sent)
        h.addWidget(self.lbl_recv)
        h.addWidget(self.lbl_req)
        h.addWidget(self.lbl_circ)
        h.addStretch()

    def refresh(self):
        s = self.tor.traffic_stats()
        self.lbl_sent.setText(f"Tracked sent: {self._fmt_bytes(s['bytes_sent'])}")
        self.lbl_recv.setText(f"Tracked received: {self._fmt_bytes(s['bytes_received'])}")
        self.lbl_req.setText(f"Tracked requests: {s['requests']}")
        self.lbl_circ.setText(f"Circuits: {s['circuits']}")

    @staticmethod
    def _fmt_bytes(n):
        for unit in ["B", "KB", "MB", "GB"]:
            if n < 1024:
                return f"{n:.1f} {unit}"
            n /= 1024
        return f"{n:.1f} TB"


class TorPanel(QWidget):
    """Left panel - Tor status, circuit, path controls, map, activity log.
    Wrapped in a QScrollArea so all sections fit regardless of window height.
    """

    circuitUpdated = pyqtSignal(dict)
    # Thread-safe signals for cross-thread communication
    activityEvent = pyqtSignal(str, str)
    connectedEvent = pyqtSignal(bool, str, str)   # ok, msg, ip
    newCircuitEvent = pyqtSignal(dict)
    disconnectedEvent = pyqtSignal()

    def __init__(self, main_win):
        super().__init__()
        self.main_win = main_win
        self.tor: TorManager = main_win.tor
        self._circuit_retry_count = 0
        self._circuit_retry_limit = 5
        self._circuit_retry_timer = QTimer(self)
        self._circuit_retry_timer.setSingleShot(True)
        self._circuit_retry_timer.timeout.connect(self._retry_circuit)
        # No fixed width - this page fills the main content area
        self._build()
        # Connect signals (queued connection works across threads)
        self.activityEvent.connect(self._append_to_log, Qt.QueuedConnection)
        self.connectedEvent.connect(self._on_connected, Qt.QueuedConnection)
        self.newCircuitEvent.connect(self._on_new_circuit, Qt.QueuedConnection)
        self.disconnectedEvent.connect(self._on_disconnected, Qt.QueuedConnection)
        self.tor.add_listener(self._on_activity)


    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        # Keep the horizontal scrollbar reachable: clipping the map controls
        # on narrow windows was worse than a scrollbar.
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        outer.addWidget(scroll)

        inner = QWidget()
        # Fit the viewport: a fixed 900px minimum combined with a hidden
        # horizontal scrollbar clipped map controls on 1024px desktops.
        inner.setMinimumWidth(0)
        scroll.setWidget(inner)

        v = QVBoxLayout(inner)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(8)

        # --- Header ---
        header = QHBoxLayout()
        logo_lbl = QLabel()
        from gui import ASSETS
        logo_path = os.path.join(ASSETS, "logo.png")
        if os.path.exists(logo_path):
            pix = QPixmap(logo_path).scaled(56, 56, Qt.KeepAspectRatio,
                                            Qt.SmoothTransformation)
            logo_lbl.setPixmap(pix)
        title_box = QVBoxLayout()
        title = QLabel("Red Tor")
        title.setFont(QFont("Sans", 18, QFont.Bold))
        title.setStyleSheet(f"color: {TEAL};")
        subtitle = QLabel("Local Tor client · app traffic only")
        subtitle.setFont(QFont("Sans", 9))
        subtitle.setStyleSheet(f"color: {MUTED};")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addWidget(logo_lbl)
        header.addLayout(title_box)
        header.addStretch()
        v.addLayout(header)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine); sep.setFrameShadow(QFrame.Sunken)
        v.addWidget(sep)

        # --- Status ---
        status_grp = QGroupBox("Tor Status")
        sg = QGridLayout(status_grp)
        sg.setContentsMargins(10, 16, 10, 10)
        sg.setHorizontalSpacing(10); sg.setVerticalSpacing(6)

        self.status_icon = QLabel()
        self.status_icon.setPixmap(_load_icon("tor_off.png").pixmap(32, 32))
        self.status_text = QLabel("Disconnected")
        self.status_text.setFont(QFont("Sans", 12, QFont.Bold))
        self.status_text.setStyleSheet(f"color: {RED_OFF};")
        # Rotating spinner shown only while a connection attempt is running.
        self.spinner = SpinnerLabel(status_grp)
        self.spinner.hide()

        self.mode_lbl = QLabel("Mode: --")
        self.mode_lbl.setStyleSheet(f"color: {MUTED};")
        self.exit_ip_lbl = QLabel("Tor exit IP: not checked")
        self.exit_ip_lbl.setStyleSheet(f"color: {MUTED};")

        self.start_btn = QPushButton("  Start Tor")
        self.start_btn.setIcon(_load_icon("power.png"))
        self.start_btn.setIconSize(QSize(18, 18))
        self.start_btn.clicked.connect(self.start_tor)

        self.stop_btn = QPushButton("  Stop")
        self.stop_btn.setIcon(_load_icon("tor_off.png"))
        self.stop_btn.setIconSize(QSize(18, 18))
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_tor)

        self.disconnect_btn = QPushButton("  Disconnect this app from Tor")
        self.disconnect_btn.setIcon(_load_icon("power.png"))
        self.disconnect_btn.setIconSize(QSize(18, 18))
        self.disconnect_btn.setToolTip("Disconnect this app from Tor. Other applications are unaffected.")
        self.disconnect_btn.setStyleSheet(
            f"background: {PURPLE_PALE}; color: #111111; border: 1px solid {RED_OFF}; "
            f"font-weight: 700; border-radius: 3px;")
        self.disconnect_btn.clicked.connect(self.main_win._disconnect_app)

        sg.addWidget(self.status_icon, 0, 0)
        sg.addWidget(self.status_text, 0, 1)
        sg.addWidget(self.spinner, 0, 2)
        sg.addWidget(self.mode_lbl, 1, 0, 1, 2)
        sg.addWidget(self.exit_ip_lbl, 2, 0, 1, 2)
        sg.addWidget(self.start_btn, 3, 0)
        sg.addWidget(self.stop_btn, 3, 1)
        sg.addWidget(self.disconnect_btn, 4, 0, 1, 2)
        v.addWidget(status_grp)

        # --- Circuit ---
        circ_grp = QGroupBox("Current Circuit Path")
        cg = QVBoxLayout(circ_grp)
        cg.setContentsMargins(6, 16, 6, 6)
        self.circuit_view = CircuitView()
        self.circuit_view.setMinimumHeight(280)
        cg.addWidget(self.circuit_view)
        cc = QHBoxLayout()
        self.new_circ_btn = QPushButton("  New Circuit")
        self.new_circ_btn.setIcon(_load_icon("new_circuit.png"))
        self.new_circ_btn.setIconSize(QSize(18, 18))
        self.new_circ_btn.setEnabled(False)
        self.new_circ_btn.clicked.connect(self.new_circuit)
        self.new_circ_btn.setToolTip("Request NEWNYM; a new exit IP is not guaranteed")
        self.refresh_btn = QPushButton("  Refresh")
        self.refresh_btn.setIcon(_load_icon("path.png"))
        self.refresh_btn.setIconSize(QSize(18, 18))
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.clicked.connect(self.refresh_circuit_async)
        cc.addWidget(self.new_circ_btn)
        cc.addWidget(self.refresh_btn)
        cg.addLayout(cc)
        v.addWidget(circ_grp)

        # --- Path selection ---
        path_grp = QGroupBox("Path Selection")
        pg = QGridLayout(path_grp)
        pg.setContentsMargins(10, 16, 10, 10)
        pg.setHorizontalSpacing(10); pg.setVerticalSpacing(8)
        pg.addWidget(QLabel("Exit Country:"), 0, 0)
        self.exit_combo = QComboBox()
        for code, name in EXIT_COUNTRIES:
            self.exit_combo.addItem(f"{name}  [{code.upper()}]", code)
        saved_index = self.exit_combo.findData(self.tor.exit_country)
        if saved_index >= 0:
            self.exit_combo.setCurrentIndex(saved_index)
        pg.addWidget(self.exit_combo, 0, 1)
        self.apply_btn = QPushButton("  Apply Path Settings")
        self.apply_btn.setIcon(_load_icon("shield.png"))
        self.apply_btn.setIconSize(QSize(18, 18))
        self.apply_btn.clicked.connect(self.apply_path_settings)
        pg.addWidget(self.apply_btn, 1, 0, 1, 2)
        v.addWidget(path_grp)

        # --- Map ---
        map_grp = QGroupBox("Live Tor Relay Map")
        mg = QVBoxLayout(map_grp)
        mg.setContentsMargins(4, 16, 4, 4)

        # Header with expand button
        map_header = QHBoxLayout()
        map_hint = QLabel("Tor Metrics lookup via Tor · approximate GeoIP · toggle in Settings")
        map_hint.setStyleSheet(f"color: {MUTED}; font-size: 8pt; font-style: italic;")
        map_header.addWidget(map_hint)
        map_header.addStretch()
        self.expand_map_btn = QPushButton("  Expand")
        self.expand_map_btn.setIcon(_load_icon("globe.png"))
        self.expand_map_btn.setIconSize(QSize(14, 14))
        self.expand_map_btn.setToolTip("Open full-screen world map")
        self.expand_map_btn.setStyleSheet(
            f"padding: 3px 10px; font-size: 9pt; min-width: 0;")
        self.expand_map_btn.clicked.connect(self._show_full_map)
        map_header.addWidget(self.expand_map_btn)
        mg.addLayout(map_header)

        self.map_widget = WorldMapWidget()
        self.map_widget.setMinimumHeight(220)
        # Make the map widget clickable
        self.map_widget.mousePressEvent = self._on_map_click
        mg.addWidget(self.map_widget)
        v.addWidget(map_grp)

        # --- Traffic stats ---
        traffic_grp = QGroupBox("Traffic Statistics")
        tg = QVBoxLayout(traffic_grp)
        tg.setContentsMargins(4, 16, 4, 4)
        self.traffic_bar = TrafficStatsBar(self.tor)
        tg.addWidget(self.traffic_bar)
        v.addWidget(traffic_grp)

        # --- Activity log ---
        log_grp = QGroupBox("Activity Log")
        lg = QVBoxLayout(log_grp)
        lg.setContentsMargins(4, 16, 4, 4)
        self.log_widget = ActivityLog()
        self.log_widget.setMinimumHeight(180)
        lg.addWidget(self.log_widget)
        v.addWidget(log_grp, 1)

        v.addStretch()

    # ---- Activity listener (called from worker thread) ----
    def _on_activity(self, level: str, message: str):
        # Emit signal - Qt will queue it to the main thread safely
        self.activityEvent.emit(level, message)

    def _append_to_log(self, level: str, message: str):
        # Runs on main thread via QueuedConnection
        self.log_widget.append(level, message)

    # ---- Actions ----
    def start_tor(self):
        self.start_btn.setEnabled(False)
        self.start_btn.setText("  Connecting...")
        # 3D feedback: spinner next to the status, pulsing header light goes
        # amber while the connection attempt runs in its worker thread.
        self.status_text.setText("Connecting...")
        self.status_text.setStyleSheet(f"color: {AMBER};")
        self.spinner.start()
        self.main_win.set_conn_state("busy")
        from PyQt5.QtWidgets import QApplication
        QApplication.processEvents()

        def work():
            try:
                ok, msg = self.tor.connect()
                ip = (self.tor.get_my_ip_via_tor() or "") if ok and self.tor.auto_check_exit_ip else ""
                if ok and self.tor.auto_check_exit_ip and not ip and self.tor.last_ip_check_error:
                    msg += f" Exit-IP verification failed: {self.tor.last_ip_check_error}"
                # Use thread-safe signal instead of QTimer.singleShot
                self.connectedEvent.emit(ok, msg, ip)
            except Exception as e:
                self.connectedEvent.emit(False, f"Internal error: {e}", "")

        threading.Thread(target=work, daemon=True).start()

    def _on_connected(self, ok, msg, ip):
        self.spinner.stop()
        self.main_win.set_conn_state("ok" if ok else "off")
        if ok:
            self._circuit_retry_count = 0
            self.status_icon.setPixmap(_load_icon("tor_on.png").pixmap(32, 32))
            mode = "SOCKS ONLY" if self.tor.socks_only else "CONTROL PORT"
            self.status_text.setText("Connected (SOCKS only)" if self.tor.socks_only else "Connected")
            self.status_text.setStyleSheet(f"color: {GREEN_OK};")
            self.mode_lbl.setText(f"Mode: {mode}")
            self.mode_lbl.setToolTip(
                "Exit-IP verification works, but circuit controls require ControlPort 9051. "
                "Run sudo bash install.sh and log out/in to enable it automatically."
                if self.tor.socks_only else "Authenticated Tor control port is available.")
            ip_status = ip or ("not verified" if self.tor.auto_check_exit_ip else "not checked")
            self.exit_ip_lbl.setText(f"Tor exit IP: {ip_status}")
            self.start_btn.setEnabled(False)
            self.start_btn.setText("  Start Tor")
            self.stop_btn.setEnabled(True)
            self.new_circ_btn.setEnabled(self.tor.controller is not None)
            self.refresh_btn.setEnabled(self.tor.controller is not None)
            self.refresh_view()
            # connect() may have checked the exit IP and thereby opened the
            # first Tor stream after its initial circuit snapshot. Read again
            # now so the current active relay path is not left blank/stale.
            if self.tor.controller is not None:
                self._circuit_retry_timer.start(100)
            self.main_win.status_bar.showMessage(msg, 5000)
        else:
            self._circuit_retry_timer.stop()
            self._circuit_retry_count = self._circuit_retry_limit
            self.status_icon.setPixmap(_load_icon("tor_off.png").pixmap(32, 32))
            self.status_text.setText("Disconnected")
            self.status_text.setStyleSheet(f"color: {RED_OFF};")
            self.mode_lbl.setText("Mode: --")
            self.exit_ip_lbl.setText("Tor exit IP: not verified")
            self.start_btn.setEnabled(True)
            self.start_btn.setText("  Start Tor")
            self.stop_btn.setEnabled(False)
            self.new_circ_btn.setEnabled(False)
            self.refresh_btn.setEnabled(False)
            self.refresh_view()
            QMessageBox.warning(self, "Connection Failed", msg)

    def stop_tor(self):
        self._circuit_retry_timer.stop()
        self._circuit_retry_count = self._circuit_retry_limit
        self.spinner.stop()
        self.main_win.set_conn_state("off")
        # Flip the manager state first so every page immediately shows
        # "disconnected", then close the control socket and stop any owned
        # Tor process in the background: terminating a slow Tor process must
        # not freeze the interface.
        self.tor.mark_disconnected()
        self.status_icon.setPixmap(_load_icon("tor_off.png").pixmap(32, 32))
        self.status_text.setText("Disconnected")
        self.status_text.setStyleSheet(f"color: {RED_OFF};")
        self.mode_lbl.setText("Mode: --")
        self.exit_ip_lbl.setText("Tor exit IP: not checked")
        self.start_btn.setEnabled(False)
        self.start_btn.setText("  Start Tor")
        self.stop_btn.setEnabled(False)
        self.new_circ_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        self.refresh_view()

        def work():
            try:
                self.tor.disconnect()
            except Exception:
                pass
            finally:
                self.disconnectedEvent.emit()

        threading.Thread(target=work, daemon=True).start()
        self.main_win.status_bar.showMessage("Tor stopped.", 3000)

    def _on_disconnected(self):
        # Background disconnect finished; allow a fresh Start attempt.
        self.start_btn.setEnabled(True)

    def shutdown(self):
        """Stop background timers before the window closes."""
        self._circuit_retry_timer.stop()
        self.spinner.stop()

    def new_circuit(self):
        if not self.tor.connected:
            return
        if not self.tor.controller:
            self.main_win.status_bar.showMessage(
                "Circuit rotation needs Tor control-port access.", 5000)
            return
        self.new_circ_btn.setEnabled(False)
        self.new_circ_btn.setText("  Building...")

        def work():
            try:
                circ = self.tor.new_circuit()
                self.newCircuitEvent.emit(circ or {})
            except Exception as e:
                # On error, re-enable button
                self.newCircuitEvent.emit({})

        threading.Thread(target=work, daemon=True).start()

    def refresh_circuit_async(self, retry=False):
        """Read the currently built general circuit without rotating it."""
        if not self.tor.connected or not self.tor.controller:
            self.main_win.status_bar.showMessage(
                "A live circuit path needs an authenticated Tor control port.", 5000)
            return
        if not retry:
            self._circuit_retry_timer.stop()
            self._circuit_retry_count = 0
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("  Reading...")

        def work():
            try:
                circuit = self.tor.refresh_circuit()
                self.newCircuitEvent.emit(circuit or {})
            except Exception:
                self.newCircuitEvent.emit({})
        threading.Thread(target=work, daemon=True).start()

    def _on_new_circuit(self, circ):
        self.new_circ_btn.setEnabled(self.tor.controller is not None)
        self.new_circ_btn.setText("  New Circuit")
        self.refresh_btn.setEnabled(self.tor.controller is not None)
        self.refresh_btn.setText("  Refresh")
        self.refresh_view()
        if circ and circ.get("id"):
            # Lift-and-fade the path card so a rebuilt circuit reads as new.
            fade_in_widget(self.circuit_view, ms=200, lift=8)
            self._circuit_retry_timer.stop()
            self._circuit_retry_count = 0
            self.main_win.status_bar.showMessage(
                f"Circuit view updated: #{circ.get('id')}", 4000)
        elif (self.tor.connected and self.tor.controller
              and self._circuit_retry_count < self._circuit_retry_limit):
            self._circuit_retry_count += 1
            attempt = self._circuit_retry_count
            self.main_win.status_bar.showMessage(
                f"Tor is still building a circuit; checking again ({attempt}/{self._circuit_retry_limit}).", 3500)
            self._circuit_retry_timer.start(2000)
        else:
            self.main_win.status_bar.showMessage(
                "No circuit details were returned.", 4000)

    def _retry_circuit(self):
        self.refresh_circuit_async(retry=True)

    def refresh_view(self):
        circ = self.tor.current_circuit
        reason = self._circuit_unavailable_reason() if not circ else None
        self.circuit_view.set_circuit(circ, reason)
        dest = self._destination_for_map(circ)
        self.circuit_view.set_destination(dest)
        self.map_widget.show_circuit_and_destination(circ, dest, reason)
        self.circuitUpdated.emit(circ or {})

    @staticmethod
    def _destination_for_map(circuit):
        target = (circuit or {}).get("stream_target")
        if target:
            location = target.get("location") or {}
            return {**location, "host": target.get("host"),
                    "port": target.get("port"), "display": target.get("display"),
                    "status": target.get("status"), "source": "active-stream"}
        return None

    def _circuit_unavailable_reason(self):
        if self.tor.socks_only:
            return ("Tor is connected in SOCKS-only mode: the exit verifies, but the "
                    "relay path needs an authenticated control port. The installer "
                    "enables it automatically — run: sudo bash install.sh (then log "
                    "out and back in so cookie-group permissions apply).")
        if not self.tor.connected:
            return "Not connected to Tor. Connect first, then open a page through the Tor browser."
        if self.tor.controller is None:
            return "Tor is connected, but circuit details require authenticated control-port access."
        return "Tor has not reported a built general-purpose circuit yet. Open a Tor-routed page; the app will retry briefly."

    def apply_path_settings(self):
        exit_code = self.exit_combo.currentData()
        ok, msg = self.tor.set_exit_country(exit_code)
        if ok:
            settings = load_settings()
            settings["default_exit"] = exit_code
            try:
                save_settings(settings)
            except Exception as exc:
                QMessageBox.warning(self, "Preference Save Failed", str(exc))
            settings_tab = getattr(self.main_win, "settings_tab", None)
            if settings_tab is not None:
                saved_index = settings_tab.default_exit.findData(exit_code)
                if saved_index >= 0:
                    settings_tab.default_exit.setCurrentIndex(saved_index)
            QMessageBox.information(
                self, "Path Preference Applied",
                f"Exit country: {exit_code.upper()}\n{msg}\nA new circuit will be requested.")
            self.new_circuit()
        else:
            QMessageBox.warning(
                self, "Path Preference Not Applied",
                f"Exit country: {exit_code.upper()}\n{msg}")

    # ---- Full map dialog ----
    def _show_full_map(self):
        """Open a full-screen world map dialog."""
        dialog = FullMapDialog(
            self,
            circuit=self.tor.current_circuit,
            destination=self._destination_for_map(self.tor.current_circuit),
            unavailable_reason=(self._circuit_unavailable_reason()
                                if not self.tor.current_circuit
                                else None),
        )
        dialog.exec_()

    def _on_map_click(self, event):
        """Left click on the small map opens the full map dialog."""
        if getattr(event, "button", None) is not None and event.button() == Qt.LeftButton:
            self._show_full_map()
