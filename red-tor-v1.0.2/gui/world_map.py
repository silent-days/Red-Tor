"""Offline world map for live Tor relay order using Natural Earth land data.

Relay fingerprints and location metadata are queried from Tor Metrics only
through the app's verified Tor SOCKS connection. Coordinates are approximate;
client location is never inferred or displayed.
"""

import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.collections import PolyCollection
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from PyQt5.QtWidgets import QSizePolicy

from gui.map_data import LAND_PATH, great_circle as _great_circle, load_land_polygons, valid_point as _valid_point
from gui.theme import CREAM_LIGHT, TAN_DARK, DARK_TEXT, MUTED, PURPLE, PURPLE_DARK, PURPLE_LIGHT, AMBER


_OCEAN, _LAND, _EDGE, _GRID = "#E6EDF7", "#D8E1F0", "#A9B6CC", "#C3CCDF"
_LAND_POLYGONS = load_land_polygons(LAND_PATH)


class WorldMapWidget(FigureCanvas):
    """Map showing only live Tor relays with valid GeoIP coordinates."""

    def __init__(self, parent=None):
        self.fig = Figure(figsize=(6, 3.5), dpi=100, facecolor=CREAM_LIGHT)
        super().__init__(self.fig)
        self.setParent(parent)
        self.setMinimumHeight(220)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.ax = self.fig.add_subplot(111)
        self.show_circuit_and_destination(None, None)

    def _draw_world(self):
        self.ax.add_patch(plt.Rectangle((-180, -90), 360, 180,
                                       facecolor=_OCEAN, edgecolor="none", zorder=0))
        if _LAND_POLYGONS:
            land = PolyCollection(_LAND_POLYGONS, closed=True,
                                  facecolors=_LAND, edgecolors=_EDGE,
                                  linewidths=0.35, antialiased=True, zorder=1)
            self.ax.add_collection(land)
        else:
            self.ax.text(0.5, 0.5, "Offline map data is missing",
                         transform=self.ax.transAxes, ha="center", va="center",
                         color=AMBER, fontsize=9)
        self.ax.grid(True, linestyle=":", linewidth=0.45, color=_GRID, alpha=0.8, zorder=2)
        self.ax.axhline(0, color=_EDGE, linewidth=0.6, linestyle="--", alpha=0.7, zorder=2)
        self.ax.axvline(0, color=_EDGE, linewidth=0.6, linestyle="--", alpha=0.7, zorder=2)

    def _draw_arc(self, start, end, color):
        xs, ys = _great_circle(start[0], start[1], end[0], end[1])
        self.ax.plot(xs, ys, color=color, linewidth=4, alpha=0.18, zorder=3, solid_capstyle="round")
        self.ax.plot(xs, ys, color=color, linewidth=1.8, alpha=0.92, zorder=4, solid_capstyle="round")

    def show_circuit_and_destination(self, circuit, destination=None, unavailable_reason=None):
        self.ax.clear()
        self.ax.set_facecolor(_OCEAN)
        self._draw_world()
        circuit = circuit if circuit else None
        nodes = (circuit or {}).get("nodes", [])
        mapped = []
        for node in nodes:
            point = _valid_point(node)
            mapped.append((node, point))

        # Relay order is shown, not a measured physical packet route. Never
        # connect across a hop whose GeoIP coordinates are unavailable.
        for i in range(len(mapped) - 1):
            if mapped[i][1] and mapped[i + 1][1]:
                self._draw_arc(mapped[i][1], mapped[i + 1][1],
                               PURPLE_LIGHT if i == 0 else PURPLE_DARK)
        colors = {"Entry": PURPLE_LIGHT, "Exit": PURPLE_DARK}
        for node, point in mapped:
            if not point:
                continue
            lon, lat = point
            color = colors.get(node.get("position"), PURPLE)
            self.ax.scatter([lon], [lat], s=170, color=color, edgecolors="white",
                            linewidths=1.4, zorder=6)
            city = node.get("city") or "Location unavailable"
            country = str(node.get("country") or "??").upper()
            label = (f"{node.get('position', 'Relay')}\n"
                     f"{node.get('nickname', 'Unnamed')}\n{city}, {country}*")
            self.ax.annotate(label, (lon, lat), xytext=(8, 8), textcoords="offset points",
                             fontsize=7, color=DARK_TEXT, zorder=7,
                             bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=color, lw=0.8))

        if destination:
            dest = _valid_point(destination)
            host = destination.get("display") or destination.get("host", "?")
            if dest:
                self.ax.scatter([dest[0]], [dest[1]], marker="s", s=115, color=AMBER,
                                edgecolors="white", linewidths=1.2, zorder=6)
                self.ax.annotate(
                    f"Destination server (not a Tor hop)\n{host}\n"
                    f"{destination.get('city', 'Unknown')}, {str(destination.get('country_code', '--')).upper()}*",
                    dest, xytext=(8, -28), textcoords="offset points", fontsize=7,
                    color=DARK_TEXT, zorder=7,
                    bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=AMBER, lw=0.8))
                exits = [(node, point) for node, point in mapped
                         if node.get("position") == "Exit" and point]
                if destination.get("source") == "active-stream" and exits:
                    xs, ys = _great_circle(exits[-1][1][0], exits[-1][1][1], dest[0], dest[1])
                    self.ax.plot(xs, ys, color=AMBER, linewidth=1.5, linestyle="--",
                                 alpha=0.9, zorder=5)
                    midpoint = len(xs) // 2
                    self.ax.annotate("exit → target (logical link; not a measured physical route)",
                                     (xs[midpoint], ys[midpoint]), fontsize=6.5,
                                     color=DARK_TEXT, xytext=(4, 4),
                                     textcoords="offset points", zorder=7)
            else:
                self.ax.text(0.5, 0.96, f"Active Tor stream target (not geolocated): {host}",
                             transform=self.ax.transAxes, ha="center", va="top",
                             fontsize=7.5, color=DARK_TEXT,
                             bbox=dict(boxstyle="round,pad=0.35", fc="white", ec=AMBER, lw=0.8))

        points = [point for _node, point in mapped if point]
        if circuit and nodes and not points:
            route = "  →  ".join(
                f"{node.get('nickname', 'Relay')} ({str(node.get('country') or '??').upper()})"
                for node in nodes)
            message = ("Live Tor path is available, but Tor Metrics has not returned coordinates.\n"
                       "No relay position is guessed.\n" + route)
        elif not circuit:
            message = (unavailable_reason or
                       "Connect to Tor, load a page, then refresh the circuit.\n"
                       "Client location is deliberately not shown.")
        elif len(points) < len(nodes):
            message = "Some relay locations are unavailable; only known adjacent hops are connected."
        else:
            message = None
        if message:
            self.ax.text(0.5, 0.52, message, transform=self.ax.transAxes,
                         ha="center", va="center", fontsize=8.5,
                         color=DARK_TEXT if circuit else MUTED, wrap=True,
                         bbox=dict(boxstyle="round,pad=0.5", fc="white", ec=_EDGE, alpha=0.92))

        self.ax.set_xlim(-180, 180)
        self.ax.set_ylim(-90, 90)
        self.ax.set_xticks([]); self.ax.set_yticks([])
        title = "Live Tor relay order · GeoIP locations are approximate"
        if circuit:
            title = f"Tor circuit #{circuit.get('id', '?')} · approximate GeoIP locations"
        self.ax.set_title(title, color="#3F1D72", fontsize=10, weight="bold", pad=6)
        for spine in self.ax.spines.values():
            spine.set_color(TAN_DARK)
        self.ax.text(0.01, 0.015,
                     "* GeoIP estimates, not precise server locations or measured physical packet routes",
                     transform=self.ax.transAxes, fontsize=6.5, color=MUTED)
        self.fig.subplots_adjust(top=0.88, bottom=0.04, left=0.02, right=0.98)
        self.draw_idle()
