"""Kepler light-curve validation and phase-fold reference calculations.

The archive FITS file remains the source of truth. This module creates a
reproducible, JSON-friendly view from its cadence columns and a declared
ephemeris/processing configuration.
"""

from __future__ import annotations

import hashlib
import math
import statistics
from pathlib import Path
from typing import Any, Sequence

SCHEMA = "transit-atlas.kepler-lightcurve"
SCHEMA_VERSION = 1
DEFAULT_QUALITY_BITMASK = 1_130_799
PHASE_CONVENTION = "((time_bkjd - epoch_bkjd + period_days / 2) % period_days) / period_days - 0.5"
NORMALIZATION = "per_product_median_relative_flux_ppm"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_ephemeris(period_days: float, epoch_bkjd: float, duration_hours: float) -> None:
    values = (period_days, epoch_bkjd, duration_hours)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("Ephemeris values must be finite.")
    if period_days <= 0:
        raise ValueError("Orbital period must be greater than zero.")
    if duration_hours <= 0:
        raise ValueError("Transit duration must be greater than zero.")
    if duration_hours / 24 >= period_days:
        raise ValueError("Transit duration must be shorter than the orbital period.")


def phase_for_time(time_bkjd: float, period_days: float, epoch_bkjd: float) -> float:
    if not math.isfinite(time_bkjd):
        raise ValueError("Cadence time must be finite.")
    if not math.isfinite(period_days) or period_days <= 0:
        raise ValueError("Orbital period must be finite and greater than zero.")
    if not math.isfinite(epoch_bkjd):
        raise ValueError("Transit epoch must be finite.")
    return ((time_bkjd - epoch_bkjd + period_days / 2) % period_days) / period_days - 0.5


def fold_light_curve(
    time_bkjd: Sequence[float],
    flux: Sequence[float],
    flux_err: Sequence[float],
    quality: Sequence[int],
    cadenceno: Sequence[int | None],
    *,
    period_days: float,
    epoch_bkjd: float,
    duration_hours: float,
    quality_bitmask: int = DEFAULT_QUALITY_BITMASK,
) -> dict[str, Any]:
    """Fold one Kepler product around a KOI ephemeris.

    Quality flags are evaluated with (quality & quality_bitmask) == 0.
    The source arrays are not mutated. The median baseline is calculated from
    finite, quality-accepted fluxes in this product only.
    """
    validate_ephemeris(period_days, epoch_bkjd, duration_hours)
    if quality_bitmask < 0:
        raise ValueError("Quality bitmask cannot be negative.")

    lengths = {len(time_bkjd), len(flux), len(flux_err), len(quality), len(cadenceno)}
    if len(lengths) != 1:
        raise ValueError("Time, flux, uncertainty, quality and cadence arrays must have equal lengths.")
    if len(time_bkjd) == 0:
        raise ValueError("The light curve contains no cadences.")

    accepted: list[tuple[float, float, float | None, int, int | None]] = []
    quality_rejected = 0
    invalid_rejected = 0

    for time, value, error, flag, cadence in zip(
        time_bkjd, flux, flux_err, quality, cadenceno, strict=True
    ):
        if int(flag) & quality_bitmask:
            quality_rejected += 1
            continue
        try:
            numeric_time = float(time)
            numeric_flux = float(value)
        except (TypeError, ValueError):
            invalid_rejected += 1
            continue
        if not math.isfinite(numeric_time) or not math.isfinite(numeric_flux):
            invalid_rejected += 1
            continue
        try:
            numeric_error = float(error)
            valid_error = numeric_error if math.isfinite(numeric_error) and numeric_error >= 0 else None
        except (TypeError, ValueError):
            valid_error = None
        accepted.append((numeric_time, numeric_flux, valid_error, int(flag), cadence))

    if not accepted:
        raise ValueError("No finite cadences remain after applying the quality mask.")

    baseline = statistics.median(row[1] for row in accepted)
    if not math.isfinite(baseline) or baseline <= 0:
        raise ValueError("The accepted flux median must be finite and greater than zero.")

    folded = []
    for time, value, error, flag, cadence in accepted:
        phase = phase_for_time(time, period_days, epoch_bkjd)
        folded.append({
            "phase": phase,
            "phase_days": phase * period_days,
            "time_bkjd": time,
            "relative_flux_ppm": (value / baseline - 1.0) * 1_000_000.0,
            "relative_flux_error_ppm": (
                error / baseline * 1_000_000.0 if error is not None else None
            ),
            "quality": flag,
            "cadenceno": cadence,
        })
    folded.sort(key=lambda row: (row["phase"], row["time_bkjd"]))

    return {
        "normalization": NORMALIZATION,
        "normalization_median_flux": baseline,
        "quality_bitmask": quality_bitmask,
        "cadences_total": len(time_bkjd),
        "cadences_used": len(folded),
        "cadences_quality_rejected": quality_rejected,
        "cadences_invalid_rejected": invalid_rejected,
        "transit_half_duration_phase": duration_hours / (48.0 * period_days),
        "points": folded,
    }


