import math
import unittest

from gui.map_data import LAND_PATH, great_circle, load_land_polygons, valid_point


class MapDataTests(unittest.TestCase):
    def test_bundled_natural_earth_basemap_loads_without_network(self):
        polygons = load_land_polygons()
        self.assertGreaterEqual(len(polygons), 100)
        self.assertTrue(all(len(poly) >= 4 for poly in polygons))
        self.assertTrue(all(-180 <= lon <= 180 and -90 <= lat <= 90
                            for poly in polygons for lon, lat in poly))
        self.assertTrue(LAND_PATH.endswith("natural-earth-110m-land.geojson"))

    def test_valid_point_rejects_missing_nan_and_out_of_range_coordinates(self):
        self.assertEqual(valid_point({"lat": 40.7, "lon": -74.0}), (-74.0, 40.7))
        self.assertIsNone(valid_point({"lat": None, "lon": None}))
        self.assertIsNone(valid_point({"lat": float("nan"), "lon": 0}))
        self.assertIsNone(valid_point({"lat": 95, "lon": 0}))

    def test_great_circle_splits_at_date_line(self):
        xs, ys = great_circle(170, 10, -170, 20)
        self.assertEqual(len(xs), len(ys))
        self.assertTrue(any(math.isnan(x) for x in xs))
        self.assertAlmostEqual(xs[0], 170.0)
        self.assertAlmostEqual(ys[0], 10.0)
        self.assertAlmostEqual(xs[-1], -170.0)
        self.assertAlmostEqual(ys[-1], 20.0)

    def test_antipodal_great_circle_does_not_divide_by_zero(self):
        xs, ys = great_circle(0, 0, 180, 0)
        self.assertEqual(len(xs), len(ys))
        self.assertEqual(sum(math.isfinite(v) for v in xs), 64)
        self.assertEqual(sum(math.isfinite(v) for v in ys), 64)
        self.assertAlmostEqual(xs[0], 0.0)
        self.assertAlmostEqual(abs(xs[-1]), 180.0)


if __name__ == "__main__":
    unittest.main()
