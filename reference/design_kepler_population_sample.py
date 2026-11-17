#!/usr/bin/env python3
"""Create a deterministic, disposition-balanced Kepler KOI sample frame."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/raw/kepler-koi-cumulative-2026-11-14.csv"
OUTPUT = ROOT / "data/studies/kepler-population-sample-2026-11-17.json"
DISPOSITIONS = ("CONFIRMED", "FALSE POSITIVE", "CANDIDATE")
STRATA = ("low", "middle", "high")
PER_STRATUM = 4
SEED = "TransitAtlas-Kepler-population-v1-2026-11-17"


def _quantile(sorted_values: list[float], fraction: float) -> float:
    position = (len(sorted_values) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def build_sample(rows: list[dict[str, str]]) -> dict:
    selected: list[dict] = []
    summaries: dict[str, dict] = {}
    for disposition in DISPOSITIONS:
        eligible = []
        for row in rows:
            if row.get("koi_disposition") != disposition:
                continue
            try:
                snr = float(row["koi_model_snr"])
                host = int(row["kepid"])
                period = float(row["koi_period"])
                duration = float(row["koi_duration"])
                depth = float(row["koi_depth"])
            except (KeyError, TypeError, ValueError):
                continue
            if not all(math.isfinite(x) and x > 0 for x in (snr, period, duration, depth)):
                continue
            eligible.append((row, snr, host))
        if len(eligible) < PER_STRATUM * len(STRATA):
            raise ValueError(f"Insufficient eligible rows for {disposition}")
        snrs = sorted(item[1] for item in eligible)
        lower = _quantile(snrs, 1 / 3)
        upper = _quantile(snrs, 2 / 3)
        bins = {
            "low": [x for x in eligible if x[1] <= lower],
            "middle": [x for x in eligible if lower < x[1] <= upper],
            "high": [x for x in eligible if x[1] > upper],
        }
        used_hosts: set[int] = set()
        summaries[disposition] = {
            "eligible_rows": len(eligible),
            "eligible_unique_hosts": len({x[2] for x in eligible}),
            "snr_tertile_boundaries": {"low_upper_inclusive": lower, "middle_upper_inclusive": upper},
            "strata": {},
        }
        for stratum in STRATA:
            ranked = sorted(
                bins[stratum],
                key=lambda item: hashlib.sha256(f"{SEED}|{disposition}|{stratum}|{item[0]['kepoi_name']}".encode()).hexdigest(),
            )
            chosen = []
            for row, snr, host in ranked:
                if host in used_hosts:
                    continue
                used_hosts.add(host)
                chosen.append((row, snr, host))
                if len(chosen) == PER_STRATUM:
                    break
            if len(chosen) != PER_STRATUM:
                raise ValueError(f"Could not select {PER_STRATUM} unique hosts for {disposition}/{stratum}")
            summaries[disposition]["strata"][stratum] = {
                "eligible_rows": len(bins[stratum]),
                "selected": len(chosen),
            }
            for row, snr, host in chosen:
                selected.append({
                    "koi_id": row["kepoi_name"],
                    "host_id": host,
                    "disposition": disposition,
                    "snr_stratum": stratum,
                    "model_snr": snr,
                    "period_days": float(row["koi_period"]),
                    "duration_hours": float(row["koi_duration"]),
                    "depth_ppm": float(row["koi_depth"]),
                    "impact_parameter": _optional_float(row.get("koi_impact")),
                    "effective_temperature_k": _optional_float(row.get("koi_steff")),
                    "surface_gravity_log10_cgs": _optional_float(row.get("koi_slogg")),
                    "stellar_radius_solar": _optional_float(row.get("koi_srad")),
                })
    selected.sort(key=lambda x: (DISPOSITIONS.index(x["disposition"]), STRATA.index(x["snr_stratum"]), x["koi_id"]))
    if len({x["host_id"] for x in selected}) != len(selected):
        raise AssertionError("Selected sample contains repeated host stars")
    return {
        "schema": "transit-atlas.kepler-population-sample",
        "schema_version": 1,
        "status": "provisional_sample_frame_not_archive_validated",
        "created_utc_date": "2026-11-17",
        "selection_seed": SEED,
        "selection_method": "Within each disposition, calculate empirical model-SNR tertiles; select four rows from each tertile using SHA-256 ordering and without replacement by host star.",
        "source": {
            "archive": "NASA Exoplanet Archive",
            "table": "cumulative",
            "snapshot_date": "2026-11-14",
            "file": "data/raw/kepler-koi-cumulative-2026-11-14.csv",
            "sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        },
        "design": {"dispositions": list(DISPOSITIONS), "snr_strata": list(STRATA), "per_stratum": PER_STRATUM, "target_count": len(DISPOSITIONS) * len(STRATA) * PER_STRATUM},
        "stratum_summary": summaries,
        "targets": selected,
        "archive_validation_required_before_lock": [
            "Confirm an unambiguous KOI-to-KIC mapping and retrieveable DR25 long-cadence products.",
            "Record available quarters, cadence counts, gaps, quality-usable cadences and product checksums.",
            "Check that each target has sufficient observed transit events and usable out-of-transit baseline.",
            "Check ephemeris uncertainty against transit duration; classify limitations before any replacement.",
            "If a target fails eligibility, replace it only with the next deterministic eligible row in the same disposition/SNR stratum and record the exclusion.",
        ],
    }


def _optional_float(value: str | None) -> float | None:
    try:
        result = float(value) if value not in (None, "", "--") else None
    except ValueError:
        return None
    return result if result is not None and math.isfinite(result) else None


def main() -> None:
    with SOURCE.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    result = build_sample(rows)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(result['targets'])} targets to {OUTPUT.relative_to(ROOT)}")
    for disposition, summary in result["stratum_summary"].items():
        print(disposition, summary["strata"])


if __name__ == "__main__":
    main()
