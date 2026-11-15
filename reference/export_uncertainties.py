"""Join quoted KOI errors to the pinned baseline without changing any measurements."""

import csv
import hashlib
import io
import json
import math
from pathlib import Path

from transit_atlas import FEATURES, MANIFEST, load_snapshot, parse_value

SOURCE = MANIFEST.with_name("kepler-koi-errors-2026-11-15.json")
OUTPUT = MANIFEST.parents[1] / "generated" / "uncertainties.json"
NONNEGATIVE = {"koi_impact", "koi_steff"}


def range_for(row, feature, value):
    if feature.field == "koi_model_snr":
        return None
    try:
        minus = float(row[feature.field + "_err2"])
        plus = float(row[feature.field + "_err1"])
    except ValueError:
        return None
    if not (math.isfinite(minus) and math.isfinite(plus) and minus <= 0 <= plus):
        return None
    low, high = value + minus, value + plus
    if feature.log10 or feature.field in NONNEGATIVE:
        low = max(0.0, low)
    return [low, high] if math.isfinite(high) and low < high else None


def build_ranges(snapshot=MANIFEST, source=SOURCE):
    _, observations, _, _ = load_snapshot(snapshot)
    candidates = {row.koi_id: row for row in observations if row.disposition == "CANDIDATE"}
    manifest = json.loads(source.read_text(encoding="utf-8"))
    raw = (source.parent / manifest["file"]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest["sha256"]:
        raise ValueError("Uncertainty extract checksum does not match")
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"), newline="")))
    by_id = {row["kepoi_name"]: row for row in rows}
    if len(rows) != manifest["rows"] or len(by_id) != len(rows):
        raise ValueError("Uncertainty extract row count or KOI IDs do not match")

    ranges = {}
    unmatched = []
    for koi, baseline in sorted(candidates.items()):
        source_row = by_id.get(koi)
        if (
            source_row is None
            or int(source_row["kepid"]) != baseline.host_id
            or any(
                parse_value(source_row[feature.field], feature) != (value, None)
                for feature, value in zip(FEATURES, baseline.values, strict=True)
            )
        ):
            unmatched.append(koi)
            continue
        quoted_ranges = [
            range_for(source_row, feature, value)
            for feature, value in zip(FEATURES, baseline.values, strict=True)
        ]
        if any(interval is not None for interval in quoted_ranges):
            ranges[koi] = quoted_ranges
    return {
        "retrieved_utc_date": manifest["retrieved_utc_date"],
        "source_sha256": manifest["sha256"],
        "usable_baseline_candidates": len(candidates),
        "unmatched_candidates": unmatched,
        "ranges": ranges,
    }


if __name__ == "__main__":
    result = build_ranges()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, allow_nan=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Exported quoted ranges for {len(result['ranges']):,} candidates")
