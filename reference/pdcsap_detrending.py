"""Offline PDCSAP detrending and deterministic transit injection/recovery study."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import scipy
from astropy import __version__ as astropy_version
from astropy.io import fits
from scipy.signal import savgol_filter

from kepler_lightcurve import DEFAULT_QUALITY_BITMASK

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data/raw/kepler-lightcurves"
EPHEMERIS_FILE = ROOT / "data/raw/kepler-lightcurve-ephemerides-2026-11-15.json"
OUTPUT_DIR = ROOT / "data/generated/pdcsap-detrending"
TARGETS = (
    {"koi_id": "K00115.03", "host_id": 9579641, "role": "candidate"},
    {"koi_id": "K02961.01", "host_id": 10471515, "role": "reference"},
)
WINDOWS = (101, 201, 401)
POLYORDER = 2
INJECTION_OFFSETS = 48
INJECTIONS_PER_DEPTH = 12


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def mad(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if not values.size:
        return float("nan")
    median = np.median(values)
    return float(np.median(np.abs(values - median)))


def read_product(path: Path, host_id: int) -> dict[str, Any]:
    with fits.open(path, memmap=True) as hdul:
        primary, hdu = hdul[0].header, hdul[1]
        data = hdu.data
        names = set(hdu.columns.names or ())
        required = {"TIME", "CADENCENO", "SAP_QUALITY", "PDCSAP_FLUX", "PDCSAP_FLUX_ERR"}
        missing = sorted(required - names)
        if missing:
            raise ValueError(f"Missing FITS columns: {', '.join(missing)}")
        header = hdu.header
        if int(header.get("KEPLERID", primary.get("KEPLERID", host_id))) != host_id or int(header.get("QUARTER", primary.get("QUARTER", 4))) != 4 or int(header.get("DATA_REL", primary.get("DATA_REL", 25))) != 25:
            raise ValueError(f"Unexpected target/quarter/release in {path.name}")
        time = np.asarray(data["TIME"], dtype=float)
        cadence = np.asarray(data["CADENCENO"], dtype=np.int64)
        quality = np.asarray(data["SAP_QUALITY"], dtype=np.int64)
        flux = np.asarray(data["PDCSAP_FLUX"], dtype=float)
        error = np.asarray(data["PDCSAP_FLUX_ERR"], dtype=float)
        meta = {"timesys": header.get("TIMESYS"), "timeunit": header.get("TIMEUNIT"), "bjdrefi": header.get("BJDREFI"), "procver": primary.get("PROCVER")}
    selected = ((quality & DEFAULT_QUALITY_BITMASK) == 0) & np.isfinite(time) & np.isfinite(flux)
    time, cadence, flux, error = time[selected], cadence[selected], flux[selected], error[selected]
    order = np.argsort(time)
    time, cadence, flux, error = time[order], cadence[order], flux[order], error[order]
    if len(np.unique(cadence)) != len(cadence) or np.any(np.diff(time) <= 0):
        raise ValueError("Selected cadence identity/time must be unique and strictly increasing")
    return {"time": time, "cadence": cadence, "flux": flux, "error": error,
            "selection": {"raw": int(len(selected)), "used": int(selected.sum()), "quality_bitmask": DEFAULT_QUALITY_BITMASK},
            "source": {"filename": path.name, "sha256": sha256_file(path), "bytes": path.stat().st_size, **meta}}


def split_segments(time: np.ndarray, gap_factor: float = 5.0) -> list[np.ndarray]:
    if len(time) < 3:
        raise ValueError("At least three timestamps are required")
    spacing = np.diff(time)
    median_spacing = float(np.median(spacing[spacing > 0]))
    breaks = np.flatnonzero(spacing > gap_factor * median_spacing) + 1
    return [part for part in np.split(np.arange(len(time)), breaks) if len(part)]


def ephemeris_mask(time: np.ndarray, period: float, epoch: float, duration_hours: float,
                   period_err: float, epoch_err: float, padding: float = 1.5) -> np.ndarray:
    cycles = np.rint((time - epoch) / period).astype(int)
    centres = epoch + cycles * period
    propagated = np.sqrt(epoch_err**2 + (cycles * period_err)**2)
    half_width = padding * duration_hours / 48.0 + propagated
    return np.abs(time - centres) <= half_width


def trapezoid_train(time: np.ndarray, period: float, epoch: float, duration_hours: float,
                    depth: float, ingress_fraction: float = 0.15) -> tuple[np.ndarray, np.ndarray]:
    phase_days = ((time - epoch + period / 2) % period) - period / 2
    half = duration_hours / 48.0
    ingress = half * ingress_fraction
    distance = np.abs(phase_days)
    profile = np.zeros(len(time), dtype=float)
    flat = distance <= half - ingress
    slope = (distance > half - ingress) & (distance <= half)
    profile[flat] = 1.0
    profile[slope] = (half - distance[slope]) / ingress
    return 1.0 - depth * profile, profile > 0


def estimate_trend(time: np.ndarray, flux: np.ndarray, excluded: np.ndarray,
                   window: int, polyorder: int = POLYORDER) -> np.ndarray:
    if len(time) != len(flux) or len(time) != len(excluded):
        raise ValueError("Trend inputs must have identical cadence lengths")
    if window % 2 != 1 or window <= polyorder:
        raise ValueError("Savitzky-Golay window must be odd and exceed polynomial order")
    trend = np.full(len(flux), np.nan, dtype=float)
    for segment in split_segments(time):
        if len(segment) < window:
            raise ValueError(f"Segment of {len(segment)} cadences is shorter than window {window}")
        local_flux = flux[segment]
        local_excluded = excluded[segment]
        x = np.arange(len(segment))
        valid = ~local_excluded & np.isfinite(local_flux)
        if valid.sum() < window:
            raise ValueError("Too few unmasked cadences to estimate trend in a segment")
        interpolated = np.interp(x, x[valid], local_flux[valid])
        trend[segment] = savgol_filter(interpolated, window_length=window, polyorder=polyorder, mode="interp")
    if not np.all(np.isfinite(trend)) or np.any(trend <= 0):
        raise ValueError("Trend contains non-finite or non-positive values")
    return trend


def flatten(flux: np.ndarray, error: np.ndarray, trend: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if not np.all(np.isfinite(trend)) or np.any(trend <= 0):
        raise ValueError("Trend must be finite and positive")
    return flux / trend, error / trend


def window_depth(time: np.ndarray, flux: np.ndarray, period: float, epoch: float,
                 duration_hours: float) -> dict[str, float | int]:
    phase = ((time - epoch + period / 2) % period) / period - 0.5
    inside = np.abs(phase) <= duration_hours / (48 * period)
    outside = ~inside
    if not inside.any() or not outside.any():
        raise ValueError("Depth window has no in-transit or out-of-transit cadences")
    med_in, med_out = float(np.median(flux[inside])), float(np.median(flux[outside]))
    return {"depth_ppm": 1e6 * (med_out - med_in) / med_out,
            "in_count": int(inside.sum()), "out_count": int(outside.sum()),
            "in_mad_ppm": mad((flux[inside] / np.median(flux) - 1) * 1e6),
            "out_mad_ppm": mad((flux[outside] / np.median(flux) - 1) * 1e6)}


def folded_shape_profile(time: np.ndarray, flux: np.ndarray, period: float, epoch: float,
                         duration_hours: float, bins: int = 31) -> dict[str, Any]:
    """Median folded profile in duration-scaled phase bins around the real transit."""
    phase_days = ((time - epoch + period / 2) % period) - period / 2
    scaled = phase_days / (duration_hours / 24.0)
    edges = np.linspace(-1.5, 1.5, bins + 1)
    baseline = float(np.median(flux[np.abs(scaled) > 0.75]))
    centres, values, counts = [], [], []
    for left, right in zip(edges[:-1], edges[1:]):
        selected = (scaled >= left) & (scaled < right)
        centres.append(float((left + right) / 2))
        counts.append(int(selected.sum()))
        values.append(float(np.median(flux[selected]) / baseline) if selected.any() else None)
    finite = [(x, y) for x, y in zip(centres, values) if y is not None]
    depth = 1.0 - min((y for _, y in finite), default=1.0)
    half_level = 1.0 - depth / 2.0
    below = [x for x, y in finite if y <= half_level]
    width = max(below) - min(below) if len(below) >= 2 else 0.0
    return {"phase_duration_units": centres, "relative_flux": values, "counts": counts,
            "half_depth_width_duration_units": float(width),
            "minimum_relative_flux": float(min((y for _, y in finite), default=1.0))}


def protected_injection_train(time: np.ndarray, period: float, epoch: float,
                              duration_hours: float, depth: float,
                              real_mask: np.ndarray) -> tuple[np.ndarray, np.ndarray, int, int]:
    """Inject only complete transit windows clear of real transits and major gaps."""
    half = duration_hours / 48.0
    spacing = np.diff(time)
    median_spacing = float(np.median(spacing[spacing > 0]))
    gap_indices = np.flatnonzero(spacing > 5.0 * median_spacing)
    gaps = [(float(time[i]), float(time[i + 1])) for i in gap_indices]
    cycles = np.arange(int(np.floor((time.min() - epoch) / period)) - 1,
                       int(np.ceil((time.max() - epoch) / period)) + 2)
    profile = np.zeros(len(time), dtype=float)
    mask = np.zeros(len(time), dtype=bool)
    accepted_events = skipped_events = 0
    ingress = half * 0.15
    for cycle in cycles:
        centre = epoch + int(cycle) * period
        if any(centre + half >= left and centre - half <= right for left, right in gaps):
            skipped_events += 1
            continue
        local = np.abs(time - centre) <= half
        if not local.any() or np.any(local & real_mask):
            skipped_events += 1
            continue
        distance = np.abs(time[local] - centre)
        local_profile = np.zeros(int(local.sum()), dtype=float)
        local_profile[distance <= half - ingress] = 1.0
        slope = (distance > half - ingress) & (distance <= half)
        local_profile[slope] = (half - distance[slope]) / ingress
        profile[local] = np.maximum(profile[local], local_profile)
        mask[local] |= local_profile > 0
        accepted_events += 1
    return 1.0 - depth * profile, mask, accepted_events, skipped_events


def valid_injection_epochs(time: np.ndarray, real_mask: np.ndarray, period: float,
                           epoch: float, duration_hours: float) -> list[tuple[float, float]]:
    offsets = np.arange(INJECTION_OFFSETS, dtype=float) / INJECTION_OFFSETS
    result = []
    for offset in offsets:
        injected_epoch = epoch + float(offset) * period
        _, mask, accepted, _ = protected_injection_train(
            time, period, injected_epoch, duration_hours, 1e-3, real_mask
        )
        if mask.any() and accepted >= 2:
            result.append((float(offset), injected_epoch))
    if len(result) < INJECTIONS_PER_DEPTH:
        raise ValueError(f"Only {len(result)} valid phase offsets; {INJECTIONS_PER_DEPTH} required")
    positions = np.linspace(0, len(result) - 1, INJECTIONS_PER_DEPTH).round().astype(int)
    return [result[i] for i in positions]


def run_target(target: dict[str, Any], ephemeris: dict[str, Any]) -> dict[str, Any]:
    koi = target["koi_id"]
    product = read_product(RAW_DIR / f"{koi}-q04.fits", target["host_id"])
    time, cadence = product["time"], product["cadence"]
    flux, error = product["flux"], product["error"]
    period, epoch, duration = (float(ephemeris[k]) for k in ("koi_period", "koi_time0bk", "koi_duration"))
    period_err = max(abs(float(ephemeris.get("koi_period_err1") or 0)), abs(float(ephemeris.get("koi_period_err2") or 0)))
    epoch_err = max(abs(float(ephemeris.get("koi_time0bk_err1") or 0)), abs(float(ephemeris.get("koi_time0bk_err2") or 0)))
    real_mask = ephemeris_mask(time, period, epoch, duration, period_err, epoch_err)
    segments = split_segments(time)
    spacing = float(np.median(np.diff(time)))
    configs = [{"mode": mode, "window": window} for window in WINDOWS for mode in ("unmasked", "transit_masked")]
    configurations = {}
    for config in configs:
        mode, window = config["mode"], config["window"]
        excluded = np.zeros(len(time), dtype=bool) if mode == "unmasked" else real_mask.copy()
        trend = estimate_trend(time, flux, excluded, window)
        flat_flux, flat_error = flatten(flux, error, trend)
        configurations[f"{mode}_{window}"] = {
            "mode": mode, "window_cadences": window, "window_nominal_days": window * spacing,
            "trend": trend, "flux": flat_flux, "error": flat_error,
            "real_depth": window_depth(time, flat_flux, period, epoch, duration),
            "out_mad_ppm": window_depth(time, flat_flux, period, epoch, duration)["out_mad_ppm"],
            "trend_min": float(trend.min()), "trend_max": float(trend.max()),
            "masked_cadences": int(excluded.sum()),
        }
    baseline_depth = window_depth(time, flux, period, epoch, duration)
    baseline_shape = folded_shape_profile(time, flux, period, epoch, duration)
    baseline_scatter = baseline_depth["out_mad_ppm"]

    injection_offsets = valid_injection_epochs(time, real_mask, period, epoch, duration)
    catalogue_depth = float(ephemeris["catalogue_depth_ppm"])
    injection_ledger = []
    recovery_summary = {}
    null_summary: dict[str, list[float]] = {name: [] for name in configurations}
    for multiplier in (0.5, 1.0, 2.0):
        depth = catalogue_depth * multiplier / 1e6
        recoveries: dict[str, list[float]] = {name: [] for name in configurations}
        for offset, injected_epoch in injection_offsets:
            injected_flux, injected_mask, accepted_events, skipped_events = protected_injection_train(
                time, period, injected_epoch, duration, depth, real_mask
            )
            paired_no_injection = flux.copy()
            paired_injection = flux * injected_flux
            for name, config in configurations.items():
                window = config["window_cadences"]
                mode = config["mode"]
                # Re-estimate each trend on its own paired series; injection masks are added only for masked mode.
                no_excluded = real_mask.copy() if mode == "transit_masked" else np.zeros(len(time), dtype=bool)
                inj_excluded = (real_mask | injected_mask) if mode == "transit_masked" else np.zeros(len(time), dtype=bool)
                no_trend = estimate_trend(time, paired_no_injection, no_excluded, window)
                inj_trend = estimate_trend(time, paired_injection, inj_excluded, window)
                no_flat, _ = flatten(paired_no_injection, error, no_trend)
                inj_flat, _ = flatten(paired_injection, error, inj_trend)
                null_depth = window_depth(time, no_flat, period, injected_epoch, duration)["depth_ppm"]
                null_summary[name].append(float(null_depth))
                inside = injected_mask
                outside = ~inside
                if not inside.any() or not outside.any():
                    raise ValueError("Injection recovery window is empty")
                delta = inj_flat / no_flat - 1.0
                recovered = 1e6 * (float(np.median(delta[outside])) - float(np.median(delta[inside])))
                ratio = recovered / (catalogue_depth * multiplier)
                recoveries[name].append(float(ratio))
                injection_ledger.append({"phase_offset_fraction": offset, "injected_epoch_bkjd": injected_epoch,
                    "depth_multiplier": multiplier, "injected_depth_ppm": catalogue_depth * multiplier,
                    "accepted_transit_events": accepted_events, "skipped_gap_or_overlap_events": skipped_events,
                    "configuration": name, "recovered_depth_ppm": recovered,
                    "recovery_ratio": ratio, "null_control_depth_ppm": null_depth,
                    "overlap_with_real_mask": bool(np.any(injected_mask & real_mask))})
        for name, values in recoveries.items():
            arr = np.asarray(values)
            recovery_summary.setdefault(name, {})[str(multiplier)] = {
                "count": int(len(arr)), "median_ratio": float(np.median(arr)),
                "iqr_ratio": float(np.percentile(arr, 75) - np.percentile(arr, 25)),
                "minimum_ratio": float(arr.min()), "maximum_ratio": float(arr.max())}

    configs_output = {}
    for name, config in configurations.items():
        depth_change = (config["real_depth"]["depth_ppm"] - baseline_depth["depth_ppm"]) / abs(baseline_depth["depth_ppm"]) if baseline_depth["depth_ppm"] else float("inf")
        configs_output[name] = {
            "mode": config["mode"], "window_cadences": config["window_cadences"],
            "window_nominal_days": config["window_nominal_days"],
            "real_depth": config["real_depth"], "real_depth_relative_change": float(depth_change),
            "real_shape_profile": folded_shape_profile(time, config["flux"], period, epoch, duration),
            "shape_half_depth_width_ratio": (folded_shape_profile(time, config["flux"], period, epoch, duration)["half_depth_width_duration_units"] / baseline_shape["half_depth_width_duration_units"] if baseline_shape["half_depth_width_duration_units"] else None),
            "null_control": {"count": len(null_summary[name]), "median_depth_ppm": float(np.median(null_summary[name])),
                "mad_depth_ppm": mad(np.asarray(null_summary[name])),
                "minimum_depth_ppm": float(np.min(null_summary[name])), "maximum_depth_ppm": float(np.max(null_summary[name]))},
            "out_mad_ppm": config["out_mad_ppm"],
            "out_mad_improvement_percent": float((baseline_scatter - config["out_mad_ppm"]) / baseline_scatter * 100) if baseline_scatter else 0,
            "trend_min": config["trend_min"], "trend_max": config["trend_max"],
            "uncertainty_distribution": {"original_median": float(np.nanmedian(error)),
                "original_mad": mad(error), "flattened_median": float(np.nanmedian(config["error"])),
                "flattened_mad": mad(config["error"]),
                "flattened_minimum": float(np.nanmin(config["error"])),
                "flattened_maximum": float(np.nanmax(config["error"]))},
            "masked_cadences": config["masked_cadences"],
            "injection_recovery": recovery_summary[name],
        }

    return {
        "identity": {**target, "quarter": 4, "data_release": 25}, "source": product["source"],
        "selection": product["selection"],
        "ephemeris": {"period_days": period, "epoch_bkjd": epoch, "duration_hours": duration,
            "period_uncertainty_days": period_err, "epoch_uncertainty_days": epoch_err,
            "source": "NASA Exoplanet Archive cumulative table, q1_q17_dr25_sup_koi"},
        "cadence": {"count": len(time), "median_spacing_days": spacing,
            "segments": [{"start_cadence": int(cadence[s[0]]), "end_cadence": int(cadence[s[-1]]), "count": len(s)} for s in segments],
            "gap_threshold_days": 5 * spacing},
        "baseline": {"depth": baseline_depth, "shape_profile": baseline_shape, "out_mad_ppm": baseline_scatter,
            "real_transit_mask_cadences": int(real_mask.sum())},
        "configurations": configs_output,
        "injections": injection_ledger,
        "cadence_products": [{"cadenceno": int(cadence[i]), "time_bkjd": float(time[i]),
            "pdcsap_flux": float(flux[i]), "pdcsap_flux_err": float(error[i]) if np.isfinite(error[i]) else None,
            **{f"{name}_trend": float(config["trend"][i]) for name, config in configurations.items()},
            **{f"{name}_flux": float(config["flux"][i]) for name, config in configurations.items()},
            **{f"{name}_flux_err": float(config["error"][i]) if np.isfinite(config["error"][i]) else None for name, config in configurations.items()},
            "real_transit_mask": bool(real_mask[i])} for i in range(len(time))],
        "_plot": {"time": time, "flux": flux, "real_mask": real_mask,
            "configurations": configurations, "period": period, "epoch": epoch, "duration": duration},
    }


def plot_target(result: dict[str, Any], path: Path) -> None:
    internal = result.pop("_plot")
    time, flux = internal["time"], internal["flux"]
    configs = internal["configurations"]
    fig, axes = plt.subplots(4, 1, figsize=(15, 16), constrained_layout=True)
    axes[0].plot(time, flux / np.median(flux), linewidth=0.55)
    axes[0].set_title(f'{result["identity"]["koi_id"]}: original PDCSAP (normalised)')
    axes[0].set_ylabel("Relative flux")
    for name, config in configs.items():
        axes[1].plot(time, config["trend"] / np.median(flux), linewidth=0.65, label=name)
    axes[1].set_title("Estimated local trends")
    axes[1].set_ylabel("Trend / baseline")
    axes[1].legend(ncol=3, fontsize=8)
    for name, config in configs.items():
        axes[2].plot(time, config["flux"] / np.median(config["flux"]), linewidth=0.5, label=name)
    axes[2].set_title("Flattened derived series (normalised)")
    axes[2].set_ylabel("Relative flux")
    axes[2].set_xlabel("Time (BKJD)")
    axes[2].legend(ncol=3, fontsize=8)
    baseline_profile = folded_shape_profile(time, flux, internal["period"], internal["epoch"], internal["duration"])
    axes[3].plot(baseline_profile["phase_duration_units"], baseline_profile["relative_flux"], linewidth=1.8, label="unflattened PDCSAP")
    for name, config in result["configurations"].items():
        profile = config["real_shape_profile"]
        axes[3].plot(profile["phase_duration_units"], profile["relative_flux"], linewidth=0.9, label=name)
    axes[3].set_title("Real transit: duration-scaled folded shape")
    axes[3].set_xlabel("Phase / transit duration")
    axes[3].set_ylabel("Relative flux")
    axes[3].legend(ncol=4, fontsize=7)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    result["artifacts"] = {"plot": str(path.relative_to(ROOT))}


def render_report(report: dict[str, Any]) -> str:
    lines = ["# PDCSAP detrending and transit-preservation results", "",
        "**Status:** completed offline two-target Q4 method experiment. Results are descriptive; trapezoidal injections are controlled recovery probes, not physical transit models.", "",
        "## Method", "",
        f'- Quality bitmask: `{DEFAULT_QUALITY_BITMASK}`; selected finite TIME/PDCSAP_FLUX cadences.',
        f'- Savitzky–Golay polynomial order: `{POLYORDER}`; windows: `{", ".join(map(str, WINDOWS))}` cadences.',
        "- Time series split at gaps greater than five times median accepted cadence spacing.",
        "- Masked trend excludes ephemeris transits padded by 1.5 durations plus propagated epoch/period uncertainty.",
        f'- Injection design: {INJECTIONS_PER_DEPTH} deterministic phase offsets per target and depth; 0.5x, 1x and 2x catalogue depth.',
        "- Flattened uncertainty is PDCSAP_FLUX_ERR divided by the same positive trend.",
        "- Null controls measure the no-injection processed series at each deterministic injection phase; folded shape profiles are stored in the JSON output and shown in the plots.", "",
        "## Results", ""]
    for target in report["targets"]:
        lines += [f'### {target["identity"]["koi_id"]}', "",
            f'- Cadences: {target["cadence"]["count"]}; segments: {len(target["cadence"]["segments"])}; real-mask cadences: {target["baseline"]["real_transit_mask_cadences"]}.',
            f'- Baseline depth: {target["baseline"]["depth"]["depth_ppm"]:.3f} ppm; baseline out-of-transit MAD: {target["baseline"]["out_mad_ppm"]:.3f} ppm.', "",
            "| Configuration | Depth (ppm) | Depth change | Shape width ratio | OOT MAD (ppm) | MAD improvement | 0.5x / 1x / 2x median recovery | Null depth (ppm) |",
            "|---|---:|---:|---:|---:|---:|---:|---:|"]
        for name, config in target["configurations"].items():
            rec = [config["injection_recovery"][str(m)] ["median_ratio"] for m in (0.5, 1.0, 2.0)]
            width_ratio = config["shape_half_depth_width_ratio"]
            width_text = f"{width_ratio:.3f}" if width_ratio is not None else "n/a"
            lines.append(f'| {name} | {config["real_depth"]["depth_ppm"]:.3f} | {config["real_depth_relative_change"]*100:.2f}% | {width_text} | {config["out_mad_ppm"]:.3f} | {config["out_mad_improvement_percent"]:.2f}% | {rec[0]:.3f} / {rec[1]:.3f} / {rec[2]:.3f} | {config["null_control"]["median_depth_ppm"]:.3f} |')
        lines.append("")
    lines += ["## Interpretation and limitations", "",
        "The predeclared eligibility rules are engineering decision thresholds for this small experiment, not universal astrophysical standards. A configuration is eligible only when every depth's median recovery is 0.90–1.10 for both targets, each recovery IQR is at most 0.20, real depth changes by at most 10%, shape checks show no systematic narrowing, and out-of-transit MAD improves by at least 5% for one target without worsening by more than 5% for the other.",
        "",
        "The machine-readable output includes duration-scaled folded shape profiles, half-depth width ratios, no-injection phase-offset null depths and the complete injection ledger. The half-depth width is a coarse descriptive diagnostic; inspect the supplied time-series plots and phase profiles before any eligibility decision. This is a two-target, single-quarter study and cannot establish population-wide or multi-quarter behaviour.",
        "",
        f'**Experiment decision:** {report["decision"]["conclusion"]}',
        "The numerical shape-width screen is a conservative coarse check, not a replacement for expert review of ingress/egress morphology. No application default, catalogue feature, scaler or KNN ranking is changed.", ""]
    return "\n".join(lines)


def run_analysis(output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    ephemerides = json.loads(EPHEMERIS_FILE.read_text())
    by_koi = {row["kepoi_name"]: row for row in ephemerides["rows"]}
    catalogue = json.loads((ROOT / "data/generated/catalogue.json").read_text())
    # Use the pinned catalogue's koi_depth as the declared injection scale.
    depth_by_koi = {row["koi_id"]: float(row["values"][2]) for row in catalogue.get("observations", []) if row.get("koi_id")}
    targets = []
    for target in TARGETS:
        ephemeris = dict(by_koi[target["koi_id"]])
        if target["koi_id"] not in depth_by_koi:
            # The pinned generated light-curve record carries the same catalogue depth provenance.
            lightcurve = json.loads((ROOT / "data/generated/lightcurves" / f'{target["koi_id"]}-q04.json').read_text())
            ephemeris["catalogue_depth_ppm"] = depth_by_koi[target["koi_id"]]
        else:
            ephemeris["catalogue_depth_ppm"] = depth_by_koi[target["koi_id"]]
        result = run_target(target, ephemeris)
        plot_path = output_dir / f'{target["koi_id"]}-detrending.png'
        plot_target(result, plot_path)
        targets.append(result)
    configuration_names = list(targets[0]["configurations"])
    decisions = {}
    for name in configuration_names:
        per_target = []
        for target in targets:
            config = target["configurations"][name]
            recovery_ok = all(
                0.90 <= config["injection_recovery"][str(multiplier)]["median_ratio"] <= 1.10
                and config["injection_recovery"][str(multiplier)]["iqr_ratio"] <= 0.20
                for multiplier in (0.5, 1.0, 2.0)
            )
            width_ratio = config["shape_half_depth_width_ratio"]
            per_target.append({"koi_id": target["identity"]["koi_id"],
                "recovery_criteria_pass": recovery_ok,
                "real_depth_change_pass": abs(config["real_depth_relative_change"]) <= 0.10,
                "shape_width_screen_pass": width_ratio is not None and width_ratio >= 0.90,
                "scatter_improvement_percent": config["out_mad_improvement_percent"]})
        scatter_values = [row["scatter_improvement_percent"] for row in per_target]
        scatter_ok = max(scatter_values) >= 5.0 and min(scatter_values) >= -5.0
        decisions[name] = {"targets": per_target, "scatter_criteria_pass": scatter_ok,
            "eligible": all(row["recovery_criteria_pass"] and row["real_depth_change_pass"] and row["shape_width_screen_pass"] for row in per_target) and scatter_ok}
    eligible_names = [name for name, decision in decisions.items() if decision["eligible"]]
    report = {"schema": "transit-atlas.pdcsap-detrending", "version": 1,
        "status": "completed_with_eligible_configuration" if eligible_names else "completed_no_eligible_configuration",
        "decision": {"eligible_configurations": eligible_names, "configuration_assessments": decisions,
            "conclusion": "No tested configuration meets all predeclared engineering criteria; retain unflattened PDCSAP as the baseline." if not eligible_names else "One or more configurations meet the numerical screening criteria; visual scientific review and broader validation are still required."},
        "method": {"flux_column": "PDCSAP_FLUX", "uncertainty_column": "PDCSAP_FLUX_ERR",
            "quality_bitmask": DEFAULT_QUALITY_BITMASK, "quality_rule": "(SAP_QUALITY & mask) == 0",
            "windows_cadences": list(WINDOWS), "polyorder": POLYORDER,
            "trend": "scipy.signal.savgol_filter after linear interpolation across excluded transit cadences",
            "gap_factor": 5, "injection_profile": "deterministic trapezoid; ingress/egress each 15% of half-duration",
            "injection_phase_grid": INJECTION_OFFSETS, "injections_per_depth": INJECTIONS_PER_DEPTH,
            "injection_depth_multipliers": [0.5, 1.0, 2.0],
            "limitations": ["Two targets, one quarter only.", "Trapezoidal injections are not physical transit models.", "Shape/ingress-egress assessment requires visual review.", "Eligibility thresholds are engineering rules, not astrophysical standards."]},
        "software": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__, "astropy": astropy_version, "matplotlib": matplotlib.__version__},
        "ephemeris_source": {"file": str(EPHEMERIS_FILE.relative_to(ROOT)), "sha256": sha256_file(EPHEMERIS_FILE), "archive": ephemerides["archive"], "table": ephemerides["table"], "retrieved_at_utc": ephemerides["retrieved_at_utc"]},
        "targets": targets}
    report["artifacts"] = {"analysis_json": str((output_dir / "analysis.json").relative_to(ROOT)), "report_markdown": str((output_dir / "report.md").relative_to(ROOT))}
    (output_dir / "analysis.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    (output_dir / "report.md").write_text(render_report(report))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    report = run_analysis(args.output_dir)
    print(f'Analysed {len(report["targets"])} targets; wrote {args.output_dir / "analysis.json"} and report.md')
    for target in report["targets"]:
        print(target["identity"]["koi_id"], "baseline MAD", round(target["baseline"]["out_mad_ppm"], 3), "ppm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
