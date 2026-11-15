import unittest

from evaluate import CONFIRMED, FALSE_POSITIVE, agreement, evaluate, rank_queries
from transit_atlas import MANIFEST, Observation


class EvaluationTests(unittest.TestCase):
    def test_agreement_distinguishes_overall_and_balanced_recall(self):
        expected = [CONFIRMED, FALSE_POSITIVE, FALSE_POSITIVE]
        scores = agreement(expected, [FALSE_POSITIVE] * 3)
        self.assertEqual(scores["agreement"], 2 / 3)
        self.assertEqual(scores["balanced_agreement"], 0.5)
        self.assertIsNone(agreement([], [])["agreement"])
        self.assertIsNone(agreement([CONFIRMED], [CONFIRMED])["balanced_agreement"])

    def test_rank_queries_rejects_a_shared_host(self):
        training = [Observation(str(i), i, CONFIRMED, (1.0,) * 8) for i in range(1, 8)]
        with self.assertRaisesRegex(ValueError, "overlaps"):
            rank_queries([training[0]], [], training, [])

    def test_pinned_snapshot_retains_expected_counts_and_selection(self):
        report = evaluate(MANIFEST)
        self.assertEqual(report["selected_k"], 5)
        self.assertEqual(report["test"]["knn"]["confusion_actual_by_vote"], {
            CONFIRMED: {CONFIRMED: 295, FALSE_POSITIVE: 18},
            FALSE_POSITIVE: {CONFIRMED: 54, FALSE_POSITIVE: 409},
        })
        bands = report["test_signal_to_noise_bands"]
        self.assertEqual(sum(band["knn"]["rows"] for band in bands.values()), 776)
        self.assertEqual(report["complete_case_coverage"]["test"][FALSE_POSITIVE], {"raw": 483, "usable": 463})
        self.assertEqual(report["correlation_sensitivity"]["neighbour_sets_changed"], 480)


if __name__ == "__main__":
    unittest.main()
