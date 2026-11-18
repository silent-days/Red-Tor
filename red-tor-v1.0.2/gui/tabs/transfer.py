"""Red Tor - Transfer Stats page.

Own page for the observed app-side transfer-rate chart that used to share the
Dashboard's bottom row. It samples the same Tor-manager counters every two
seconds, so the graph keeps running while any page is open, not only while the
Dashboard is visible.
"""
import time

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor, QPainter, QPen, QBrush
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea,
)

# Optional: PyQt5.QtChart - if not installed we fall back to a lightweight
# custom-painted line chart widget so the page still works on minimal installs.
try:
    from PyQt5.QtChart import QChart, QChartView, QSplineSeries, QValueAxis
    HAVE_QTCHART = True
except ImportError:
    HAVE_QTCHART = False

from gui.theme import (
    VIOLET, VIOLET_DARK, PURPLE_PALE, GREEN_OK, MUTED, TEAL, TAN_DARK,
    CREAM_DARK, DARK_TEXT,
)
from gui.scroll_wrap import wrap_in_scroll


class _FallbackLineChart(QWidget):
    """Minimal QPainter-based line chart used when PyQt5.QtChart is missing.

    Paints a light background, violet line and measured-rate grid. Values are
    the observed application request rates in KiB/s.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._points = []
        self._max_points = 30
        self.setMinimumHeight(160)

    def set_values(self, values):
        self._points = list(values)[-self._max_points:]
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor("#FFFFFF"))
        max_value = max(1.0, max(self._points, default=0.0) * 1.15)
        p.setFont(QFont("Sans", 8))
        for i in range(6):
            fraction = i / 5
            y = int(h * (1 - fraction))
            p.setPen(QPen(QColor("#D8D8DD"), 1, Qt.DotLine))
            p.drawLine(40, y, w - 6, y)
            p.setPen(QColor("#111111"))
            p.drawText(2, y + 4, f"{fraction * max_value:.1f}")
        if len(self._points) >= 2:
            pen = QPen(QColor(VIOLET))
            pen.setWidth(2)
            p.setPen(pen)
            p.setBrush(QBrush(QColor(VIOLET)))
            plot_w = w - 40
            plot_h = h - 12
            pts = []
            for i, v in enumerate(self._points):
                x = 34 + (i / (self._max_points - 1)) * plot_w
                y = 6 + (1 - max(0.0, min(1.0, v / max_value))) * plot_h
                pts.append((x, y))
            for i in range(len(pts) - 1):
                p.drawLine(int(pts[i][0]), int(pts[i][1]),
                           int(pts[i + 1][0]), int(pts[i + 1][1]))
            p.drawEllipse(int(pts[-1][0]) - 3, int(pts[-1][1]) - 3, 6, 6)
        p.end()


class TransferTab(QWidget):
    """Observed app-side transfer rate · chart page."""

    def __init__(self, main_win):
        super().__init__()
        self.main_win = main_win
        self.tor = main_win.tor
        self._chart_points = []   # actual measured KiB/s samples only
        self._last_stats_sample = None
        self._build()
        self.refresh()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(2000)

    def _build(self):
        content = wrap_in_scroll(self)
        outer = QVBoxLayout(content)
        outer.setContentsMargins(22, 20, 22, 20)
        outer.setSpacing(12)

        title = QLabel("Transfer Stats")
        title.setFont(QFont("Sans", 18, QFont.Bold))
        title.setStyleSheet(f"color: {TEAL};")
        outer.addWidget(title)

        desc = QLabel(
            "Observed transfer rate of this app's own Tor-routed requests. "
            "These counters cover Red Tor's Python requests only — browser "
            "traffic is handled by Chromium internally and is not counted here.")
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {MUTED}; background: {CREAM_DARK}; "
                           f"padding: 9px 12px; border: 1px solid {TAN_DARK};")
        outer.addWidget(desc)

        outer.addWidget(self._build_chart_card(), 1)
        outer.addStretch(0)

    def _build_chart_card(self):
        card = QFrame()
        card.setObjectName("card")
        v = QVBoxLayout(card)
        v.setContentsMargins(14, 12, 14, 14)
        v.setSpacing(8)
        # Header
        hh = QHBoxLayout()
        title = QLabel("Observed app-side transfer rate · KiB/s")
        title.setWordWrap(True)
        title.setStyleSheet(f"color: {VIOLET_DARK}; font-size: 11pt; font-weight: bold;")
        hh.addWidget(title, 1)
        live = QLabel("No Tor session · no rate samples")
        live.setWordWrap(True)
        live.setStyleSheet(
            f"background: {PURPLE_PALE}; color: {VIOLET_DARK}; "
            f"border-radius: 10px; padding: 3px 10px; "
            f"font-size: 9pt; font-weight: 600;")
        self.rate_scope_lbl = live
        hh.addWidget(live)
        v.addLayout(hh)

        # Chart - prefer PyQt5.QtChart, fall back to a simple painted widget
        if HAVE_QTCHART:
            self.chart = QChart()
            self.chart.setBackgroundBrush(QColor("#FFFFFF"))
            self.chart.setPlotAreaBackgroundBrush(QColor("#FFFFFF"))
            self.chart.setPlotAreaBackgroundVisible(True)
            self.chart.legend().hide()
            from PyQt5.QtCore import QMargins
            self.chart.setMargins(QMargins(0, 0, 0, 0))

            self.chart_series = QSplineSeries()
            pen = self.chart_series.pen()
            pen.setColor(QColor(VIOLET))
            pen.setWidth(2)
            self.chart_series.setPen(pen)

            self.chart.addSeries(self.chart_series)

            self._axis_x = QValueAxis()
            self._axis_x.setRange(0, 30)
            self._axis_x.setVisible(False)
            self.chart.addAxis(self._axis_x, Qt.AlignBottom)
            self.chart_series.attachAxis(self._axis_x)

            self._axis_y = QValueAxis()
            self._axis_y.setRange(0, 1.0)
            self._axis_y.setLabelFormat("%.1f")
            self._axis_y.setTitleText("KiB/s")
            self._axis_y.setLabelsColor(QColor("#111111"))
            self._axis_y.setGridLineColor(QColor("#D8D8DD"))
            self._axis_y.setLinePenColor(QColor("#D8D8DD"))
            self._axis_y.setTickCount(5)
            self.chart.addAxis(self._axis_y, Qt.AlignLeft)
            self.chart_series.attachAxis(self._axis_y)

            self.chart_view = QChartView(self.chart)
            self.chart_view.setRenderHint(QPainter.Antialiasing)
            self.chart_view.setMinimumHeight(300)
            v.addWidget(self.chart_view, 1)
        else:
            # Fallback: custom-painted line chart (no extra dependency)
            self.chart = None
            self.chart_series = None
            self.chart_view = _FallbackLineChart()
            self.chart_view.setMinimumHeight(300)
            v.addWidget(self.chart_view, 1)

        # Footer stats
        foot = QHBoxLayout()
        self.down_lbl = QLabel("↓  — KiB/s")
        self.down_lbl.setStyleSheet(f"color: {VIOLET_DARK}; font-size: 10pt; font-weight: 600;")
        foot.addWidget(self.down_lbl)
        foot.addStretch(1)
        self.up_lbl = QLabel("↑  — KiB/s")
        self.up_lbl.setStyleSheet(f"color: {GREEN_OK}; font-size: 10pt; font-weight: 600;")
        foot.addWidget(self.up_lbl)
        v.addLayout(foot)

        return card

    def _push_chart(self):
        """Re-render the chart series from self._chart_points."""
        if HAVE_QTCHART and self.chart_series is not None:
            self.chart_series.clear()
            for i, p in enumerate(self._chart_points):
                self.chart_series.append(i, p)
            upper = max(1.0, max(self._chart_points, default=0.0) * 1.15)
            self._axis_y.setRange(0.0, upper)
        elif self.chart_view is not None:
            self.chart_view.set_values(self._chart_points)

    # ---- Refresh: sample counters and compute the KiB/s rate ----
    def refresh(self):
        s = self.tor.traffic_stats()
        now = time.monotonic()
        current = (int(s.get("bytes_received", 0)), int(s.get("bytes_sent", 0)))
        if not self.tor.connected:
            self._last_stats_sample = None
            self._chart_points.clear()
            self.down_lbl.setText("↓  — KiB/s (not connected)")
            self.up_lbl.setText("↑  — KiB/s (not connected)")
            self.rate_scope_lbl.setText("No Tor session · no rate samples")
        elif self._last_stats_sample is None:
            self._last_stats_sample = (now, current)
            self.down_lbl.setText("↓  Sampling…")
            self.up_lbl.setText("↑  Sampling…")
            self.rate_scope_lbl.setText("Waiting for a second counter sample")
        else:
            last_time, last = self._last_stats_sample
            self._last_stats_sample = (now, current)
            if current[0] < last[0] or current[1] < last[1]:
                self._chart_points.clear()
                self.down_lbl.setText("↓  Sampling after counter reset")
                self.up_lbl.setText("↑  Sampling after counter reset")
                self.rate_scope_lbl.setText("Counter reset detected · rebaselining")
            else:
                elapsed = max(0.1, now - last_time)
                rx_rate = (current[0] - last[0]) / elapsed / 1024
                tx_rate = (current[1] - last[1]) / elapsed / 1024
                self.down_lbl.setText(f"↓  {rx_rate:0.2f} KiB/s (app checks)")
                self.up_lbl.setText(f"↑  {tx_rate:0.2f} KiB/s (app checks)")
                self.rate_scope_lbl.setText("Measured Python requests only · browser excluded")
                self._chart_points.append(rx_rate + tx_rate)
                if len(self._chart_points) > 30:
                    self._chart_points.pop(0)
        self._push_chart()
