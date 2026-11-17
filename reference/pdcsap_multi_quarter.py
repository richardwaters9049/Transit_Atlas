"""Offline Q0-Q17 validation of PDCSAP detrending and transit preservation."""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import scipy
from astropy import __version__ as astropy_version
from astropy.io import fits

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/raw/kepler-multi-quarter-products-2026-11-17.json"
EPHEMERIS = ROOT / "data/raw/kepler-lightcurve-ephemerides-2026-11-15.json"
OUTPUT = ROOT / "data/generated/pdcsap-multi-quarter"
sys.path.insert(0, str(ROOT / "reference"))
from kepler_lightcurve import DEFAULT_QUALITY_BITMASK  # noqa: E402
from pdcsap_detrending import (  # noqa: E402
    ephemeris_mask, estimate_trend, flatten, folded_shape_profile, mad,
    protected_injection_train, split_segments, valid_injection_epochs, window_depth,
)

WINDOWS = (101, 201)
CONFIGS = tuple((mode, window) for window in WINDOWS for mode in ("unmasked", "transit_masked"))
DEPTH_MULTIPLIERS = (0.5, 1.0, 2.0)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_quarter(product: dict[str, Any], expected_host: int) -> dict[str, Any]:
    path = ROOT / product["relative_path"]
    actual_hash = sha256(path)
    if actual_hash != product["sha256"]:
        raise ValueError(f"SHA-256 mismatch for {path}")
    with fits.open(path, memmap=True) as hdul:
        primary, hdu = hdul[0].header, hdul[1]
        header, data = hdu.header, hdu.data
        expected = (expected_host, int(product["quarter"]), 25)
        actual = (int(header.get("KEPLERID", primary.get("KEPLERID", -1))),
                  int(header.get("QUARTER", primary.get("QUARTER", -1))),
                  int(header.get("DATA_REL", primary.get("DATA_REL", -1))))
        if actual != expected:
            raise ValueError(f"{path.name}: expected KIC/Q/DR {expected}, got {actual}")
        if str(header.get("TIMESYS", "")) != "TDB" or str(header.get("TIMEUNIT", "")) != "d" or int(header.get("BJDREFI", -1)) != 2454833:
            raise ValueError(f"{path.name}: unexpected Kepler time convention")
        required = {"TIME", "CADENCENO", "SAP_QUALITY", "PDCSAP_FLUX", "PDCSAP_FLUX_ERR"}
        missing = required - set(hdu.columns.names or ())
        if missing:
            raise ValueError(f"{path.name}: missing {sorted(missing)}")
        time = np.asarray(data["TIME"], dtype=float)
        cadence = np.asarray(data["CADENCENO"], dtype=np.int64)
        quality = np.asarray(data["SAP_QUALITY"], dtype=np.int64)
        flux = np.asarray(data["PDCSAP_FLUX"], dtype=float)
        error = np.asarray(data["PDCSAP_FLUX_ERR"], dtype=float)
        procver = str(primary.get("PROCVER", ""))
    quality_ok = (quality & DEFAULT_QUALITY_BITMASK) == 0
    finite = np.isfinite(time) & np.isfinite(flux)
    selected = quality_ok & finite
    counts = {"raw": len(time), "quality_accepted": int(quality_ok.sum()),
              "quality_rejected": int((~quality_ok).sum()),
              "invalid_after_quality": int((quality_ok & ~finite).sum()),
              "used": int(selected.sum())}
    time, cadence, flux, error = time[selected], cadence[selected], flux[selected], error[selected]
    order = np.argsort(time)
    time, cadence, flux, error = time[order], cadence[order], flux[order], error[order]
    if len(time) < 250 or len(np.unique(cadence)) != len(cadence) or np.any(np.diff(time) <= 0):
        raise ValueError(f"{path.name}: insufficient or non-unique selected cadence data")
    return {"path": path, "time": time, "cadence": cadence, "flux": flux, "error": error,
            "counts": counts, "procver": procver, "segments": split_segments(time)}


