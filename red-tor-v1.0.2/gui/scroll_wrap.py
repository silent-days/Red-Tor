"""Red Tor - page scroll wrapper.

Pages whose natural height exceeds the window used to squeeze every widget
until label text overlapped (Settings) or clipped boxes at the bottom (Local
Notes, Network Monitor). Wrapping the page in a scroll area makes the content
shift instead of break: nothing overlaps and nothing is unreachable.
"""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QScrollArea, QFrame, QWidget, QVBoxLayout


def wrap_in_scroll(parent):
    """Make a page scrollable instead of compressing or clipping content.

    Call from a page's _build() BEFORE creating its layout, then build the
    original layout on the returned content widget. The horizontal scrollbar
    appears only when a page is genuinely too wide, so squeezed side columns
    (dashboard stat cards) become reachable too.
    """
    content = QWidget(parent)
    scroll = QScrollArea(parent)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    scroll.setWidget(content)
    outer = QVBoxLayout(parent)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)
    outer.addWidget(scroll)
    return content
