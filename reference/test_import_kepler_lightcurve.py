"""Tests for the KOI-to-KIC and pinned ephemeris import contract."""

import unittest

from import_kepler_lightcurve import (
    QUARTER_STOP_TIMES,
    read_pinned_ephemeris,
    read_pinned_signal,
    validate_signal_mapping,
)


class PinnedSignalMappingTests(unittest.TestCase):
    def test_candidate_mapping_matches_the_pinned_catalogue_and_ephemeris(self):
        signal = read_pinned_signal("K00115.03")
        ephemeris, source = read_pinned_ephemeris("K00115.03")
        validate_signal_mapping(
            signal,
            koi_id="K00115.03",
            host_id=ephemeris["kepid"],
            role="candidate",
            period_days=ephemeris["koi_period"],
            duration_hours=ephemeris["koi_duration"],
        )
        self.assertEqual(ephemeris["koi_time0bk"], 132.6624)
        self.assertEqual(source["table"], "cumulative")

    def test_reference_mapping_matches_the_pinned_catalogue_and_ephemeris(self):
        signal = read_pinned_signal("K02961.01")
        ephemeris, _ = read_pinned_ephemeris("K02961.01")
        validate_signal_mapping(
            signal,
            koi_id="K02961.01",
            host_id=ephemeris["kepid"],
            role="reference",
            period_days=ephemeris["koi_period"],
            duration_hours=ephemeris["koi_duration"],
        )
        self.assertEqual(ephemeris["koi_time0bk"], 133.50785)

    def test_host_mismatch_is_rejected(self):
        signal = read_pinned_signal("K00115.03")
        with self.assertRaisesRegex(ValueError, "belongs to KIC"):
            validate_signal_mapping(
                signal,
                koi_id="K00115.03",
                host_id=10471515,
                role="candidate",
                period_days=3.43591631,
                duration_hours=3.133,
            )

    def test_period_mismatch_is_rejected(self):
        signal = read_pinned_signal("K00115.03")
        with self.assertRaisesRegex(ValueError, "does not match the pinned"):
            validate_signal_mapping(
                signal,
                koi_id="K00115.03",
                host_id=9579641,
                role="candidate",
                period_days=3.5,
                duration_hours=3.133,
            )

    def test_signal_role_mismatch_is_rejected(self):
        signal = read_pinned_signal("K00115.03")
        with self.assertRaisesRegex(ValueError, "role must be"):
            validate_signal_mapping(
                signal,
                koi_id="K00115.03",
                host_id=9579641,
                role="reference",
                period_days=3.43591631,
                duration_hours=3.133,
            )

    def test_quarter_filename_map_covers_the_primary_mission(self):
        self.assertEqual(len(QUARTER_STOP_TIMES), 18)
        self.assertEqual(QUARTER_STOP_TIMES[4], "2010078095331")
        self.assertEqual(QUARTER_STOP_TIMES[17], "2013131215648")


if __name__ == "__main__":
    unittest.main()