def analyse_quarter(target: dict[str, Any], product: dict[str, Any], ephemeris: dict[str, Any], depth_ppm: float) -> dict[str, Any]:
    data = read_quarter(product, int(target["host_id"]))
    time, flux, error = data["time"], data["flux"], data["error"]
    period, epoch, duration = (float(ephemeris[k]) for k in ("koi_period", "koi_time0bk", "koi_duration"))
    period_err = max(abs(float(ephemeris.get("koi_period_err1") or 0)), abs(float(ephemeris.get("koi_period_err2") or 0)))
    epoch_err = max(abs(float(ephemeris.get("koi_time0bk_err1") or 0)), abs(float(ephemeris.get("koi_time0bk_err2") or 0)))
    midpoint = float((time.min() + time.max()) / 2)
    cycles = int(round((midpoint - epoch) / period))
    propagated_hours = float(np.hypot(epoch_err, cycles * period_err) * 24)
    real_mask = ephemeris_mask(time, period, epoch, duration, period_err, epoch_err)
    baseline = window_depth(time, flux, period, epoch, duration)
    baseline_shape = folded_shape_profile(time, flux, period, epoch, duration)
    spacing = float(np.median(np.diff(time)))
    configs: dict[str, dict[str, Any]] = {}
    for mode, window in CONFIGS:
        name = f"{mode}_{window}"
        excluded = real_mask if mode == "transit_masked" else np.zeros(len(time), dtype=bool)
        try:
            trend = estimate_trend(time, flux, excluded, window)
        except ValueError as exc:
            configs[name] = {"mode": mode, "window_cadences": window,
                "status": "unsupported_segment_length_or_mask_coverage", "reason": str(exc)}
            continue
        flat_flux, flat_error = flatten(flux, error, trend)
        depth = window_depth(time, flat_flux, period, epoch, duration)
        shape = folded_shape_profile(time, flat_flux, period, epoch, duration)
        configs[name] = {"mode": mode, "window_cadences": window, "status": "supported",
            "window_nominal_days": window * spacing, "depth": depth,
            "depth_change_fraction": float((depth["depth_ppm"] - baseline["depth_ppm"]) / abs(baseline["depth_ppm"])) if baseline["depth_ppm"] else None,
            "shape_width_ratio": float(shape["half_depth_width_duration_units"] / baseline_shape["half_depth_width_duration_units"]) if baseline_shape["half_depth_width_duration_units"] else None,
            "out_mad_ppm": depth["out_mad_ppm"],
            "mad_improvement_percent": float((baseline["out_mad_ppm"] - depth["out_mad_ppm"]) / baseline["out_mad_ppm"] * 100) if baseline["out_mad_ppm"] else 0.0,
            "trend_min": float(trend.min()), "trend_max": float(trend.max()),
            "uncertainty_median_before": float(np.nanmedian(error)),
            "uncertainty_median_after": float(np.nanmedian(flat_error)),
            "uncertainty_mad_after": mad(flat_error),
            "masked_cadences": int(excluded.sum()), "shape_profile": shape,
            "_trend": trend, "_flux": flat_flux, "_error": flat_error}

    offsets = valid_injection_epochs(time, real_mask, period, epoch, duration)
    injection_rows: list[dict[str, Any]] = []
    for multiplier in DEPTH_MULTIPLIERS:
        depth = depth_ppm * multiplier / 1e6
        for offset, injected_epoch in offsets:
            injected_model, injection_mask, accepted, skipped = protected_injection_train(
                time, period, injected_epoch, duration, depth, real_mask)
            paired_base = flux.copy()
            paired_injected = flux * injected_model
            for name, config in configs.items():
                if config.get("status") != "supported":
                    continue
                window = int(config["window_cadences"])
                masked = config["mode"] == "transit_masked"
                base_excluded = real_mask if masked else np.zeros(len(time), dtype=bool)
                injected_excluded = (real_mask | injection_mask) if masked else np.zeros(len(time), dtype=bool)
                base_trend = estimate_trend(time, paired_base, base_excluded, window)
                injected_trend = estimate_trend(time, paired_injected, injected_excluded, window)
                base_flat, _ = flatten(paired_base, error, base_trend)
                injected_flat, _ = flatten(paired_injected, error, injected_trend)
                delta = injected_flat / base_flat - 1.0
                inside, outside = injection_mask, ~injection_mask
                recovered = 1e6 * (float(np.median(delta[outside])) - float(np.median(delta[inside])))
                ratio = recovered / (depth_ppm * multiplier)
                null_depth = window_depth(time, base_flat, period, injected_epoch, duration)["depth_ppm"]
                injection_rows.append({"phase_offset_fraction": offset, "injected_epoch_bkjd": injected_epoch,
                    "depth_multiplier": multiplier, "configuration": name,
                    "injected_depth_ppm": depth_ppm * multiplier, "recovered_depth_ppm": recovered,
                    "recovery_ratio": ratio, "null_control_depth_ppm": null_depth,
                    "accepted_events": accepted, "skipped_gap_or_overlap_events": skipped,
                    "overlap_with_real_transit_mask": bool(np.any(injection_mask & real_mask))})
    for name, config in configs.items():
        if config.get("status") != "supported":
            continue
        for multiplier in DEPTH_MULTIPLIERS:
            vals = np.array([x["recovery_ratio"] for x in injection_rows if x["configuration"] == name and x["depth_multiplier"] == multiplier])
            config.setdefault("injection_recovery", {})[str(multiplier)] = {
                "count": int(len(vals)), "median_ratio": float(np.median(vals)),
                "iqr_ratio": float(np.percentile(vals, 75) - np.percentile(vals, 25)),
                "minimum_ratio": float(vals.min()), "maximum_ratio": float(vals.max())}
        nulls = np.array([x["null_control_depth_ppm"] for x in injection_rows if x["configuration"] == name])
        config["null_control"] = {"count": len(nulls), "median_depth_ppm": float(np.median(nulls)), "mad_depth_ppm": mad(nulls)}
        config.pop("_trend"); config.pop("_flux"); config.pop("_error")
    return {"identity": {"koi_id": target["koi_id"], "host_id": target["host_id"],
                "quarter": int(product["quarter"]), "data_release": 25},
        "source": {"filename": product["filename"], "relative_path": product["relative_path"],
            "data_uri": product["data_uri"], "sha256": product["sha256"], "bytes": product["bytes"],
            "pipeline_version": data["procver"]},
        "selection": data["counts"],
        "cadence": {"count": len(time), "time_start_bkjd": float(time.min()),
            "time_end_bkjd": float(time.max()), "median_spacing_days": spacing,
            "segment_lengths": [len(x) for x in data["segments"]],
            "gap_threshold_days": spacing * 5, "real_transit_mask_cadences": int(real_mask.sum())},
        "ephemeris": {"period_days": period, "epoch_bkjd": epoch, "duration_hours": duration,
            "period_uncertainty_days": period_err, "epoch_uncertainty_days": epoch_err,
            "cycles_from_epoch": cycles, "propagated_uncertainty_hours": propagated_hours,
            "uncertainty_fraction_of_duration": propagated_hours / duration,
            "ephemeris_limited": propagated_hours > duration / 2},
        "baseline": {"depth": baseline, "out_mad_ppm": baseline["out_mad_ppm"],
            "shape_profile": baseline_shape},
        "configurations": configs, "injections": injection_rows}


