import math
import tempfile
import unittest
from pathlib import Path

import numpy as np

from transit_atlas import (
    DEFAULT_QUERY,
    FEATURES,
    MANIFEST,
    Observation,
    candidate_lookup,
    fit_reference,
    load_snapshot,
    parse_value,
    score_vectors,
    synthetic_lookup,
)


class TransitAtlasTests(unittest.TestCase):
    def test_teaching_example_reverses_closest_neighbour(self):
        result = synthetic_lookup()
        self.assertEqual(result["full_order"], ["C", "A", "B"])
        self.assertEqual(result["display_order"], ["B", "C", "A"])
        self.assertAlmostEqual(result["examples"]["B"]["full_distance"], math.sqrt(4.04))
        self.assertAlmostEqual(result["examples"]["B"]["display_distance"], 0.2)

    def test_equal_distances_use_koi_id_as_tie_breaker(self):
        ids = ["K00001.02", "K00001.01"]
        vectors = np.array([[1.0, 0.0], [-1.0, 0.0]])
        order, _, _ = score_vectors(np.zeros(2), vectors, ids)
        self.assertEqual([ids[index] for index in order], sorted(ids))

    def test_invalid_measurements_are_counted_under_distinct_reasons(self):
        cases = [
            ("", "missing"),
            ("invalid", "invalid_number"),
            ("nan", "non_finite"),
            ("inf", "non_finite"),
            ("0", "non_positive_log_input"),
            ("-1", "non_positive_log_input"),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(parse_value(raw, FEATURES[0])[1], expected)
        self.assertEqual(parse_value("0", FEATURES[3]), (0.0, None))

    def test_constant_features_get_unit_scale(self):
        row = Observation("K00115.01", 9579641, "CONFIRMED", (1.0,) * 8)
        _, scaler, scaled, _ = fit_reference([row])
        np.testing.assert_array_equal(scaler.scale_, np.ones(8))
        np.testing.assert_array_equal(scaled, np.zeros((1, 8)))

    def test_changed_snapshot_fails_checksum(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            manifest = path / MANIFEST.name
            manifest.write_bytes(MANIFEST.read_bytes())
            manifest.with_suffix(".csv").write_text("altered data\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "checksum"):
                load_snapshot(manifest)

    def test_pinned_catalogue_reproduces_real_candidate(self):
        result = candidate_lookup(MANIFEST, DEFAULT_QUERY)
        self.assertEqual(
            [result["audit"][key] for key in ("total_rows", "usable_rows", "excluded_rows")],
            [9564, 9199, 365],
        )
        self.assertEqual(result["training_references"], 5783)
        self.assertEqual(result["eligible_references"], 5781)
        self.assertEqual(result["same_host_references_excluded"], ["K00115.01", "K00115.02"])
        expected = [
            ("K02961.01", 0.484940616390),
            ("K03172.02", 0.510942325057),
            ("K06871.01", 0.515677100099),
            ("K02636.01", 0.519176549912),
            ("K07709.01", 0.548690525420),
        ]
        for row, (identifier, distance) in zip(result["neighbours"], expected, strict=True):
            with self.subTest(identifier=identifier):
                self.assertEqual(row["koi_id"], identifier)
                self.assertNotEqual(row["host_id"], result["query"]["host_id"])
                self.assertAlmostEqual(row["distance"], distance, places=11)
                self.assertAlmostEqual(row["distance"] ** 2, row["distance_squared"], places=14)
                contributions = row["feature_contributions"].values()
                self.assertAlmostEqual(
                    math.fsum(item["squared_delta"] for item in contributions),
                    row["distance_squared"],
                    places=14,
                )
                self.assertAlmostEqual(math.fsum(item["share"] for item in contributions), 1.0)


if __name__ == "__main__":
    unittest.main()
