"""Red Tor - 3D-style animations and depth effects (PyQt5 only, no deps).

Provides:
- AnimatedStack: fade + slide page transitions for the sidebar QStackedWidget
- PulsingDot: pulsing status light (off/busy/ok)
- SpinnerLabel: rotating arc spinner for "Connecting..." states
- add_shadow / apply_depth_effects: soft drop shadows that give cards and
  primary buttons real depth
- fade_in_widget: quick lift-and-fade used when circuit data is refreshed

Everything is GPU-light: effects are removed as soon as an animation ends so
long-lived widgets never keep a graphics effect that would slow repaints.
"""
from PyQt5.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, QAbstractAnimation, QPoint,
    pyqtProperty,
)
from PyQt5.QtGui import QColor, QPainter, QPen, QBrush
from PyQt5.QtWidgets import (
    QStackedWidget, QGraphicsOpacityEffect, QGraphicsDropShadowEffect, QFrame,
    QPushButton, QWidget,
)


# ---- Depth (soft drop shadows) ------------------------------------------

def add_shadow(widget, blur=22, y_offset=5, x_offset=0,
               color=(17, 17, 17), alpha=36):
    """Attach a soft drop shadow; this is what reads as 'depth' in Qt."""
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setXOffset(x_offset)
    effect.setYOffset(y_offset)
    effect.setColor(QColor(color[0], color[1], color[2], alpha))
    widget.setGraphicsEffect(effect)
    return effect


def apply_depth_effects(window):
    """One-call pass: card shadows + red glow under primary buttons.

    Only cheap-to-repaint surfaces get effects (stat cards, CTAs); the world
    map canvas and charts never get a graphics effect, so their timer-driven
    repaints stay fast.
    """
    try:
        for card in window.findChildren(QFrame):
            if card.objectName() == "card":
                add_shadow(card, blur=24, y_offset=6, alpha=40)
        for btn in window.findChildren(QPushButton):
            if btn.objectName() == "primaryBtn":
                add_shadow(btn, blur=20, y_offset=4, alpha=90,
                           color=(183, 16, 16))
    except Exception:
        pass


# ---- Fade / slide transitions -------------------------------------------

def fade_in_widget(widget, ms=180, lift=10):
    """Lift-and-fade one widget (used on circuit refreshes)."""
    if not widget or not widget.isVisible():
        return None
    old = widget.graphicsEffect()
    if old is not None:
        widget.setGraphicsEffect(None)
    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(0.0)
    widget.setGraphicsEffect(effect)
    target = widget.pos()
    widget.move(target + QPoint(0, lift))
    fade = QPropertyAnimation(effect, b"opacity", widget)
    fade.setDuration(ms)
    fade.setStartValue(0.0)
    fade.setEndValue(1.0)
    fade.setEasingCurve(QEasingCurve.OutCubic)

    def _cleanup():
        widget.move(target)
        widget.setGraphicsEffect(None)

    fade.finished.connect(_cleanup)
    fade.start(QAbstractAnimation.DeleteWhenStopped)
    return fade


class AnimatedStack(QStackedWidget):
    """QStackedWidget whose page switches fade and slide for a 3D feel."""

    FADE_MS = 230
    SLIDE_PX = 14

    def setCurrentIndex(self, index):
        widget = self.widget(index)
        was_current = widget is self.currentWidget()
        super().setCurrentIndex(index)
        if was_current or widget is None:
            return
        self._animate_in(widget)

    def setCurrentWidget(self, widget):
        if widget is None or widget is self.currentWidget():
            super().setCurrentWidget(widget)
            return
        self.setCurrentIndex(self.indexOf(widget))

    def _animate_in(self, widget):
        # Stop any in-flight transition and drop its effect before starting
        # a new one, so rapid sidebar clicks cannot stack graphics effects.
        old_anim = getattr(self, "_anim", None)
        if old_anim is not None:
            try:
                old_anim.stop()
            except Exception:
                pass
            self._anim = None
        old_effect = getattr(self, "_anim_effect", None)
        if old_effect is not None:
            try:
                old_widget = old_effect.widget() or self.currentWidget()
                old_widget.setGraphicsEffect(None)
            except Exception:
                pass
            self._anim_effect = None

        effect = QGraphicsOpacityEffect(widget)
        effect.setOpacity(0.0)
        widget.setGraphicsEffect(effect)
        self._anim_effect = effect

        target = widget.pos()
        widget.move(target + QPoint(0, self.SLIDE_PX))
        fade = QPropertyAnimation(effect, b"opacity", self)
        fade.setDuration(self.FADE_MS)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)

        def _cleanup():
            widget.move(target)
            if self._anim_effect is effect:
                widget.setGraphicsEffect(None)
                self._anim_effect = None

        fade.finished.connect(_cleanup)
        self._anim = fade
        fade.start(QAbstractAnimation.DeleteWhenStopped)


# ---- Status lights --------------------------------------------------------

class PulsingDot(QWidget):
    """A small circular status light that softly pulses via a timer-free
    QPropertyAnimation on its own 'pulse' property."""

    _STATES = {
        "off":  QColor("#E01414"),
        "busy": QColor("#E89A0C"),
        "ok":   QColor("#22A045"),
    }

    def __init__(self, state="off", parent=None):
        super().__init__(parent)
        self.setFixedSize(14, 14)
        self._pulse = 0.0
        self._color = self._STATES.get(state, self._STATES["off"])
        self._anim = QPropertyAnimation(self, b"pulse", self)
        self._anim.setDuration(1600)
        self._anim.setLoopCount(-1)
        self._anim.setKeyValueAt(0.0, 0.0)
        self._anim.setKeyValueAt(0.5, 1.0)
        self._anim.setKeyValueAt(1.0, 0.0)
        self._anim.start()

    @pyqtProperty(float)
    def pulse(self):
        return self._pulse

    @pulse.setter
    def pulse(self, value):
        self._pulse = value
        self.update()

    def set_state(self, state):
        """Switch the light: 'off' (red), 'busy' (amber) or 'ok' (green)."""
        self._color = self._STATES.get(state, self._STATES["off"])
        self.update()

    def paintEvent(self, _ev):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        center = self.rect().center()
        radius = 4.0
        # Outer glow follows the pulse: a soft ring that breathes.
        glow_alpha = int(30 + 55 * self._pulse)
        glow = QColor(self._color)
        glow.setAlpha(glow_alpha)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(glow))
        painter.drawEllipse(center, radius + 3.5 + 2.5 * self._pulse,
                            radius + 3.5 + 2.5 * self._pulse)
        # Core dot stays constant so the light is always readable.
        painter.setBrush(QBrush(self._color))
        painter.drawEllipse(center, radius, radius)


# ---- Spinner ---------------------------------------------------------------

class SpinnerLabel(QWidget):
    """Compact rotating-arc spinner, started while Tor is connecting."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(18, 18)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._tick)

    def start(self):
        self.show()
        self._timer.start()

    def stop(self):
        self._timer.stop()
        self.hide()

    def _tick(self):
        self._angle = (self._angle + 10) % 360
        self.update()

    def paintEvent(self, _ev):
        if not self._timer.isActive():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor("#B71010"))
        pen.setWidthF(2.6)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        rect = self.rect().adjusted(3, 3, -3, -3)
        # Leading arc + faint trail reads as rotation in any direction.
        painter.drawArc(rect, self._angle * 16, 110 * 16)
        trail = QPen(pen)
        trail.setColor(QColor(183, 16, 16, 70))
        painter.setPen(trail)
        painter.drawArc(rect, (self._angle - 70) * 16, 70 * 16)