def summarise_decisions(targets: list[dict[str, Any]]) -> dict[str, Any]:
    decisions = {}
    for name in (f"{mode}_{window}" for window in WINDOWS for mode in ("unmasked", "transit_masked")):
        per_target = []
        for target in targets:
            quarters = target["quarters"]
            evaluable = [q for q in quarters if not q["ephemeris"]["ephemeris_limited"] and q["configurations"].get(name, {}).get("status") == "supported"]
            depth_pass = sum(abs(q["configurations"][name]["depth_change_fraction"] or 0) <= .10 for q in evaluable)
            depth_no_large_excursion = all(abs(q["configurations"][name]["depth_change_fraction"] or 0) <= .20 for q in evaluable)
            width_pass = sum(q["configurations"][name]["shape_width_ratio"] is not None and .90 <= q["configurations"][name]["shape_width_ratio"] <= 1.10 for q in evaluable)
            recovery_pass = all(.90 <= q["configurations"][name]["injection_recovery"][str(m)]["median_ratio"] <= 1.10 and q["configurations"][name]["injection_recovery"][str(m)]["iqr_ratio"] <= .20 for q in evaluable for m in DEPTH_MULTIPLIERS)
            improvements = [q["configurations"][name]["mad_improvement_percent"] for q in evaluable]
            per_target.append({"koi_id": target["identity"]["koi_id"], "evaluable_quarters": len(evaluable),
                "total_quarters": len(quarters), "depth_within_10pct": depth_pass,
                "depth_fraction": depth_pass / len(evaluable) if evaluable else None,
                "no_depth_excursion_over_20pct": depth_no_large_excursion,
                "shape_width_within_10pct": width_pass,
                "shape_fraction": width_pass / len(evaluable) if evaluable else None,
                "all_evaluable_injection_recoveries_pass": recovery_pass,
                "median_mad_improvement_percent": float(np.median(improvements)) if improvements else None})
        both_pass = all(row["evaluable_quarters"] >= 15 and row["depth_fraction"] is not None and row["depth_fraction"] >= .90 and row["no_depth_excursion_over_20pct"] and row["shape_fraction"] is not None and row["shape_fraction"] >= .90 and row["all_evaluable_injection_recoveries_pass"] for row in per_target)
        scatter = [row["median_mad_improvement_percent"] for row in per_target if row["median_mad_improvement_percent"] is not None]
        scatter_pass = len(scatter) == 2 and max(scatter) >= 5 and min(scatter) >= -5
        decisions[name] = {"targets": per_target, "scatter_criteria_pass": scatter_pass, "eligible": both_pass and scatter_pass}
    eligible = [name for name, result in decisions.items() if result["eligible"]]
    return {"eligible_configurations": eligible, "assessments": decisions,
        "conclusion": "No tested configuration meets the multi-quarter preservation criteria; retain unflattened PDCSAP as the application baseline." if not eligible else "One or more configurations meet the engineering screens; independent validation with more targets is still required."}


