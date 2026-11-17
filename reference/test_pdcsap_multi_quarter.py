"""Integrity and scientific-contract tests for the Q0-Q17 PDCSAP validation."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "reference"))

from pdcsap_multi_quarter import MANIFEST, read_quarter, summarise_decisions  # noqa: E402


class MultiQuarterArchiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST.read_text())

    def test_manifest_covers_two_targets_and_all_eighteen_quarters(self):
        self.assertEqual(len(self.manifest["targets"]), 2)
        for target in self.manifest["targets"]:
            self.assertEqual([p["quarter"] for p in target["quarters"]], list(range(18)))
            self.assertTrue(all(len(p["sha256"]) == 64 for p in target["quarters"]))

    def test_all_products_have_expected_host_quarter_release_and_valid_cadences(self):
        for target in self.manifest["targets"]:
            for product in target["quarters"]:
                with self.subTest(koi=target["koi_id"], quarter=product["quarter"]):
                    data = read_quarter(product, target["host_id"])
                    self.assertGreaterEqual(data["counts"]["used"], 250)
                    self.assertEqual(len(data["time"]), len(data["cadence"]))
                    self.assertEqual(len(set(data["cadence"].tolist())), len(data["cadence"]))
                    self.assertTrue((data["time"][1:] > data["time"][:-1]).all())

    def test_generated_injection_ledger_matches_supported_configurations(self):
        analysis = json.loads((ROOT / "data/generated/pdcsap-multi-quarter/analysis.json").read_text())
        self.assertEqual(analysis["source_manifest"]["product_count"], 36)
        total = 0
        for target in analysis["targets"]:
            for quarter in target["quarters"]:
                supported = sum(config["status"] == "supported" for config in quarter["configurations"].values())
                expected = supported * 3 * 12
                self.assertEqual(len(quarter["injections"]), expected)
                total += expected
        self.assertEqual(total, 4392)

    def test_downloaded_q4_products_match_the_original_pinned_q4_bytes(self):
        for target in self.manifest["targets"]:
            product = next(p for p in target["quarters"] if p["quarter"] == 4)
            original = ROOT / "data/raw/kepler-lightcurves" / f'{target["koi_id"]}-q04.fits'
            self.assertEqual(product["sha256"], __import__("hashlib").sha256(original.read_bytes()).hexdigest())


class MultiQuarterDecisionTests(unittest.TestCase):
    def test_unsupported_or_ephemeris_limited_quarters_do_not_count_as_success(self):
        config = {"status": "unsupported_segment_length_or_mask_coverage"}
        target = {"identity": {"koi_id": "K00001.01"}, "quarters": [
            {"ephemeris": {"ephemeris_limited": False}, "configurations": {"unmasked_101": config}}
            for _ in range(18)
        ]}
        decision = summarise_decisions([target, target])
        self.assertFalse(decision["assessments"]["unmasked_101"]["eligible"])
        self.assertEqual(decision["assessments"]["unmasked_101"]["targets"][0]["evaluable_quarters"], 0)


if __name__ == "__main__":
    unittest.main()
