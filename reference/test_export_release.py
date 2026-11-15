import json
import unittest

from export_release import OUTPUT, build_release


class ReleaseExportTests(unittest.TestCase):
    def test_pinned_dr24_match_coverage(self):
        result = build_release()
        self.assertEqual(result, json.loads(OUTPUT.read_text(encoding="utf-8")))
        self.assertEqual(result["coverage"], {
            "matched": 1202, "missing": 666, "incomplete": 4, "host_mismatch": 0,
        })
        example = result["matches"]["K00005.01"]
        self.assertEqual(example["host_id"], 8554498)
        self.assertEqual(example["values"][5], 5753.0)
        self.assertNotIn("K00115.03", result["matches"])


if __name__ == "__main__":
    unittest.main()
