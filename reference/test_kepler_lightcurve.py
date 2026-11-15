"""Tests for Kepler cadence filtering, flux normalisation and phase folding."""

import math
import unittest

from kepler_lightcurve import (
    DEFAULT_QUALITY_BITMASK,
    fold_light_curve,
    phase_for_time,
    validate_ephemeris,
    validate_fits_product_identity,
)


class PhaseFoldingTests(unittest.TestCase):
    def test_transit_epoch_is_zero_and_phase_wraps_at_half_period(self):
        period = 4.0
        epoch = 100.0
        self.assertAlmostEqual(phase_for_time(epoch, period, epoch), 0.0)
        self.assertAlmostEqual(phase_for_time(epoch + 1.0, period, epoch), 0.25)
        self.assertAlmostEqual(phase_for_time(epoch - 1.0, period, epoch), -0.25)
        self.assertAlmostEqual(phase_for_time(epoch + 2.0, period, epoch), -0.5)

    def test_folded_points_are_sorted_and_use_median_relative_flux(self):
        result = fold_light_curve(
            [10.0, 9.0, 11.0, 10.5],
            [100.0, 99.0, 101.0, 90.0],
            [1.0, 1.0, 1.0, 1.0],
            [0, 0, 0, 0],
            [10, 9, 11, 12],
            period_days=2.0,
            epoch_bkjd=10.0,
            duration_hours=2.0,
            quality_bitmask=0,
        )
        self.assertEqual(result["cadences_used"], 4)
        self.assertEqual(result["normalization_median_flux"], 99.5)
        phases = [point["phase"] for point in result["points"]]
        self.assertEqual(phases, sorted(phases))
        transit = next(point for point in result["points"] if point["time_bkjd"] == 10.0)
        self.assertAlmostEqual(transit["phase"], 0.0)
        self.assertAlmostEqual(transit["relative_flux_ppm"], (100 / 99.5 - 1) * 1e6)

    def test_quality_mask_rejects_flagged_cadences_without_mutating_source(self):
        times = [100.0, 100.1, 100.2]
        fluxes = [100.0, 1.0, 100.0]
        flags = [0, DEFAULT_QUALITY_BITMASK, 0]
        result = fold_light_curve(
            times, fluxes, [1.0, 1.0, 1.0], flags, [1, 2, 3],
            period_days=3.0,
            epoch_bkjd=100.0,
            duration_hours=1.0,
        )
        self.assertEqual(result["cadences_total"], 3)
        self.assertEqual(result["cadences_quality_rejected"], 1)
        self.assertEqual(result["cadences_used"], 2)
        self.assertEqual(times, [100.0, 100.1, 100.2])
        self.assertEqual(fluxes, [100.0, 1.0, 100.0])

    def test_non_finite_time_or_flux_is_excluded_and_missing_error_is_retained(self):
        result = fold_light_curve(
            [100.0, math.nan, 100.2],
            [100.0, 100.0, 101.0],
            [1.0, 1.0, math.nan],
            [0, 0, 0],
            [1, 2, 3],
            period_days=2.0,
            epoch_bkjd=100.0,
            duration_hours=1.0,
            quality_bitmask=0,
        )
        self.assertEqual(result["cadences_invalid_rejected"], 1)
        self.assertEqual(result["cadences_used"], 2)
        self.assertIsNone(result["points"][1]["relative_flux_error_ppm"])

    def test_null_values_are_supported_in_the_json_cadence_arrays(self):
        result = fold_light_curve(
            [100.0, None, 100.2],
            [100.0, 100.0, None],
            [1.0, 1.0, None],
            [0, 0, 0],
            [1, 2, 3],
            period_days=2.0,
            epoch_bkjd=100.0,
            duration_hours=1.0,
            quality_bitmask=0,
        )
        self.assertEqual(result["cadences_invalid_rejected"], 2)
        self.assertEqual(result["cadences_used"], 1)

    def test_invalid_ephemerides_are_rejected(self):
        with self.assertRaises(ValueError):
            validate_ephemeris(0.0, 100.0, 1.0)
        with self.assertRaises(ValueError):
            validate_ephemeris(1.0, 100.0, 24.0)
        with self.assertRaises(ValueError):
            phase_for_time(100.0, -1.0, 100.0)

    def test_mismatched_cadence_columns_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "equal lengths"):
            fold_light_curve(
                [100.0], [100.0, 101.0], [1.0], [0], [1],
                period_days=2.0,
                epoch_bkjd=100.0,
                duration_hours=1.0,
                quality_bitmask=0,
            )

    def test_fits_host_quarter_and_release_must_match_the_import(self):
        raw = {"metadata": {"KEPLERID": 9579641, "QUARTER": 4, "DATA_REL": 25}}
        validate_fits_product_identity(raw, host_id=9579641, quarter=4, data_release=25)
        with self.assertRaisesRegex(ValueError, "KEPLERID mismatch"):
            validate_fits_product_identity(raw, host_id=10471515, quarter=4, data_release=25)
        with self.assertRaisesRegex(ValueError, "QUARTER mismatch"):
            validate_fits_product_identity(raw, host_id=9579641, quarter=3, data_release=25)
        with self.assertRaisesRegex(ValueError, "DATA_REL mismatch"):
            validate_fits_product_identity(raw, host_id=9579641, quarter=4, data_release=24)


if __name__ == "__main__":
    unittest.main()
