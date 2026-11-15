"""Match the pinned Kepler DR24 observations to current usable candidates."""

import json

from transit_atlas import MANIFEST, load_snapshot

SOURCE = MANIFEST.with_name("kepler-koi-dr24-2026-11-15.json")
OUTPUT = MANIFEST.parents[1] / "generated" / "dr24.json"


def build_release():
    _, current, _, _ = load_snapshot(MANIFEST)
    manifest, historical, rejected, _ = load_snapshot(SOURCE)
    earlier = {row.koi_id: row for row in historical}
    candidates = [row for row in current if row.disposition == "CANDIDATE"]
    matches = {}
    coverage = {"matched": 0, "missing": 0, "incomplete": 0, "host_mismatch": 0}
    for candidate in candidates:
        row = earlier.get(candidate.koi_id)
        if row is None:
            coverage["incomplete" if candidate.koi_id in rejected else "missing"] += 1
        elif row.host_id != candidate.host_id:
            coverage["host_mismatch"] += 1
        else:
            coverage["matched"] += 1
            matches[row.koi_id] = {
                "host_id": row.host_id, "disposition": row.disposition, "values": list(row.values),
            }
    return {
        "release": manifest["release"],
        "release_last_updated": manifest["release_last_updated"],
        "retrieved_utc_date": manifest["retrieved_utc_date"],
        "source_sha256": manifest["sha256"],
        "coverage": coverage,
        "matches": matches,
    }


if __name__ == "__main__":
    report = build_release()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(report, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(f"DR24 candidate coverage: {report['coverage']}")
