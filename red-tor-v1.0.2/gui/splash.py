"""Animated Red Tor splash with progress tied to completed UI startup phases."""
import os
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QFont, QPixmap, QPainter, QColor, QPainterPath
from PyQt5.QtWidgets import QWidget, QLabel, QProgressBar, QVBoxLayout, QHBoxLayout

from gui.theme import NIGHT_2, NIGHT_3, VIOLET, VIOLET_DARK, FROST, FROST_DIM, ICE_LIGHT
from gui import ASSETS


class SplashScreen(QWidget):
    """Borderless animated splash; percentage reflects completed init stages."""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.SplashScreen |
                            Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(460, 330)
        self._fading_out = False
        self._last_progress = 0
        self._build()
        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(350)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.setEasingCurve(QEasingCurve.OutCubic)
        self.setWindowOpacity(0.0)
        self._fade.start()

    def set_progress(self, percent, message):
        """Report a completed app-init milestone (not Tor/network progress)."""
        percent = max(self._last_progress, min(100, int(percent)))
        self._last_progress = percent
        self.percent_lbl.setText(f"{percent}%  ·  startup phases")
        self.loading_lbl.setText(str(message))
        self._progress_animation.stop()
        self._progress_animation.setStartValue(self.progress.value())
        self._progress_animation.setEndValue(percent)
        self._progress_animation.setDuration(max(80, min(220, (percent - self.progress.value()) * 5)))
        self._progress_animation.setEasingCurve(QEasingCurve.OutCubic)
        self._progress_animation.start()

    def fade_out_and_close(self):
        if self._fading_out:
            return
        self._fading_out = True
        self._fade.stop()
        self._fade_out = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_out.setDuration(220)
        self._fade_out.setStartValue(self.windowOpacity())
        self._fade_out.setEndValue(0.0)
        self._fade_out.setEasingCurve(QEasingCurve.InCubic)
        self._fade_out.finished.connect(self.close)
        self._fade_out.start()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 36, 40, 34)
        outer.setSpacing(10)
        logo_lbl = QLabel()
        logo_path = os.path.join(ASSETS, "logo.png")
        if os.path.exists(logo_path):
            logo_lbl.setPixmap(QPixmap(logo_path).scaled(
                112, 112, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        logo_lbl.setAlignment(Qt.AlignCenter)
        outer.addWidget(logo_lbl)

        name = QLabel(
            f"<div style='text-align:center;'><span style='color:{FROST}; "
            f"font-size:30px; font-weight:bold; letter-spacing:3px;'>RED</span> "
            f"<span style='color:{VIOLET}; font-size:30px; font-weight:bold; "
            f"letter-spacing:3px;'>TOR</span></div>")
        name.setTextFormat(Qt.RichText)
        name.setAlignment(Qt.AlignCenter)
        outer.addWidget(name)

        tag = QLabel("Local Tor client interface · not Tor Browser")
        tag.setAlignment(Qt.AlignCenter)
        tag.setFont(QFont("Sans", 9, QFont.Bold))
        tag.setStyleSheet(f"color: {FROST};")
        outer.addWidget(tag)
        outer.addSpacing(8)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        self.progress.setStyleSheet(f"""
            QProgressBar {{ background: {NIGHT_3}; border: 1px solid {ICE_LIGHT}; border-radius: 4px; }}
            QProgressBar::chunk {{ background: {VIOLET}; border-radius: 4px; }}
        """)
        outer.addWidget(self.progress)
        self._progress_animation = QPropertyAnimation(self.progress, b"value", self)

        row = QHBoxLayout()
        self.loading_lbl = QLabel("Starting Red Tor interface…")
        self.loading_lbl.setWordWrap(True)
        self.loading_lbl.setStyleSheet(f"color: {VIOLET_DARK}; font-size: 9pt; font-weight: 600;")
        row.addWidget(self.loading_lbl, 1)
        self.percent_lbl = QLabel("0%  ·  startup phases")
        self.percent_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.percent_lbl.setStyleSheet(f"color: {FROST_DIM}; font-size: 8pt;")
        row.addWidget(self.percent_lbl)
        outer.addLayout(row)
        foot = QLabel("Progress ends when the interface is ready; Tor is not auto-connected.")
        foot.setWordWrap(True)
        foot.setAlignment(Qt.AlignCenter)
        foot.setStyleSheet(f"color: {FROST_DIM}; font-size: 8pt;")
        outer.addWidget(foot)

    def paintEvent(self, ev):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(20, 20, self.width() - 40, self.height() - 40, 16, 16)
        painter.fillPath(path, QColor(NIGHT_2))
        painter.setPen(QColor(ICE_LIGHT))
        painter.drawPath(path)
        super().paintEvent(ev)