def read_kepler_fits(path: Path, flux_column: str = "pdcsap_flux") -> dict[str, Any]:
    """Read a local Kepler light-curve FITS file without discarding quality flags."""
    try:
        import lightkurve as lk
    except ImportError as error:
        raise RuntimeError(
            "Install the pinned light-curve dependencies with "
            "python -m pip install -r reference/requirements.txt."
        ) from error

    if flux_column not in {"pdcsap_flux", "sap_flux"}:
        raise ValueError("Flux column must be 'pdcsap_flux' or 'sap_flux'.")

    light_curve = lk.read(
        str(path),
        flux_column=flux_column,
        quality_bitmask="none",
    )

    def numeric_values(values: Any) -> list[float | None]:
        result = []
        for value in values:
            try:
                number = float(value)
                result.append(number if math.isfinite(number) else None)
            except (TypeError, ValueError):
                result.append(None)
        return result

    def integer_values(values: Any) -> list[int]:
        result = []
        for value in values:
            try:
                number = float(value)
                result.append(int(number) if math.isfinite(number) else 0)
            except (TypeError, ValueError):
                result.append(0)
        return result

    def optional_integer_values(values: Any) -> list[int | None]:
        result = []
        for value in values:
            try:
                number = float(value)
                result.append(int(number) if math.isfinite(number) else None)
            except (TypeError, ValueError):
                result.append(None)
        return result

    metadata = dict(light_curve.meta)
    time_format = str(light_curve.time.format).lower()
    time_scale = str(light_curve.time.scale).lower()
    if time_format != "bkjd":
        raise ValueError(f"Expected Kepler BKJD timestamps, received {time_format!r}.")
    if time_scale != "tdb":
        raise ValueError(f"Expected Kepler TDB timestamps, received {time_scale!r}.")
    time = numeric_values(light_curve.time.value)
    flux = numeric_values(light_curve.flux.value)
    flux_error = numeric_values(light_curve.flux_err.value)
    quality = integer_values(light_curve.quality)
    cadence = optional_integer_values(light_curve.cadenceno)

    if not (len(time) == len(flux) == len(flux_error) == len(quality) == len(cadence)):
        raise ValueError("The FITS cadence columns have inconsistent lengths.")

    return {
        "time_bkjd": time,
        "flux": flux,
        "flux_err": flux_error,
        "quality": quality,
        "cadenceno": cadence,
        "time_format": time_format,
        "time_scale": time_scale,
        "time_unit": str(metadata.get("TIMEUNIT", "d")),
        "flux_unit": str(getattr(light_curve.flux, "unit", "unknown")),
        "metadata": {
            key: metadata.get(key)
            for key in (
                "TELESCOP", "INSTRUME", "OBJECT", "KEPLERID", "QUARTER",
                "CHANNEL", "MODULE", "OUTPUT", "TIMESYS", "TIMEUNIT",
                "BJDREFI", "BJDREFF", "DATA_REL", "CREATOR", "PROCVER",
                "DATE",
            )
            if metadata.get(key) is not None
        },
        "lightkurve_version": lk.__version__,
        "flux_column": flux_column,
        "source_sha256": sha256_file(path),
        "source_bytes": path.stat().st_size,
    }


