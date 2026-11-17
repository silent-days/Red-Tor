"""Red Tor - Activity log widget.

Shows real-time events from the Tor manager in a scrolling log.
Color-coded by level: OK=green, INFO=blue, WARN=amber, ERROR=red.
"""
from datetime import datetime
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QFont, QTextCursor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QPlainTextEdit, QPushButton, QHBoxLayout, QLabel,
)

from gui.theme import (
    CREAM, CREAM_LIGHT, CREAM_DARK, TAN, TAN_DARK, DARK_TEXT, MUTED,
    GREEN_OK, BLUE_INFO, AMBER, RED_OFF, PURPLE, PURPLE_DARK,
)

# Level -> (color, prefix symbol)
_LEVELS = {
    "OK":    (GREEN_OK,  "[+]"),
    "INFO":  (BLUE_INFO, "[i]"),
    "WARN":  (AMBER,     "[!]"),
    "ERROR": (RED_OFF,   "[x]"),
}


class ActivityLog(QWidget):
    """Scrolling activity log widget."""

    MAX_LINES = 500

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()
        self._buffer = []

    def _build(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(4)

        # Header
        h = QHBoxLayout()
        title = QLabel("Activity Log")
        title.setFont(QFont("Sans", 10, QFont.Bold))
        title.setStyleSheet(f"color: {PURPLE_DARK};")
        h.addWidget(title)
        h.addStretch()
        self.count_lbl = QLabel("0 events")
        self.count_lbl.setStyleSheet(f"color: {MUTED}; font-size: 9pt;")
        h.addWidget(self.count_lbl)
        clear_btn = QPushButton("Clear")
        clear_btn.setFixedWidth(70)
        clear_btn.clicked.connect(self.clear)
        h.addWidget(clear_btn)
        v.addLayout(h)

        # Log view
        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setMaximumBlockCount(self.MAX_LINES)
        self.view.setFont(QFont("Monospace", 9))
        # Override background via stylesheet (still respect theme)
        self.view.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {CREAM_LIGHT};
                border: 1px solid {TAN_DARK};
                color: {DARK_TEXT};
                font-family: 'DejaVu Sans Mono', 'Liberation Mono', monospace;
                font-size: 9pt;
            }}
        """)
        v.addWidget(self.view)

        self._count = 0

    def append(self, level: str, message: str):
        """Append a log line. Called by TorManager listener."""
        color, prefix = _LEVELS.get(level, (DARK_TEXT, "[?]"))
        # Use HTML for color
        # Escape HTML special chars in message
        safe = (message.replace("&", "&amp;")
                       .replace("<", "&lt;")
                       .replace(">", "&gt;"))
        html = (f"<span style='color:{MUTED};'>[{datetime.now().strftime('%H:%M:%S')}]</span> "
                f"<span style='color:{color}; font-weight:600;'>{prefix} {level}</span> "
                f"<span style='color:{DARK_TEXT};'>{safe}</span>")
        self.view.appendHtml(html)
        self.view.moveCursor(QTextCursor.End)
        self._count += 1
        self.count_lbl.setText(f"{self._count} events")

    def clear(self):
        self.view.clear()
        self._count = 0
        self.count_lbl.setText("0 events")