def make_plot(target: dict[str, Any], path: Path) -> None:
    quarters = target["quarters"]
    x = [q["identity"]["quarter"] for q in quarters]
    fig, axes = plt.subplots(3, 1, figsize=(14, 12), constrained_layout=True)
    axes[0].plot(x, [q["baseline"]["depth"]["depth_ppm"] for q in quarters], marker="o", label="Unflattened PDCSAP")
    axes[0].set_ylabel("Windowed depth (ppm)"); axes[0].set_title(target["identity"]["koi_id"] + " — per-quarter baseline depth")
    for name in ("unmasked_101", "transit_masked_101", "unmasked_201", "transit_masked_201"):
        axes[1].plot(x, [q["configurations"][name].get("depth_change_fraction", None) * 100 if q["configurations"][name].get("status") == "supported" else None for q in quarters], marker=".", label=name)
    axes[1].axhline(10, linestyle="--"); axes[1].axhline(-10, linestyle="--")
    axes[1].set_ylabel("Depth change (%)"); axes[1].set_title("Derived depth change from each quarter's PDCSAP control"); axes[1].legend(ncol=2)
    for name in ("unmasked_101", "transit_masked_101", "unmasked_201", "transit_masked_201"):
        axes[2].plot(x, [q["configurations"][name].get("mad_improvement_percent") if q["configurations"][name].get("status") == "supported" else None for q in quarters], marker=".", label=name)
    axes[2].axhline(5, linestyle="--"); axes[2].set_xlabel("Kepler quarter"); axes[2].set_ylabel("OOT MAD improvement (%)"); axes[2].set_title("Scatter reduction by quarter")
    fig.savefig(path, dpi=150); plt.close(fig)


