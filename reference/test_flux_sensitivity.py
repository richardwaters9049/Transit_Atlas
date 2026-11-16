"""Tests for paired SAP/PDCSAP flux sensitivity analysis."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "reference"))

from flux_sensitivity import (  # noqa: E402
    RAW_DIR,
    TARGETS,
    measure_variant,
    rank_with_depth,
    read_paired_fits,
    run_analysis,
)
from transit_atlas import MANIFEST, fit_reference, load_snapshot  # noqa: E402


class PairedFluxSelectionTests(unittest.TestCase):
    def test_pinned_products_share_valid_cadence_identity(self):
        for target in TARGETS:
            with self.subTest(koi=target["koi_id"]):
                data = read_paired_fits(
                    RAW_DIR / f'{target["koi_id"]}-q04.fits',
                    target["host_id"], 4,
                )
                count = data["selection"]["cadences_used"]
                self.assertEqual(len(data["time"]), count)
                self.assertEqual(len(data["cadenceno"]), count)
                self.assertEqual(len(set(data["cadenceno"].tolist())), count)
                self.assertTrue(np.all(np.isfinite(data["sap"])))
                self.assertTrue(np.all(np.isfinite(data["pdcsap"])))
                self.assertEqual(
                    count,
                    data["selection"]["cadences_quality_accepted"]
                    - data["selection"]["cadences_invalid_after_quality"],
                )

    def test_flux_variants_use_identical_phase_and_cadence_selection(self):
        time = np.linspace(100.0, 110.0, 1000)
        cadence = np.arange(1000)
        phase = ((time - 102.0 + 1.0) % 2.0) / 2.0 - 0.5
        transit = np.abs(phase) <= 0.03
        pdcsap = np.ones(1000)
        pdcsap[transit] -= 0.01
        sap = pdcsap * (1.0 + 0.0002 * (time - time.mean()))
        errors = np.full(1000, 0.001)
        args = {"period_days": 2.0, "epoch_bkjd": 102.0, "duration_hours": 2.88}
        baseline = measure_variant(time, cadence, pdcsap, errors, **args)
        alternative = measure_variant(time, cadence, sap, errors, **args)
        self.assertEqual(
            [p["cadenceno"] for p in baseline["points"]],
            [p["cadenceno"] for p in alternative["points"]],
        )
        self.assertEqual(
            [p["phase"] for p in baseline["points"]],
            [p["phase"] for p in alternative["points"]],
        )
        self.assertEqual(
            [p["in_transit"] for p in baseline["points"]],
            [p["in_transit"] for p in alternative["points"]],
        )

    def test_non_positive_flux_cannot_produce_a_depth(self):
        time = np.linspace(100.0, 110.0, 100)
        cadence = np.arange(100)
        errors = np.full(100, 0.01)
        for invalid in (0.0, -1.0, float("nan"), float("inf")):
            with self.subTest(value=invalid):
                with self.assertRaises(ValueError):
                    measure_variant(
                        time, cadence, np.full(100, invalid), errors,
                        period_days=2.0, epoch_bkjd=102.0, duration_hours=2.0,
                    )

    def test_missing_uncertainties_do_not_discard_valid_flux_cadences(self):
        time = np.linspace(100.0, 110.0, 100)
        result = measure_variant(
            time, np.arange(100), np.ones(100), np.full(100, np.nan),
            period_days=2.0, epoch_bkjd=102.0, duration_hours=2.0,
        )
        self.assertEqual(len(result["points"]), 100)
        self.assertEqual(result["valid_uncertainty_ppm"]["count"], 0)


class RankingSensitivityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.observations, _, _ = load_snapshot(MANIFEST)
        cls.training, cls.scaler, cls.scaled_references, _ = fit_reference(cls.observations)

    def test_depth_substitution_keeps_host_exclusion_and_reports_distance_components(self):
        result = rank_with_depth(
            "K00115.03", 23.2, self.observations, self.training,
            self.scaler, self.scaled_references,
        )
        self.assertTrue(result["available"])
        self.assertEqual(len(result["neighbours"]), 5)
        self.assertNotIn("K00115.03", [row["koi_id"] for row in result["neighbours"]])
        self.assertTrue(all(row["host_id"] != 9579641 for row in result["neighbours"]))
        for row in result["neighbours"]:
            self.assertGreaterEqual(row["distance_squared"], row["depth_squared_contribution"])
            self.assertGreaterEqual(row["depth_squared_contribution"], 0.0)

    def test_repeated_analysis_produces_identical_numerical_report(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            first_dir = Path(temporary) / "first"
            second_dir = Path(temporary) / "second"
            run_analysis(first_dir)
            run_analysis(second_dir)
            first = json.loads((first_dir / "analysis.json").read_text())
            second = json.loads((second_dir / "analysis.json").read_text())
            first.pop("artifacts")
            second.pop("artifacts")
            self.assertEqual(first, second)

    def test_invalid_depth_is_rejected_before_log_transform(self):
        for invalid in (0.0, -0.1, float("nan"), float("inf")):
            with self.subTest(depth=invalid):
                result = rank_with_depth(
                    "K00115.03", invalid, self.observations, self.training,
                    self.scaler, self.scaled_references,
                )
                self.assertFalse(result["available"])
                self.assertIn("positive", result["reason"])


if __name__ == "__main__":
    unittest.main()
