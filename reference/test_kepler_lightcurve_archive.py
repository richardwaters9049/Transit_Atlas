"""Offline replay tests against the two pinned Kepler Q4 FITS products."""

import json
import math
import unittest
from pathlib import Path

from kepler_lightcurve import fold_light_curve, read_kepler_fits, sha256_file

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = (
    "K00115.03-q04.json",
    "K02961.01-q04.json",
)


class ArchivedLightCurveReplayTests(unittest.TestCase):
    def test_pinned_fits_products_replay_the_saved_folded_series(self):
        for fixture_name in FIXTURES:
            with self.subTest(fixture=fixture_name):
                document_path = ROOT / "data/generated/lightcurves" / fixture_name
                document = json.loads(document_path.read_text(encoding="utf-8"))
                source_path = ROOT / document["source"]["local_file"]

                self.assertEqual(document["schema"], "transit-atlas.kepler-lightcurve")
                self.assertEqual(document["version"], 1)
                self.assertEqual(document["source"]["quarter"], 4)
                self.assertEqual(document["source"]["time_format"], "bkjd")
                self.assertEqual(document["source"]["time_scale"], "tdb")
                self.assertEqual(sha256_file(source_path), document["source"]["sha256"])

                raw = read_kepler_fits(source_path, document["processing"]["flux_column"])
                self.assertEqual(len(raw["time_bkjd"]), document["folded"]["cadences_total"])
                self.assertEqual(raw["source_sha256"], document["source"]["sha256"])

                replay = fold_light_curve(
                    raw["time_bkjd"],
                    raw["flux"],
                    raw["flux_err"],
                    raw["quality"],
                    raw["cadenceno"],
                    period_days=document["ephemeris"]["period_days"],
                    epoch_bkjd=document["ephemeris"]["epoch_bkjd"],
                    duration_hours=document["ephemeris"]["duration_hours"],
                    quality_bitmask=document["processing"]["quality_bitmask"],
                )

                for field in (
                    "cadences_total",
                    "cadences_used",
                    "cadences_quality_rejected",
                    "cadences_invalid_rejected",
                    "quality_bitmask",
                    "normalization",
                ):
                    self.assertEqual(replay[field], document["folded"][field])
                self.assertTrue(math.isclose(
                    replay["normalization_median_flux"],
                    document["folded"]["normalization_median_flux"],
                    rel_tol=1e-13,
                ))

                expected = document["folded"]["points"]
                actual = replay["points"]
                self.assertEqual(len(actual), len(expected))
                for expected_point, actual_point in zip(expected, actual, strict=True):
                    for field in (
                        "phase",
                        "phase_days",
                        "time_bkjd",
                        "relative_flux_ppm",
                    ):
                        self.assertTrue(math.isclose(
                            expected_point[field],
                            actual_point[field],
                            rel_tol=1e-13,
                            abs_tol=1e-10,
                        ), f"{fixture_name}: {field} differs")
                    self.assertEqual(expected_point["quality"], actual_point["quality"])
                    self.assertEqual(expected_point["cadenceno"], actual_point["cadenceno"])
                    expected_error = expected_point["relative_flux_error_ppm"]
                    actual_error = actual_point["relative_flux_error_ppm"]
                    if expected_error is None:
                        self.assertIsNone(actual_error)
                    else:
                        self.assertTrue(math.isclose(
                            expected_error, actual_error, rel_tol=1e-13, abs_tol=1e-10
                        ))

    def test_candidate_and_reference_have_distinct_signal_ephemerides(self):
        documents = [
            json.loads((ROOT / "data/generated/lightcurves" / name).read_text())
            for name in FIXTURES
        ]
        self.assertEqual(
            [item["identity"]["koi_id"] for item in documents],
            ["K00115.03", "K02961.01"],
        )
        self.assertNotEqual(
            documents[0]["ephemeris"]["period_days"],
            documents[1]["ephemeris"]["period_days"],
        )
        self.assertNotEqual(
            documents[0]["ephemeris"]["epoch_bkjd"],
            documents[1]["ephemeris"]["epoch_bkjd"],
        )


if __name__ == "__main__":
    unittest.main()
