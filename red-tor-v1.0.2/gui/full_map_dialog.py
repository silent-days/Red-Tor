"""Expanded map dialog using the same live relay data as the Tor panel."""
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton

from gui.theme import CREAM_LIGHT, CREAM_DARK, DARK_TEXT, MUTED, PURPLE_DARK, PURPLE_PALE, RED_OFF, TAN_DARK
from gui.world_map import WorldMapWidget


class FullMapDialog(QDialog):
    """Large map of Tor's live circuit; GeoIP positions are approximate."""

    def __init__(self, parent=None, circuit=None, destination=None, unavailable_reason=None):
        super().__init__(parent)
        self.circuit = circuit
        self.destination = destination
        self.unavailable_reason = unavailable_reason
        self.setWindowTitle("Red Tor — Live Circuit Map")
        self.resize(1050, 680)
        self.setMinimumSize(760, 520)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        header = QLabel("  Red Tor · Live Tor relay order")
        header.setFont(QFont("Sans", 14, QFont.Bold))
        header.setStyleSheet(f"background: {PURPLE_PALE}; color: #111111; border-bottom: 1px solid {RED_OFF}; padding: 12px 16px;")
        layout.addWidget(header)

        self.map_widget = WorldMapWidget()
        self.map_widget.setMinimumHeight(560)
        self.map_widget.show_circuit_and_destination(
            self.circuit, self.destination, self.unavailable_reason)
        layout.addWidget(self.map_widget, 1)

        nodes = (self.circuit or {}).get("nodes", [])
        if nodes:
            route = "  →  ".join(
                f"{node.get('position', 'Relay')}: {node.get('nickname', 'Unnamed')} "
                f"({str(node.get('country') or '??').upper()}, {node.get('city') or 'location unavailable'})"
                for node in nodes)
            info = QLabel(route)
        else:
            info = QLabel(self.unavailable_reason or
                          "No live relay path is available. Connect to Tor and load a page through Tor.")
        info.setWordWrap(True)
        info.setStyleSheet(f"background: {CREAM_DARK}; color: {DARK_TEXT}; padding: 10px 16px; border-top: 1px solid {TAN_DARK};")
        layout.addWidget(info)

        note = QLabel("Relay coordinates are approximate Tor Metrics GeoIP estimates. Lines show relay order, not a measured physical packet route. The client location is not shown.")
        note.setWordWrap(True)
        note.setStyleSheet(f"background: {CREAM_LIGHT}; color: {MUTED}; padding: 8px 16px;")
        layout.addWidget(note)

        footer = QHBoxLayout()
        footer.addStretch()
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        close.setStyleSheet(f"background: {PURPLE_PALE}; color: #111111; border-bottom: 1px solid {RED_OFF}; padding: 8px 24px; border-radius: 3px;")
        footer.addWidget(close)
        container = QLabel()
        container.setLayout(footer)
        container.setStyleSheet(f"background: {CREAM_LIGHT}; padding: 6px;")
        layout.addWidget(container)
