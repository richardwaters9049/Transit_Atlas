import csv
import unittest
from pathlib import Path

from design_kepler_population_sample import DISPOSITIONS, PER_STRATUM, STRATA, build_sample

ROOT = Path(__file__).resolve().parents[1]


class KeplerPopulationSampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with (ROOT / "data/raw/kepler-koi-cumulative-2026-11-14.csv").open(newline="", encoding="utf-8") as handle:
            cls.rows = list(csv.DictReader(handle))

    def test_selection_is_deterministic_and_balanced(self):
        first = build_sample(self.rows)
        second = build_sample(self.rows)
        self.assertEqual(first, second)
        self.assertEqual(len(first["targets"]), 36)
        self.assertEqual(len({row["host_id"] for row in first["targets"]}), 36)
        for disposition in DISPOSITIONS:
            selected = [row for row in first["targets"] if row["disposition"] == disposition]
            self.assertEqual(len(selected), 12)
            for stratum in STRATA:
                self.assertEqual(sum(row["snr_stratum"] == stratum for row in selected), PER_STRATUM)

    def test_missing_and_nonpositive_measurements_are_excluded(self):
        rows = [row.copy() for row in self.rows]
        rows.extend([
            {"kepoi_name": "BAD-SNR", "kepid": "90000001", "koi_disposition": "CONFIRMED", "koi_model_snr": "--", "koi_period": "2", "koi_duration": "2", "koi_depth": "100"},
            {"kepoi_name": "BAD-PERIOD", "kepid": "90000002", "koi_disposition": "CONFIRMED", "koi_model_snr": "20", "koi_period": "0", "koi_duration": "2", "koi_depth": "100"},
        ])
        result = build_sample(rows)
        selected_ids = {row["koi_id"] for row in result["targets"]}
        self.assertNotIn("BAD-SNR", selected_ids)
        self.assertNotIn("BAD-PERIOD", selected_ids)


if __name__ == "__main__":
    unittest.main()
