"""Network monitor for measured Tor-daemon counters and live circuit metadata."""
import threading
import time
from datetime import datetime
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QPointF
from PyQt5.QtGui import QFont, QPainter, QPen, QColor
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QGridLayout, QPlainTextEdit

from gui.theme import CREAM_LIGHT, CREAM_DARK, DARK_TEXT, MUTED, PURPLE, PURPLE_DARK, GREEN_OK, AMBER, RED_OFF, TEAL, TAN_DARK
from gui.scroll_wrap import wrap_in_scroll


class _RateChart(QWidget):
    """Light chart of real receive/send rate intervals in KiB/s."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.samples = []
        self.setMinimumHeight(220)

    def push(self, received, sent):
        self.samples.append((max(0.0, received), max(0.0, sent)))
        self.samples = self.samples[-60:]
        self.update()

    def clear(self):
        self.samples.clear()
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#FFFFFF"))
        w, h = self.width(), self.height()
        left, right, top, bottom = 46, w - 12, 14, h - 26
        p.setPen(QPen(QColor("#D8D8DD"), 1, Qt.DotLine))
        for i in range(5):
            y = top + (bottom - top) * i / 4
            p.drawLine(left, int(y), right, int(y))
        maxv = max([v for pair in self.samples for v in pair] + [1.0])
        p.setFont(QFont("Sans", 8))
        p.setPen(QColor("#111111"))
        p.drawText(4, top + 4, f"{maxv:.1f}")
        p.drawText(4, bottom, "0")
        if len(self.samples) > 1:
            for series, color in ((0, GREEN_OK), (1, "#E01414")):
                p.setPen(QPen(QColor(color), 2))
                points = []
                for i, pair in enumerate(self.samples):
                    x = left + (right - left) * i / (len(self.samples) - 1)
                    y = bottom - (bottom - top) * min(pair[series] / maxv, 1.0)
                    points.append(QPointF(x, y))
                for a, b in zip(points, points[1:]):
                    p.drawLine(a, b)
        elif not self.samples:
            p.setPen(QColor("#111111"))
            p.drawText(left + 12, (top + bottom) // 2, "Waiting for real counter samples")
        p.setPen(QColor("#111111"))
        p.drawText(left, h - 5, "Recent measured samples · KiB/s")
        p.end()


class NetworkMonitorTab(QWidget):
    """Live, source-labelled Tor network counters and circuit path."""
    sampleReady = pyqtSignal(dict)
    circuitDone = pyqtSignal()
    activityEvent = pyqtSignal(str)

    def __init__(self, main_win):
        super().__init__()
        self.main_win = main_win
        self.tor = main_win.tor
        self._worker_lock = threading.Lock()
        self._previous = None
        self._previous_at = None
        self._source = None
        self._build()
        self.sampleReady.connect(self._apply_sample, Qt.QueuedConnection)
        self.activityEvent.connect(self._append_activity, Qt.QueuedConnection)
        self.tor.add_listener(self._on_activity)
        self.circuitDone.connect(lambda: self.refresh_btn.setEnabled(True), Qt.QueuedConnection)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.sample)
        self.timer.start(2000)
        self.sample()

    def _build(self):
        # The stat-card row clipped its right side at the 1024 px minimum
        # window width; the page now scrolls instead of cutting boxes.
        content = wrap_in_scroll(self)
        outer = QVBoxLayout(content)
        outer.setContentsMargins(22, 20, 22, 20)
        outer.setSpacing(12)
        title = QLabel("Network Monitor")
        title.setFont(QFont("Sans", 18, QFont.Bold))
        title.setStyleSheet(f"color: {TEAL};")
        outer.addWidget(title)
        self.scope = QLabel("Waiting for a verified Tor session.")
        self.scope.setWordWrap(True)
        self.scope.setStyleSheet(f"color: {MUTED}; background: {CREAM_DARK}; padding: 9px 12px;")
        outer.addWidget(self.scope)

        row = QHBoxLayout()
        self.rx = self._stat_card("Received", "-- KiB/s", GREEN_OK)
        self.tx = self._stat_card("Sent", "-- KiB/s", "#F87171")
        self.total = self._stat_card("Source totals", "--", PURPLE_DARK)
        self.mode = self._stat_card("Data source", "Offline", MUTED)
        for card in (self.rx[0], self.tx[0], self.total[0], self.mode[0]):
            row.addWidget(card, 1)
        outer.addLayout(row)

        chart_frame = QFrame()
        chart_frame.setStyleSheet(f"background: #FFFFFF; color: #111111; border: 1px solid {TAN_DARK}; border-radius: 6px;")
        cv = QVBoxLayout(chart_frame)
        heading = QHBoxLayout()
        heading.addWidget(QLabel("Measured transfer rates · source shown above"))
        heading.addStretch()
        self.chart_key = QLabel(
            f"<span style='color:{GREEN_OK};'>●</span> Download"
            f"&nbsp;&nbsp;&nbsp;&nbsp;<span style='color:#E01414;'>●</span> Upload")
        self.chart_key.setTextFormat(Qt.RichText)
        self.chart_key.setStyleSheet(f"color: {MUTED};")
        heading.addWidget(self.chart_key)
        cv.addLayout(heading)
        self.chart = _RateChart()
        cv.addWidget(self.chart)
        outer.addWidget(chart_frame, 1)

        path_header = QHBoxLayout()
        path_header.addWidget(QLabel("Current circuit snapshot"))
        path_header.addStretch()
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._refresh_circuit)
        path_header.addWidget(self.refresh_btn)
        outer.addLayout(path_header)
        self.path_box = QPlainTextEdit()
        self.path_box.setReadOnly(True)
        self.path_box.setMaximumBlockCount(80)
        self.path_box.setStyleSheet(f"background: {CREAM_LIGHT}; color: {DARK_TEXT}; border: 1px solid {TAN_DARK}; padding: 6px;")
        outer.addWidget(self.path_box, 1)
        events_title = QLabel("Live Tor events")
        events_title.setStyleSheet(f"color: {DARK_TEXT}; font-weight: 600;")
        outer.addWidget(events_title)
        self.activity_log = QPlainTextEdit()
        self.activity_log.setReadOnly(True)
        self.activity_log.setMaximumBlockCount(300)
        self.activity_log.setMaximumHeight(150)
        self.activity_log.setStyleSheet(f"background: {CREAM_LIGHT}; color: {DARK_TEXT}; border: 1px solid {TAN_DARK}; padding: 6px;")
        outer.addWidget(self.activity_log)
        note = QLabel("With a control port, rates come from the Tor daemon and include its Tor traffic (not the whole computer). SOCKS-only mode cannot expose daemon counters or the circuit path; this page will not invent them.")
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {MUTED}; padding: 6px;")
        outer.addWidget(note)

    def _stat_card(self, title, value, color):
        frame = QFrame()
        frame.setStyleSheet(f"background: {CREAM_LIGHT}; border: 1px solid {TAN_DARK}; border-radius: 5px;")
        layout = QVBoxLayout(frame)
        name = QLabel(title)
        name.setStyleSheet(f"color: {MUTED}; border: none;")
        val = QLabel(value)
        val.setFont(QFont("Sans", 13, QFont.Bold))
        val.setStyleSheet(f"color: {color}; border: none;")
        layout.addWidget(name)
        layout.addWidget(val)
        return frame, val

    def _on_activity(self, level, message):
        self.activityEvent.emit(f"[{datetime.now().strftime('%H:%M:%S')}] {level}: {message}")

    def _append_activity(self, line):
        self.activity_log.appendPlainText(str(line))

    def sample(self):
        if not self._worker_lock.acquire(False):
            return
        def work():
            try:
                data = self.tor.daemon_traffic_stats()
                self.sampleReady.emit(data)
            except Exception as exc:
                self.sampleReady.emit({"available": False, "source": "error", "error": str(exc)})
            finally:
                self._worker_lock.release()
        threading.Thread(target=work, daemon=True).start()

    @staticmethod
    def _format_bytes(value):
        value = max(0, int(value))
        units = ("B", "KiB", "MiB", "GiB", "TiB")
        amount = float(value)
        for unit in units:
            if amount < 1024 or unit == units[-1]:
                return f"{amount:.1f} {unit}"
            amount /= 1024

    def _apply_sample(self, data):
        source = data.get("source", "offline")
        available = bool(data.get("available"))
        if not available:
            self._source = None
            self._previous = None
            self._previous_at = None
            detail = data.get("error")
            self.scope.setText(
                f"Live counters unavailable: {detail}" if detail else
                "Offline or disconnected. Connect to Tor before monitoring live counters.")
            self.rx[1].setText("-- KiB/s")
            self.tx[1].setText("-- KiB/s")
            self.total[1].setText("--")
            self.mode[1].setText("Offline")
            self.path_box.setPlainText("No live circuit snapshot.")
            self.chart.clear()
            return

        received = int(data.get("bytes_received", 0) or 0)
        sent = int(data.get("bytes_sent", 0) or 0)
        now = time.monotonic()
        has_rate = self._source == source and self._previous is not None and self._previous_at is not None
        if has_rate and (received < self._previous[0] or sent < self._previous[1]):
            has_rate = False
            self.chart.clear()
        if has_rate:
            elapsed = max(0.1, now - self._previous_at)
            rx_rate = max(0, received - self._previous[0]) / elapsed / 1024
            tx_rate = max(0, sent - self._previous[1]) / elapsed / 1024
        else:
            rx_rate = tx_rate = None
        self._source = source
        self._previous = (received, sent)
        self._previous_at = now

        if source == "tor-daemon":
            self.scope.setText("Live Tor daemon counters. Rates are sampled by this page; cumulative totals may include traffic since the Tor process started and are not a per-app or whole-system breakdown.")
            self.mode[1].setText("Tor daemon")
        else:
            if self.tor.socks_only:
                reason = "SOCKS-only Tor detected; no control-port counters are available."
            else:
                reason = "The control port did not provide traffic counters."
            self.scope.setText(f"{reason} Only this app's Python-request counters are visible; Chromium browser traffic and total Tor rates are unavailable. App counters are cumulative for this app process.")
            self.mode[1].setText("App-only")

        if has_rate:
            self.rx[1].setText(f"{rx_rate:.1f} KiB/s")
            self.tx[1].setText(f"{tx_rate:.1f} KiB/s")
            self.chart.push(rx_rate, tx_rate)
        else:
            self.rx[1].setText("Sampling…")
            self.tx[1].setText("Sampling…")
            self.chart.clear()
        self.total[1].setText(f"↓ {self._format_bytes(received)}  ↑ {self._format_bytes(sent)}")

        circuit = self.tor.current_circuit
        if not circuit:
            self.path_box.setPlainText("No live relay path is available. Load a page through Tor and refresh; a control port is required.")
        else:
            lines = [f"Circuit #{circuit.get('id', '?')} · {'active stream' if circuit.get('active_stream') else 'built general-purpose circuit'}"]
            for index, node in enumerate(circuit.get("nodes", []), 1):
                fp = str(node.get("fingerprint") or "")
                lines.append(f"{index}. {node.get('position', 'Relay')} — {node.get('nickname', 'Unnamed')} — {str(node.get('country') or '??').upper()} — {node.get('city') or 'location unavailable'} — {fp}")
            target = circuit.get("stream_target")
            if target:
                lines.append(f"Active Tor-reported target: {target.get('display')} · {target.get('status')}")
                location = target.get("location") or {}
                if location.get("via_tor"):
                    lines.append(f"Destination GeoIP estimate: {location.get('city')}, {location.get('country')} ({location.get('ip')})")
                else:
                    lines.append("Destination geolocation: off or unavailable; hostname and port are from Tor STREAM data.")
            else:
                lines.append("Active Tor stream destination: unavailable (no associated active stream reported).")
            self.path_box.setPlainText("\n".join(lines))

    def _refresh_circuit(self):
        if not self.tor.connected or not self.tor.controller:
            self.path_box.setPlainText("A live circuit snapshot requires an authenticated Tor control port.")
            return
        self.refresh_btn.setEnabled(False)
        def work():
            try:
                self.tor.refresh_circuit()
            finally:
                try:
                    self.sampleReady.emit(self.tor.daemon_traffic_stats())
                finally:
                    self.circuitDone.emit()
        threading.Thread(target=work, daemon=True).start()

    def refresh(self):
        self.sample()
        if self.tor.connected and self.tor.controller:
            self._refresh_circuit()
