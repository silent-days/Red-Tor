"""Accurate, compact visualization of a live Tor circuit's relay hops."""
from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QPainter, QPen, QColor, QFont, QPainterPath, QBrush
from PyQt5.QtWidgets import QWidget, QSizePolicy

from gui.theme import (
    CREAM_LIGHT, CREAM_DARK, TAN_DARK, DARK_TEXT, MUTED,
    PURPLE, PURPLE_DARK, PURPLE_LIGHT, GREEN_OK, AMBER,
)


class CircuitView(QWidget):
    """Draw only the relay path returned by Tor's live control port."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(250)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.circuit = None
        self.unavailable_reason = None
        self.destination = None

    def set_circuit(self, circuit, unavailable_reason=None):
        self.circuit = circuit
        self.unavailable_reason = unavailable_reason
        self.update()

    def set_destination(self, dest):
        # Destination is an outbound stream target, not an extra Tor relay hop.
        self.destination = dest
        self.update()

    def _message(self, painter, text, color=MUTED):
        painter.setPen(QColor(color))
        painter.setFont(QFont("Sans", 10))
        painter.drawText(self.rect().adjusted(24, 34, -24, -20),
                         Qt.AlignCenter | Qt.TextWordWrap, text)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(CREAM_LIGHT))
        p.setPen(QPen(QColor(TAN_DARK), 1))
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))

        header = self.rect().adjusted(0, 0, 0, -self.height() + 30)
        p.fillRect(header, QColor(CREAM_DARK))
        p.setPen(QColor(DARK_TEXT))
        p.setFont(QFont("Sans", 9, QFont.Bold))

        circuit = self.circuit
        if not circuit:
            title = "Tor circuit unavailable"
            p.drawText(header.adjusted(10, 0, -10, 0), Qt.AlignVCenter, title)
            message = (self.unavailable_reason or
                       "No live relay path is available. Connect to Tor, open a page through Tor, then refresh.")
            self._message(p, message, MUTED)
            p.end()
            return

        nodes = circuit.get("nodes") or []
        title = f"Live Tor circuit #{circuit.get('id', '?')}"
        if circuit.get("active_stream"):
            title += "  ·  selected for an active stream"
        else:
            title += "  ·  built general-purpose circuit"
        p.drawText(header.adjusted(10, 0, -10, 0), Qt.AlignVCenter, title)
        if len(nodes) < 2:
            self._message(p, "Tor has not reported a complete built relay path yet. Load a page through Tor and refresh.", AMBER)
            p.end()
            return

        left, right = 58, max(58, self.width() - 58)
        count = len(nodes)
        spacing = (right - left) / max(1, count - 1)
        center_y = max(105, min(self.height() // 2 - 5, self.height() - 98))
        radius = 17
        xs = [left + spacing * i for i in range(count)]

        # A plain line represents circuit order only, not a physical route or
        # a promise that the exit-to-website connection uses HTTPS.
        p.setPen(QPen(QColor(PURPLE), 3, Qt.SolidLine, Qt.RoundCap))
        path = QPainterPath(QPointF(xs[0] + radius, center_y))
        for i in range(1, count):
            path.lineTo(xs[i] - radius, center_y)
        p.drawPath(path)
        for i in range(1, count):
            mid_x = (xs[i - 1] + xs[i]) / 2
            p.setPen(QPen(QColor(PURPLE_DARK), 2))
            p.drawLine(int(mid_x - 4), int(center_y - 4), int(mid_x + 4), int(center_y + 4))
            p.drawLine(int(mid_x - 4), int(center_y + 4), int(mid_x + 4), int(center_y - 4))

        palette = [PURPLE_LIGHT, PURPLE, PURPLE_DARK]
        col_width = max(72, min(150, spacing * 0.9))
        for i, node in enumerate(nodes):
            x = xs[i]
            color = QColor(palette[min(i, len(palette) - 1)])
            p.setPen(QPen(QColor(CREAM_LIGHT), 2))
            p.setBrush(QBrush(color))
            p.drawEllipse(QPointF(x, center_y), radius, radius)
            p.setPen(QColor(CREAM_LIGHT))
            p.setFont(QFont("Sans", 10, QFont.Bold))
            p.drawText(int(x - radius), int(center_y - radius), radius * 2, radius * 2,
                       Qt.AlignCenter, str(i + 1))

            p.setPen(QColor(DARK_TEXT))
            p.setFont(QFont("Sans", 9, QFont.Bold))
            role = str(node.get("position") or ("Entry" if i == 0 else "Exit" if i == count - 1 else f"Hop {i + 1}"))
            name = str(node.get("nickname") or "Unnamed relay")
            if len(name) > 20:
                name = name[:19] + "…"
            p.drawText(int(x - col_width / 2), center_y + 27, int(col_width), 18,
                       Qt.AlignCenter, f"{role}: {name}")

            city = str(node.get("city") or "Location unavailable")
            country = str(node.get("country") or "??").upper()
            if len(city) > 22:
                city = city[:21] + "…"
            p.setPen(QColor(MUTED))
            p.setFont(QFont("Sans", 8))
            p.drawText(int(x - col_width / 2), center_y + 46, int(col_width), 16,
                       Qt.AlignCenter, f"{city}, {country}")
            fp = str(node.get("fingerprint") or "")
            if fp:
                p.setFont(QFont("Monospace", 7))
                p.drawText(int(x - col_width / 2), center_y + 63, int(col_width), 14,
                           Qt.AlignCenter, fp.replace(" ", "")[:12] + "…")

        p.setPen(QColor(MUTED))
        p.setFont(QFont("Sans", 8))
        destination = self.destination or circuit.get("stream_target")
        if destination:
            host = destination.get("display") or destination.get("host") or "unknown"
            status = destination.get("status", "")
            p.setPen(QColor(DARK_TEXT))
            p.setFont(QFont("Sans", 8, QFont.Bold))
            p.drawText(self.rect().adjusted(8, 0, -8, -20), Qt.AlignBottom | Qt.AlignHCenter,
                       f"Tor-reported destination: {host} {status}")
        p.setPen(QColor(MUTED))
        p.setFont(QFont("Sans", 7))
        p.drawText(self.rect().adjusted(8, 0, -8, -4), Qt.AlignBottom | Qt.AlignHCenter,
                   "Actual relay order from Tor. Locations are GeoIP estimates; client location is not shown.")
        p.end()
