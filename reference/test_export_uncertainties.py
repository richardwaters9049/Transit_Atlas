import json
import unittest

from export_uncertainties import OUTPUT, build_ranges, range_for
from transit_atlas import FEATURES


class QuotedErrorsTests(unittest.TestCase):
    def test_export_matches_pinned_candidates_and_measurements(self):
        built = build_ranges()
        self.assertEqual(built, json.loads(OUTPUT.read_text(encoding="utf-8")))
        self.assertEqual(built["usable_baseline_candidates"], 1872)
        ranges = built["ranges"]["K00115.03"]
        self.assertEqual(sum(interval is not None for interval in ranges), 7)
        self.assertIsNone(ranges[4])
        self.assertAlmostEqual(ranges[3][0], 0.148)
        self.assertAlmostEqual(ranges[3][1], 0.661)

    def test_invalid_or_missing_errors_hold_the_measurement_fixed(self):
        depth = FEATURES[2]
        bad = {"koi_depth_err2": "0.2", "koi_depth_err1": "0.4"}
        self.assertIsNone(range_for(bad, depth, 0.3))
        bad["koi_depth_err2"] = ""
        self.assertIsNone(range_for(bad, depth, 0.3))
        bad["koi_depth_err2"] = "-0.5"
        self.assertEqual(range_for(bad, depth, 0.3), [0.0, 0.7])


if __name__ == "__main__":
    unittest.main()
