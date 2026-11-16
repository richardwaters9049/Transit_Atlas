"""Offline paired SAP/PDCSAP depth and 8D KNN sensitivity analysis."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import sys
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import sklearn
from astropy import __version__ as astropy_version
from astropy.io import fits

from kepler_lightcurve import DEFAULT_QUALITY_BITMASK, PHASE_CONVENTION
from transit_atlas import FEATURES, MANIFEST, fit_reference, load_snapshot, score_vectors

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data/raw/kepler-lightcurves"
OUTPUT_DIR = ROOT / "data/generated/flux-sensitivity"
TARGETS = (
    {"koi_id": "K00115.03", "host_id": 9579641, "role": "candidate"},
    {"koi_id": "K02961.01", "host_id": 10471515, "role": "reference"},
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def summary(values: np.ndarray) -> dict[str, Any]:
    values = values[np.isfinite(values)]
    if not values.size:
        return {"count": 0, "median": None, "mad": None, "minimum": None, "maximum": None}
    median = float(np.median(values))
    return {
        "count": int(values.size),
        "median": median,
        "mad": float(np.median(np.abs(values - median))),
        "minimum": float(np.min(values)),
        "maximum": float(np.max(values)),
    }


def read_paired_fits(path: Path, expected_host: int, expected_quarter: int) -> dict[str, Any]:
    """Read both flux columns from one FITS file and establish a shared cadence mask."""
    with fits.open(path, memmap=True) as hdul:
        primary, hdu = hdul[0].header, hdul[1]
        header, data = hdu.header, hdu.data
        names = set(hdu.columns.names or ())
        required = {
            "TIME", "CADENCENO", "SAP_QUALITY", "SAP_FLUX", "SAP_FLUX_ERR",
            "PDCSAP_FLUX", "PDCSAP_FLUX_ERR",
        }
        missing = sorted(required - names)
        if missing:
            raise ValueError(f"{path.name} is missing FITS columns: {', '.join(missing)}")

        def meta(key: str, fallback: Any = None) -> Any:
            return header.get(key, primary.get(key, fallback))

        host_id = int(meta("KEPLERID", expected_host))
        quarter = int(meta("QUARTER", expected_quarter))
        release = int(meta("DATA_REL", 0))
        if (host_id, quarter, release) != (expected_host, expected_quarter, 25):
            raise ValueError(
                f"{path.name}: expected KIC/Q/DR ("
                f"{expected_host}/{expected_quarter}/25), got {host_id}/{quarter}/{release}"
            )

        time = np.asarray(data["TIME"], dtype=np.float64)
        cadence = np.asarray(data["CADENCENO"], dtype=np.int64)
        quality = np.asarray(data["SAP_QUALITY"], dtype=np.int64)
        sap = np.asarray(data["SAP_FLUX"], dtype=np.float64)
        sap_err = np.asarray(data["SAP_FLUX_ERR"], dtype=np.float64)
        pdcsap = np.asarray(data["PDCSAP_FLUX"], dtype=np.float64)
        pdcsap_err = np.asarray(data["PDCSAP_FLUX_ERR"], dtype=np.float64)

    if str(header.get("TIMESYS", "")) != "TDB":
        raise ValueError(f"{path.name}: expected TDB timestamps")
    if str(header.get("TIMEUNIT", "")) != "d" or int(header.get("BJDREFI", -1)) != 2454833:
        raise ValueError(f"{path.name}: expected Kepler BKJD day timestamps")
    quality_ok = (quality & DEFAULT_QUALITY_BITMASK) == 0
    paired_finite = np.isfinite(time) & np.isfinite(sap) & np.isfinite(pdcsap)
    selected = quality_ok & paired_finite
    if not np.any(selected):
        raise ValueError(f"{path.name}: no paired finite cadences survive quality filtering")

    return {
        "identity": {"host_id": host_id, "quarter": quarter, "data_release": release},
        "source": {
            "filename": path.name,
            "relative_path": str(path.relative_to(ROOT)),
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
            "time_format": "BKJD",
            "time_scale": str(header.get("TIMESYS", "")),
            "time_unit": str(header.get("TIMEUNIT", "")),
            "bjd_reference_integer": int(header.get("BJDREFI", -1)),
            "bjd_reference_fraction": float(header.get("BJDREFF", float("nan"))),
            "pipeline_version": str(primary.get("PROCVER", "")),
            "creator": str(primary.get("CREATOR", "")),
            "object": str(header.get("OBJECT", "")),
            "quality_column": "SAP_QUALITY",
            "quality_bitmask": DEFAULT_QUALITY_BITMASK,
        },
        "selection": {
            "cadences_total": int(len(time)),
            "cadences_quality_accepted": int(np.count_nonzero(quality_ok)),
            "cadences_quality_rejected": int(np.count_nonzero(~quality_ok)),
            "cadences_paired_finite": int(np.count_nonzero(paired_finite)),
            "cadences_invalid_after_quality": int(np.count_nonzero(quality_ok & ~paired_finite)),
            "cadences_used": int(np.count_nonzero(selected)),
        },
        "time": time[selected],
        "cadenceno": cadence[selected],
        "quality": quality[selected],
        "sap": sap[selected],
        "sap_err": sap_err[selected],
        "pdcsap": pdcsap[selected],
        "pdcsap_err": pdcsap_err[selected],
    }


def measure_variant(
    time: np.ndarray, cadence: np.ndarray, flux: np.ndarray, flux_err: np.ndarray,
    *, period_days: float, epoch_bkjd: float, duration_hours: float,
) -> dict[str, Any]:
    """Return a fixed-window descriptive depth and every selected cadence."""
    if not (len(time) == len(cadence) == len(flux) == len(flux_err)):
        raise ValueError("Cadence arrays must have equal lengths")
    if not np.all(np.isfinite(time)) or not np.all(np.isfinite(flux)):
        raise ValueError("Selected time and flux values must be finite")
    baseline = float(np.median(flux))
    if not math.isfinite(baseline) or baseline <= 0:
        raise ValueError("Flux median must be finite and positive")
    phase = ((time - epoch_bkjd + period_days / 2) % period_days) / period_days - 0.5
    half_window = duration_hours / (48.0 * period_days)
    inside = np.abs(phase) <= half_window
    outside = ~inside
    if not inside.any() or not outside.any():
        raise ValueError("Transit or out-of-transit window is empty")
    in_flux, out_flux = flux[inside], flux[outside]
    median_in, median_out = float(np.median(in_flux)), float(np.median(out_flux))
    if median_out <= 0:
        raise ValueError("Out-of-transit median must be positive")
    depth = 1e6 * (median_out - median_in) / median_out
    valid_err = np.isfinite(flux_err) & (flux_err >= 0)
    err_ppm = flux_err[valid_err] / baseline * 1e6
    in_err = flux_err[inside & valid_err] / baseline * 1e6
    out_err = flux_err[outside & valid_err] / baseline * 1e6
    relative_ppm = (flux / baseline - 1) * 1e6
    points = [
        {
            "cadenceno": int(cadence[i]),
            "time_bkjd": float(time[i]),
            "phase": float(phase[i]),
            "in_transit": bool(inside[i]),
            "flux": float(flux[i]),
            "flux_err": float(flux_err[i]) if math.isfinite(flux_err[i]) else None,
            "relative_flux_ppm": float(relative_ppm[i]),
        }
        for i in range(len(time))
    ]
    return {
        "normalization": "per_variant_median_relative_flux_ppm",
        "normalization_median_flux": baseline,
        "in_transit_cadences": int(inside.sum()),
        "out_of_transit_cadences": int(outside.sum()),
        "in_transit_flux": summary(in_flux),
        "out_of_transit_flux": summary(out_flux),
        "in_transit_relative_flux_ppm": summary(relative_ppm[inside]),
        "out_of_transit_relative_flux_ppm": summary(relative_ppm[outside]),
        "valid_uncertainty_ppm": summary(err_ppm),
        "in_transit_uncertainty_ppm": summary(in_err),
        "out_of_transit_uncertainty_ppm": summary(out_err),
        "windowed_median_depth_ppm": float(depth),
        "points": points,
    }


def rank_with_depth(
    koi_id: str, depth_ppm: float, observations: list[Any], training: list[Any],
    scaler: Any, scaled_references: np.ndarray, k: int = 5,
) -> dict[str, Any]:
    """Substitute only depth; use the existing training scaler and reference pool."""
    if not math.isfinite(depth_ppm) or depth_ppm <= 0:
        return {"available": False, "reason": "Depth must be finite and positive for log10 scaling."}
    query = next((row for row in observations if row.koi_id == koi_id), None)
    if query is None:
        raise ValueError(f"{koi_id} is absent from the pinned catalogue")
    values = np.asarray(query.values, dtype=np.float64).copy()
    values[2] = depth_ppm
    for index, feature in enumerate(FEATURES):
        if feature.log10:
            if not math.isfinite(values[index]) or values[index] <= 0:
                return {"available": False, "reason": f"{feature.field} is invalid for log10 scaling."}
            values[index] = math.log10(values[index])
    scaled_query = scaler.transform(values.reshape(1, -1))[0]
    eligible = [
        index for index, row in enumerate(training)
        if row.host_id != query.host_id and row.koi_id != query.koi_id
    ]
    refs = [training[index] for index in eligible]
    order, squared, contributions = score_vectors(
        scaled_query, scaled_references[eligible], [row.koi_id for row in refs]
    )
    neighbours = []
    for rank, position in enumerate(order[:k], start=1):
        d2 = float(squared[position])
        depth_d2 = float(contributions[position, 2])
        neighbours.append({
            "rank": rank,
            "koi_id": refs[position].koi_id,
            "host_id": refs[position].host_id,
            "disposition": refs[position].disposition,
            "distance": math.sqrt(d2),
            "distance_squared": d2,
            "depth_squared_contribution": depth_d2,
            "depth_squared_share": depth_d2 / d2 if d2 > 0 else None,
        })
    return {
        "available": True,
        "query_depth_ppm": depth_ppm,
        "reference_count": len(refs),
        "neighbours": neighbours,
    }


def plot_results(results: list[dict[str, Any]], path: Path) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(15, 9), constrained_layout=True)
    for row, result in enumerate(results):
        variants = result["variants"]
        for col, name in enumerate(("pdcsap", "sap")):
            points = variants[name]["points"]
            x = np.asarray([p["time_bkjd"] if col == 0 else p["phase"] for p in points])
            y = np.asarray([p["relative_flux_ppm"] for p in points])
            axes[row, col].scatter(x, y, s=3, alpha=0.35, rasterized=True)
            axes[row, col].axhline(0, linewidth=0.7, alpha=0.5)
            axes[row, col].set_title(f'{result["identity"]["koi_id"]} · {name.upper()}')
            axes[row, col].set_ylabel("Relative flux (ppm)")
            axes[row, col].set_xlabel("Time (BKJD)" if col == 0 else "Orbital phase")
            if col == 1:
                axes[row, col].set_xlim(-0.15, 0.15)
        low = min(min(p["relative_flux_ppm"] for p in variants[n]["points"]) for n in ("pdcsap", "sap"))
        high = max(max(p["relative_flux_ppm"] for p in variants[n]["points"]) for n in ("pdcsap", "sap"))
        pad = max((high - low) * 0.04, 10)
        for axis in axes[row]:
            axis.set_ylim(low - pad, high + pad)
    fig.suptitle("Paired Kepler SAP and PDCSAP flux · shared axes per target")
    fig.savefig(path, dpi=170)
    plt.close(fig)


def run_analysis(output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    catalogue_manifest, observations, rejected, audit = load_snapshot(MANIFEST)
    training, scaler, scaled_refs, partitions = fit_reference(observations)
    scaler_spec = [
        {
            "field": feature.field,
            "transform": "log10" if feature.log10 else "identity",
            "training_mean": float(scaler.mean_[i]),
            "training_scale": float(scaler.scale_[i]),
        }
        for i, feature in enumerate(FEATURES)
    ]
    results = []
    for target in TARGETS:
        koi_id = target["koi_id"]
        source_doc = json.loads(
            (ROOT / "data/generated/lightcurves" / f"{koi_id}-q04.json").read_text()
        )
        ephemeris = source_doc["ephemeris"]
        paired = read_paired_fits(
            RAW_DIR / f"{koi_id}-q04.fits", target["host_id"], 4
        )
        variants = {
            name: measure_variant(
                paired["time"], paired["cadenceno"], paired[name], paired[f"{name}_err"],
                period_days=float(ephemeris["period_days"]),
                epoch_bkjd=float(ephemeris["epoch_bkjd"]),
                duration_hours=float(ephemeris["duration_hours"]),
            )
            for name in ("pdcsap", "sap")
        }
        pdcsap_depth = variants["pdcsap"]["windowed_median_depth_ppm"]
        sap_depth = variants["sap"]["windowed_median_depth_ppm"]
        delta = sap_depth - pdcsap_depth
        in_mad_ratio = (
            variants["sap"]["in_transit_relative_flux_ppm"]["mad"]
            / variants["pdcsap"]["in_transit_relative_flux_ppm"]["mad"]
        )
        out_mad_ratio = (
            variants["sap"]["out_of_transit_relative_flux_ppm"]["mad"]
            / variants["pdcsap"]["out_of_transit_relative_flux_ppm"]["mad"]
        )
        results.append({
            "identity": {
                **target, "quarter": 4, "data_release": 25,
                "ephemeris": {
                    "period_days": ephemeris["period_days"],
                    "epoch_bkjd": ephemeris["epoch_bkjd"],
                    "duration_hours": ephemeris["duration_hours"],
                    "epoch_definition": ephemeris["epoch_definition"],
                },
            },
            "source": paired["source"],
            "ephemeris_provenance": ephemeris.get("source", {}),
            "selection": paired["selection"],
            "variants": variants,
            "comparison": {
                "sap_minus_pdcsap_depth_ppm": delta,
                "relative_change_percent_of_pdcsap": delta / abs(pdcsap_depth) * 100 if pdcsap_depth else None,
                "sap_to_pdcsap_in_transit_mad_ratio": in_mad_ratio,
                "sap_to_pdcsap_out_of_transit_mad_ratio": out_mad_ratio,
                "sap_depth_assessment": "unreliable_for_depth_inference",
                "sap_depth_assessment_reason": (
                    "Visual inspection of the shared-axis time series and phase fold shows "
                    "large coherent variation; normalized SAP MAD is "
                    f"{in_mad_ratio:.2f}x PDCSAP in transit and {out_mad_ratio:.2f}x out of transit. "
                    "No detrending was applied, so the SAP depth and its KNN ranking are diagnostic only."
                ),
                "interpretation": "Descriptive windowed-median statistic, not a transit-model fit.",
            },
        })

    rankings = []
    for result in results:
        koi_id = result["identity"]["koi_id"]
        query = next(row for row in observations if row.koi_id == koi_id)
        catalogue_depth = float(query.values[2])
        rankings.append({
            "koi_id": koi_id,
            "catalogue_depth_ppm": catalogue_depth,
            "catalogue": rank_with_depth(koi_id, catalogue_depth, observations, training, scaler, scaled_refs),
            "pdcsap_windowed_median_depth": rank_with_depth(
                koi_id, result["variants"]["pdcsap"]["windowed_median_depth_ppm"],
                observations, training, scaler, scaled_refs,
            ),
            "sap_windowed_median_depth": rank_with_depth(
                koi_id, result["variants"]["sap"]["windowed_median_depth_ppm"],
                observations, training, scaler, scaled_refs,
            ),
        })

    report = {
        "schema": "transit-atlas.flux-sensitivity",
        "version": 1,
        "status": "completed",
        "method": {
            "baseline_flux_column": "PDCSAP_FLUX",
            "alternative_flux_column": "SAP_FLUX",
            "quality_column": "SAP_QUALITY",
            "quality_bitmask": DEFAULT_QUALITY_BITMASK,
            "quality_rule": "(quality & quality_bitmask) == 0",
            "paired_cadence_rule": "finite TIME, SAP_FLUX and PDCSAP_FLUX on the same cadence",
            "phase_convention": PHASE_CONVENTION,
            "transit_window": "abs(phase) <= duration_hours / (48 * period_days)",
            "depth_estimator": "1e6 * (median_out - median_in) / median_out",
            "normalization": "separate full-selected-series median for each flux column",
            "flux_columns": {
                "pdcsap": "PDCSAP_FLUX",
                "pdcsap_uncertainty": "PDCSAP_FLUX_ERR",
                "sap": "SAP_FLUX",
                "sap_uncertainty": "SAP_FLUX_ERR",
            },
            "knn": {
                "feature_count": 8,
                "changed_feature": "koi_depth only",
                "reference_pool": "labelled training partition from pinned catalogue snapshot",
                "scaler": "StandardScaler fitted on log-transformed labelled training references",
                "host_exclusion": "exclude query host; also exclude query KOI itself",
                "k": 5,
            },
            "limitations": [
                "Single Q4 product per KOI; not a multi-quarter or leave-one-quarter-out analysis.",
                "Windowed median is descriptive and is not a transit-model fit.",
                "SAP may retain long-term instrumental trends; no detrending is applied.",
                "Only koi_depth is replaced; the other seven catalogue features remain fixed.",
                "A ranking change is not evidence for or against planetary status.",
            ],
        },
        "software": {
            "python": platform.python_version(), "numpy": np.__version__,
            "astropy": astropy_version, "scikit_learn": sklearn.__version__,
            "matplotlib": matplotlib.__version__,
        },
        "catalogue": {
            "manifest_file": str(MANIFEST.relative_to(ROOT)),
            "snapshot_file": str((MANIFEST.parent / catalogue_manifest["file"]).relative_to(ROOT)),
            "snapshot_sha256": catalogue_manifest["sha256"],
            "rows": catalogue_manifest["rows"],
            "training_references": len(training),
            "training_partition": partitions,
            "audit": audit,
            "rejected_rows": len(rejected),
            "features_and_frozen_scaler": scaler_spec,
        },
        "results": results,
        "rankings": rankings,
    }
    plot_path = output_dir / "sap-pdcsap-comparison.png"
    plot_results(results, plot_path)
    report["artifacts"] = {
        "comparison_plot": str(plot_path.relative_to(ROOT)),
        "analysis_json": str((output_dir / "analysis.json").relative_to(ROOT)),
        "report_markdown": str((output_dir / "report.md").relative_to(ROOT)),
    }
    (output_dir / "analysis.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    (output_dir / "report.md").write_text(render_markdown(report), encoding="utf-8")
    return report


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# SAP versus PDCSAP sensitivity results", "",
        "**Status:** completed offline analysis. Measurements are descriptive, not transit-model fits.", "",
        "## Method", "",
        f'- Shared quality mask: {report["method"]["quality_bitmask"]}.',
        "- Both flux columns are read from each same FITS file and restricted to paired finite cadences.",
        "- Both variants use identical cadence IDs, quality flags, ephemeris and transit window.",
        "- KNN substitutes only depth and retains the frozen training scaler and host-excluded pool.", "",
        "## Measurements", "",
        "| KOI | Cadences | PDCSAP depth (ppm) | SAP depth (ppm) | SAP − PDCSAP (ppm) | Relative change | SAP/PDCSAP MAD ratio (in/out) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for result in report["results"]:
        comp = result["comparison"]
        lines.append(
            f'| {result["identity"]["koi_id"]} | {result["selection"]["cadences_used"]} '
            f'| {result["variants"]["pdcsap"]["windowed_median_depth_ppm"]:.4f} '
            f'| {result["variants"]["sap"]["windowed_median_depth_ppm"]:.4f} '
            f'| {comp["sap_minus_pdcsap_depth_ppm"]:.4f} '
            f'| {comp["relative_change_percent_of_pdcsap"]:.2f}% '
            f'| {comp["sap_to_pdcsap_in_transit_mad_ratio"]:.2f}x / '
            f'{comp["sap_to_pdcsap_out_of_transit_mad_ratio"]:.2f}x |'
        )
    lines.extend([
        "",
        "## Scatter and quoted uncertainties",
        "",
        "| KOI | Flux | In-transit MAD (ppm) | Out-of-transit MAD (ppm) | Median uncertainty (ppm) |",
        "| --- | --- | ---: | ---: | ---: |",
    ])
    for result in report["results"]:
        for name in ("pdcsap", "sap"):
            variant = result["variants"][name]
            lines.append(
                f'| {result["identity"]["koi_id"]} | {name.upper()} '
                f'| {variant["in_transit_relative_flux_ppm"]["mad"]:.2f} '
                f'| {variant["out_of_transit_relative_flux_ppm"]["mad"]:.2f} '
                f'| {variant["valid_uncertainty_ppm"]["median"]:.2f} |'
            )
    lines.extend(["", "## KNN ranking sensitivity", ""])
    for ranking in report["rankings"]:
        lines.extend([
            f'### {ranking["koi_id"]}', "",
            f'Catalogue depth: {ranking["catalogue_depth_ppm"]:.4f} ppm.', "",
            "| Depth input | Top five KOIs (distance; depth squared contribution) |",
            "| --- | --- |",
        ])
        for label, key in (
            ("Catalogue", "catalogue"),
            ("PDCSAP measured", "pdcsap_windowed_median_depth"),
            ("SAP diagnostic (unreliable)", "sap_windowed_median_depth"),
        ):
            item = ranking[key]
            if item["available"]:
                value = "; ".join(
                    f'{n["koi_id"]} ({n["distance"]:.5f}; {n["depth_squared_contribution"]:.5f})'
                    for n in item["neighbours"]
                )
            else:
                value = f'Unavailable: {item["reason"]}'
            lines.append(f"| {label} | {value} |")
        lines.append("")
    lines.extend([
        "## Interpretation and limitations", "",
        "The SAP series is visibly dominated by large coherent variation in both targets. Its normalized in-transit/out-of-transit MAD is 6.46x/6.56x PDCSAP for K00115.03 and 8.00x/7.43x for K02961.01. The SAP windowed-median depths and corresponding rankings are therefore retained as diagnostics only and are not reliable transit-depth estimates. No detrending or transit model was introduced. PDCSAP measurements are also descriptive windowed medians, not validated physical transit fits.",
        "",
        "Only one Q4 product per KOI was analysed. The result does not establish multi-quarter repeatability or generalisation to other targets.", "",
        "## Reproducibility", "",
        "Run from the repository root:", "",
        "    .venv/bin/python reference/flux_sensitivity.py",
        "    .venv/bin/python -m unittest reference.test_flux_sensitivity", "",
        f'Python {report["software"]["python"]}; NumPy {report["software"]["numpy"]}; Astropy {report["software"]["astropy"]}; scikit-learn {report["software"]["scikit_learn"]}; Matplotlib {report["software"]["matplotlib"]}.',
        "",
        "Machine-readable cadence series, FITS SHA-256 values, selection counts, scaler parameters and full top-five distance evidence are in analysis.json.", "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    try:
        report = run_analysis(args.output_dir)
    except (OSError, ValueError, KeyError, StopIteration) as error:
        print(f"Flux sensitivity analysis failed: {error}", file=sys.stderr)
        return 1
    for result in report["results"]:
        print(
            f'{result["identity"]["koi_id"]}: '
            f'PDCSAP={result["variants"]["pdcsap"]["windowed_median_depth_ppm"]:.4f} ppm; '
            f'SAP={result["variants"]["sap"]["windowed_median_depth_ppm"]:.4f} ppm'
        )
    print("Wrote analysis.json, report.md and sap-pdcsap-comparison.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
