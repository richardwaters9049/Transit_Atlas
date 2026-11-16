"""Tests for the PDCSAP detrending and transit-preservation experiment."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "reference"))

from pdcsap_detrending import (  # noqa: E402
    RAW_DIR, TARGETS, ephemeris_mask, estimate_trend, flatten,
    folded_shape_profile, protected_injection_train, read_product, split_segments,
    trapezoid_train, valid_injection_epochs, window_depth, run_analysis,
)


class DetrendingPrimitiveTests(unittest.TestCase):
    def test_gap_split_does_not_bridge_large_time_gaps(self):
        time = np.concatenate([np.arange(300) * 0.02, 20 + np.arange(300) * 0.02])
        segments = split_segments(time)
        self.assertEqual([len(segment) for segment in segments], [300, 300])

    def test_trend_is_positive_finite_and_does_not_mutate_inputs(self):
        time = np.arange(1001, dtype=float) * 0.02
        flux = 1.0 + 0.001 * time + 0.0001 * np.sin(time)
        original = flux.copy()
        mask = np.zeros(len(time), dtype=bool)
        mask[450:550] = True
        trend = estimate_trend(time, flux, mask, 101)
        self.assertTrue(np.all(np.isfinite(trend)))
        self.assertTrue(np.all(trend > 0))
        np.testing.assert_array_equal(flux, original)

    def test_uncertainty_uses_same_positive_trend_as_flux(self):
        flux = np.array([10.0, 20.0, 30.0])
        error = np.array([1.0, 2.0, 3.0])
        trend = np.array([2.0, 4.0, 5.0])
        flat_flux, flat_error = flatten(flux, error, trend)
        np.testing.assert_allclose(flat_flux, [5.0, 5.0, 6.0])
        np.testing.assert_allclose(flat_error, [0.5, 0.5, 0.6])

    def test_non_positive_trend_is_rejected(self):
        with self.assertRaises(ValueError):
            flatten(np.ones(3), np.ones(3), np.array([1.0, 0.0, 1.0]))

    def test_trapezoid_injection_recovers_known_depth_without_noise(self):
        time = np.arange(0.0, 40.0, 0.005)
        period, epoch, duration, depth = 3.5, 1.0, 3.0, 250e-6
        injected, mask = trapezoid_train(time, period, epoch, duration, depth)
        self.assertTrue(mask.any())
        result = window_depth(time, injected, period, epoch, duration)
        self.assertAlmostEqual(result["depth_ppm"], depth * 1e6, delta=2.0)

    def test_ephemeris_mask_is_deterministic_and_contains_transit_centres(self):
        time = np.arange(100.0, 120.0, 0.02)
        first = ephemeris_mask(time, 3.0, 102.0, 3.0, 1e-4, 0.01)
        second = ephemeris_mask(time, 3.0, 102.0, 3.0, 1e-4, 0.01)
        np.testing.assert_array_equal(first, second)
        self.assertTrue(first[np.argmin(np.abs(time - 102.0))])

    def test_injection_offsets_are_deterministic_and_disjoint_from_real_mask(self):
        time = np.arange(100.0, 190.0, 0.02)
        period, epoch, duration = 3.5, 101.0, 2.5
        real = ephemeris_mask(time, period, epoch, duration, 1e-5, 0.001)
        first = valid_injection_epochs(time, real, period, epoch, duration)
        second = valid_injection_epochs(time, real, period, epoch, duration)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 12)
        for _, injected_epoch in first:
            _, injected_mask = trapezoid_train(time, period, injected_epoch, duration, 1e-3)
            self.assertFalse(np.any(injected_mask & real))

    def test_injection_events_crossing_major_gaps_are_skipped(self):
        time = np.concatenate([np.arange(0.0, 5.0, 0.02), np.arange(6.0, 20.0, 0.02)])
        real_mask = np.zeros(len(time), dtype=bool)
        _, mask, accepted, skipped = protected_injection_train(
            time, period=3.0, epoch=2.5, duration_hours=2.0,
            depth=200e-6, real_mask=real_mask,
        )
        self.assertGreater(accepted, 0)
        self.assertGreater(skipped, 0)
        self.assertFalse(np.any(mask & real_mask))
        self.assertFalse(np.any((time > 5.0) & (time < 6.0)))

    def test_folded_shape_profile_has_declared_bins_and_finite_width(self):
        time = np.arange(0.0, 30.0, 0.01)
        flux, _ = trapezoid_train(time, 3.0, 1.0, 2.0, 300e-6)
        profile = folded_shape_profile(time, flux, 3.0, 1.0, 2.0)
        self.assertEqual(len(profile["phase_duration_units"]), 31)
        self.assertGreaterEqual(profile["half_depth_width_duration_units"], 0.0)


class PinnedProductTests(unittest.TestCase):
    def test_regenerated_analysis_is_numerically_deterministic(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            first_dir = Path(temporary) / "first"
            second_dir = Path(temporary) / "second"
            first = run_analysis(first_dir)
            second = run_analysis(second_dir)
            first.pop("artifacts", None)
            second.pop("artifacts", None)
            for target in first["targets"] + second["targets"]:
                target.pop("artifacts", None)
            self.assertEqual(first, second)

    def test_both_targets_keep_the_pinned_cadence_identity(self):
        for target in TARGETS:
            with self.subTest(koi=target["koi_id"]):
                product = read_product(RAW_DIR / f'{target["koi_id"]}-q04.fits', target["host_id"])
                self.assertEqual(len(product["time"]), 4108)
                self.assertEqual(len(np.unique(product["cadence"])), 4108)
                self.assertEqual(len(split_segments(product["time"])), 3)
                self.assertTrue(np.all(np.isfinite(product["flux"])))


if __name__ == "__main__":
    unittest.main()
