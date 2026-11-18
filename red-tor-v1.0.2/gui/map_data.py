"""Dependency-light geography helpers used by the offline Tor relay map."""
import json
import math
import os

from gui import ASSETS

LAND_PATH = os.path.join(ASSETS, "natural-earth-110m-land.geojson")


def load_land_polygons(path=LAND_PATH):
    """Load bundled Natural Earth GeoJSON without network or extra GIS deps."""
    try:
        with open(path, encoding="utf-8") as source:
            data = json.load(source)
        polygons = []
        for feature in data.get("features", []):
            geometry = feature.get("geometry") or {}
            kind, coordinates = geometry.get("type"), geometry.get("coordinates", [])
            groups = [coordinates] if kind == "Polygon" else coordinates if kind == "MultiPolygon" else []
            for rings in groups:
                if not rings:
                    continue
                # The small-scale land layer needs only exterior rings; water
                # holes are an intentional visual simplification.
                ring = []
                for point in rings[0]:
                    try:
                        lon, lat = float(point[0]), float(point[1])
                    except (TypeError, ValueError, IndexError):
                        continue
                    if math.isfinite(lon) and math.isfinite(lat) and -180 <= lon <= 180 and -90 <= lat <= 90:
                        ring.append((lon, lat))
                if len(ring) >= 4:
                    polygons.append(ring)
        return polygons
    except (OSError, ValueError, TypeError):
        return []


def valid_point(obj):
    try:
        lat, lon = float(obj.get("lat")), float(obj.get("lon"))
        if math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180:
            return lon, lat
    except (TypeError, ValueError, AttributeError):
        pass
    return None


def great_circle(lon0, lat0, lon1, lat1, n=64):
    """Return spherical great-circle coordinates, split at the date line."""
    p0, l0, p1, l1 = map(math.radians, (lat0, lon0, lat1, lon1))
    a = (math.cos(p0) * math.cos(l0), math.cos(p0) * math.sin(l0), math.sin(p0))
    b = (math.cos(p1) * math.cos(l1), math.cos(p1) * math.sin(l1), math.sin(p1))
    omega = math.acos(max(-1.0, min(1.0, sum(a[i] * b[i] for i in range(3)))))
    xs, ys = [], []
    if omega > 1e-9 and abs(math.sin(omega)) < 1e-9:
        # Exactly antipodal points have infinitely many valid great circles.
        # Choose a stable perpendicular axis instead of dividing by sin(pi).
        axis = (0.0, 0.0, 1.0)
        orthogonal = (a[1] * axis[2] - a[2] * axis[1],
                      a[2] * axis[0] - a[0] * axis[2],
                      a[0] * axis[1] - a[1] * axis[0])
        norm = math.sqrt(sum(v * v for v in orthogonal))
        if norm < 1e-9:
            axis = (0.0, 1.0, 0.0)
            orthogonal = (a[1] * axis[2] - a[2] * axis[1],
                          a[2] * axis[0] - a[0] * axis[2],
                          a[0] * axis[1] - a[1] * axis[0])
            norm = math.sqrt(sum(v * v for v in orthogonal))
        orthogonal = tuple(v / norm for v in orthogonal)
    for i in range(n):
        t = i / (n - 1) if n > 1 else 0.0
        if omega < 1e-9:
            v = a
        elif abs(math.sin(omega)) < 1e-9:
            v = tuple(math.cos(t * omega) * a[j] + math.sin(t * omega) * orthogonal[j]
                      for j in range(3))
        else:
            sa = math.sin((1 - t) * omega) / math.sin(omega)
            sb = math.sin(t * omega) / math.sin(omega)
            v = tuple(sa * a[j] + sb * b[j] for j in range(3))
        if i == n - 1:
            v = b
        lon = math.degrees(math.atan2(v[1], v[0]))
        lat = math.degrees(math.atan2(v[2], math.hypot(v[0], v[1])))
        if xs and abs(lon - xs[-1]) > 180:
            xs.append(float("nan")); ys.append(float("nan"))
        xs.append(lon); ys.append(lat)
    return xs, ys