def render_report(report: dict[str, Any]) -> str:
    lines = ["# Multi-quarter PDCSAP validation results", "",
        f'**Decision:** {report["decision"]["conclusion"]}', "",
        "The 36 DR25 long-cadence products are processed independently by quarter. The same pinned NASA Exoplanet Archive ephemerides are used throughout; propagated timing uncertainty is reported and ephemeris-limited quarters are not counted as clean preservation successes.", "",
        "## Target-quarter results", ""]
    for target in report["targets"]:
        lines += [f'### {target["identity"]["koi_id"]} — {target["identity"]["role"]}', "",
            "| Q | Cadences | Segments | Ephemeris σ (h) | Baseline depth (ppm) | Baseline OOT MAD (ppm) |", "|---:|---:|---:|---:|---:|---:|"]
        for q in target["quarters"]:
            lines.append(f'| {q["identity"]["quarter"]} | {q["selection"]["used"]} | {len(q["cadence"]["segment_lengths"])} | {q["ephemeris"]["propagated_uncertainty_hours"]:.3f} | {q["baseline"]["depth"]["depth_ppm"]:.3f} | {q["baseline"]["out_mad_ppm"]:.3f} |')
        lines += ["", "| Configuration | Median depth change | Quarters within 10% | Median OOT MAD improvement | Injection recovery pass across quarters |", "|---|---:|---:|---:|---|"]
        for name in (f"{m}_{w}" for w in WINDOWS for m in ("unmasked", "transit_masked")):
            evaluable = [q for q in target["quarters"] if not q["ephemeris"]["ephemeris_limited"] and q["configurations"][name].get("status") == "supported"]
            changes = [q["configurations"][name]["depth_change_fraction"] * 100 for q in evaluable]
            improvements = [q["configurations"][name]["mad_improvement_percent"] for q in evaluable]
            passed = len(evaluable) >= 15 and all(.90 <= q["configurations"][name]["injection_recovery"][str(m)]["median_ratio"] <= 1.10 and q["configurations"][name]["injection_recovery"][str(m)]["iqr_ratio"] <= .20 for q in evaluable for m in DEPTH_MULTIPLIERS)
            lines.append(f'| {name} | {np.median(changes):.2f}% | {sum(abs(v)<=10 for v in changes)}/{len(changes)} | {np.median(improvements):.2f}% | {"pass" if passed else "fail / insufficient"} |')
        lines.append("")
    lines += ["## Decision details", "", "The decision rules and their engineering (non-universal) status are defined in [the protocol](../../docs/pdcsap-multi-quarter-validation.md). Q0–Q17 are independent quarter-level units; cadences and injection offsets are not treated as independent target replications. The trapezoidal injections are recovery probes, not physical transit models. No application default, catalogue feature, scaler or KNN ranking is changed.", ""]
    return "\n".join(lines)


def run(output_dir: Path = OUTPUT) -> dict[str, Any]:
    manifest = json.loads(MANIFEST.read_text())
    ephemerides = json.loads(EPHEMERIS.read_text())
    ephem = {row["kepoi_name"]: row for row in ephemerides["rows"]}
    catalogue = json.loads((ROOT / "data/generated/catalogue.json").read_text())
    signals = {row["koi_id"]: row for row in catalogue["observations"]}
    targets = []
    for source_target in manifest["targets"]:
        koi = source_target["koi_id"]
        target = {"koi_id": koi, "host_id": source_target["host_id"],
                  "role": "candidate" if ephem[koi]["koi_disposition"] == "CANDIDATE" else "reference"}
        quarters = [analyse_quarter(target, product, ephem[koi], float(signals[koi]["values"][2])) for product in source_target["quarters"]]
        targets.append({"identity": target, "quarters": quarters})
    decision = summarise_decisions(targets)
    output_dir.mkdir(parents=True, exist_ok=True)
    for target in targets:
        plot = output_dir / f'{target["identity"]["koi_id"]}-quarter-summary.png'
        make_plot(target, plot)
        target["plot"] = str(plot.relative_to(ROOT))
    report = {"schema": "transit-atlas.pdcsap-multi-quarter", "version": 1,
        "status": "completed", "decision": decision,
        "method": {"flux_column": "PDCSAP_FLUX", "error_column": "PDCSAP_FLUX_ERR",
            "quality_bitmask": DEFAULT_QUALITY_BITMASK, "windows": list(WINDOWS), "polyorder": 2,
            "modes": ["unmasked", "transit_masked"], "gap_factor": 5,
            "injection_depth_multipliers": list(DEPTH_MULTIPLIERS), "injections_per_depth_per_quarter": 12,
            "ephemeris_uncertainty_rule": "sqrt(epoch_err^2 + (cycle * period_err)^2)",
            "quarter_handling": "independent; no stitching, gap filling or cross-quarter smoothing"},
        "software": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__, "astropy": astropy_version, "matplotlib": matplotlib.__version__},
        "source_manifest": {"file": str(MANIFEST.relative_to(ROOT)), "sha256": sha256(MANIFEST), "product_count": sum(len(t["quarters"]) for t in manifest["targets"])},
        "ephemeris_source": {"file": str(EPHEMERIS.relative_to(ROOT)), "sha256": sha256(EPHEMERIS), "retrieved_at_utc": ephemerides["retrieved_at_utc"]},
        "targets": targets}
    (output_dir / "analysis.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    (output_dir / "report.md").write_text(render_report(report))
    return report


if __name__ == "__main__":
    result = run()
    print("Analysed", result["source_manifest"]["product_count"], "quarter products")
    print(result["decision"]["conclusion"])