def validate_fits_product_identity(
    raw: dict[str, Any],
    *,
    host_id: int,
    quarter: int,
    data_release: int = 25,
) -> None:
    metadata = raw["metadata"]
    expected = {
        "KEPLERID": host_id,
        "QUARTER": quarter,
        "DATA_REL": data_release,
    }
    for key, expected_value in expected.items():
        actual = metadata.get(key)
        if actual is None or int(actual) != expected_value:
            raise ValueError(
                f"FITS {key} mismatch: expected {expected_value}, received {actual!r}."
            )


def make_light_curve_document(
    *,
    koi_id: str,
    host_id: int,
    signal_role: str,
    period_days: float,
    epoch_bkjd: float,
    duration_hours: float,
    source_path: Path,
    source_relative_path: str,
    source_uri: str,
    product_filename: str,
    quarter: int,
    cadence: str,
    author: str,
    ephemeris_source: dict[str, Any] | None = None,
    data_release: int = 25,
    flux_column: str = "pdcsap_flux",
    quality_bitmask: int = DEFAULT_QUALITY_BITMASK,
) -> dict[str, Any]:
    """Build the versioned, provenance-carrying light-curve document."""
    if not (len(koi_id) == 9 and koi_id.startswith("K") and koi_id[1:6].isdigit()
            and koi_id[6] == "." and koi_id[7:9].isdigit()):
        raise ValueError("KOI ID must use the K00000.00 format.")
    if host_id <= 0:
        raise ValueError("Kepler host ID must be a positive integer.")
    if signal_role not in {"candidate", "reference"}:
        raise ValueError("Signal role must be 'candidate' or 'reference'.")

    raw = read_kepler_fits(source_path, flux_column)
    validate_fits_product_identity(
        raw,
        host_id=host_id,
        quarter=quarter,
        data_release=data_release,
    )
    folded = fold_light_curve(
        raw["time_bkjd"],
        raw["flux"],
        raw["flux_err"],
        raw["quality"],
        raw["cadenceno"],
        period_days=period_days,
        epoch_bkjd=epoch_bkjd,
        duration_hours=duration_hours,
        quality_bitmask=quality_bitmask,
    )

    return {
        "schema": SCHEMA,
        "version": SCHEMA_VERSION,
        "identity": {
            "koi_id": koi_id,
            "host_id": host_id,
            "signal_role": signal_role,
        },
        "ephemeris": {
            "period_days": period_days,
            "epoch_bkjd": epoch_bkjd,
            "duration_hours": duration_hours,
            "epoch_definition": "BKJD = BJD - 2454833.0",
            "source": ephemeris_source or {},
        },
        "source": {
            "archive": "Mikulski Archive for Space Telescopes (MAST)",
            "mission": "Kepler",
            "data_uri": source_uri,
            "product_filename": product_filename,
            "local_file": source_relative_path,
            "sha256": raw["source_sha256"],
            "bytes": raw["source_bytes"],
            "author": author,
            "quarter": quarter,
            "data_release": data_release,
            "cadence": cadence,
            "time_format": raw["time_format"],
            "time_scale": raw["time_scale"],
            "time_unit": raw["time_unit"],
            "flux_unit": raw["flux_unit"],
            "fits_metadata": raw["metadata"],
        },
        "processing": {
            "reader": "Lightkurve",
            "reader_version": raw["lightkurve_version"],
            "flux_column": flux_column,
            "quality_bitmask": quality_bitmask,
            "quality_rule": "(quality & quality_bitmask) == 0",
            "normalization": NORMALIZATION,
            "phase_convention": PHASE_CONVENTION,
            "phase_origin": "Transit centre at phase 0",
            "source_cadences_preserved": True,
        },
        "cadences": {
            "time_bkjd": raw["time_bkjd"],
            "flux": raw["flux"],
            "flux_err": raw["flux_err"],
            "quality": raw["quality"],
            "cadenceno": raw["cadenceno"],
        },
        "folded": folded,
    }
