"""Import a pinned Kepler long-cadence FITS product for a specific KOI.

The importer reads the ephemeris from the committed NASA Exoplanet Archive
snapshot, validates the KOI-to-KIC mapping against the pinned Transit Atlas
catalogue, retrieves the FITS bytes from MAST's public AWS mirror, and writes
a versioned offline JSON document.

Example from the repository root:

    python reference/import_kepler_lightcurve.py \
      --koi-id K00115.03 --role candidate --quarter 4

Use --fits /path/to/file_llc.fits to import a FITS product already downloaded.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import urlopen

from kepler_lightcurve import (
    DEFAULT_QUALITY_BITMASK,
    make_light_curve_document,
)

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data/raw/kepler-lightcurves"
OUTPUT_DIR = ROOT / "data/generated/lightcurves"
DEFAULT_EPHEMERIS_FILE = ROOT / "data/raw/kepler-lightcurve-ephemerides-2026-11-15.json"

# Kepler long-cadence product filenames use a quarter-specific stop-time token.
QUARTER_STOP_TIMES = {
    0: "2009131105131",
    1: "2009166043257",
    2: "2009259160929",
    3: "2009350155506",
    4: "2010078095331",
    5: "2010174085026",
    6: "2010265121752",
    7: "2010355172524",
    8: "2011073133259",
    9: "2011177032512",
    10: "2011271113734",
    11: "2012004120508",
    12: "2012088054726",
    13: "2012179063303",
    14: "2012277125453",
    15: "2013011073258",
    16: "2013098041711",
    17: "2013131215648",
}


def read_pinned_signal(koi_id: str) -> dict[str, Any]:
    catalogue = json.loads((ROOT / "data/generated/catalogue.json").read_text(encoding="utf-8"))
    rows = {row["koi_id"]: row for row in catalogue["observations"]}
    try:
        return rows[koi_id]
    except KeyError as error:
        raise ValueError(f"{koi_id} is not present in the pinned usable catalogue.") from error


def read_pinned_ephemeris(
    koi_id: str,
    ephemeris_file: Path = DEFAULT_EPHEMERIS_FILE,
) -> tuple[dict[str, Any], dict[str, Any]]:
    snapshot = json.loads(ephemeris_file.read_text(encoding="utf-8"))
    if snapshot.get("schema") != "transit-atlas.kepler-ephemerides" or snapshot.get("version") != 1:
        raise ValueError(f"Unsupported ephemeris snapshot: {ephemeris_file}")
    rows = {row["kepoi_name"]: row for row in snapshot["rows"]}
    try:
        return rows[koi_id], {
            "archive": snapshot["archive"],
            "table": snapshot["table"],
            "endpoint": snapshot["endpoint"],
            "query": snapshot["query"],
            "retrieved_at_utc": snapshot["retrieved_at_utc"],
        }
    except KeyError as error:
        raise ValueError(
            f"{koi_id} is not present in the pinned ephemeris snapshot {ephemeris_file}."
        ) from error


def validate_signal_mapping(
    signal: dict[str, Any],
    *,
    koi_id: str,
    host_id: int,
    role: str,
    period_days: float,
    duration_hours: float,
) -> None:
    if signal["host_id"] != host_id:
        raise ValueError(
            f"{koi_id} belongs to KIC {signal['host_id']}, not the supplied KIC {host_id}."
        )
    expected_role = "candidate" if signal["disposition"] == "CANDIDATE" else "reference"
    if role != expected_role:
        raise ValueError(
            f"{koi_id} is labelled {signal['disposition']} in the pinned catalogue; "
            f"its role must be {expected_role!r}."
        )
    if not math.isclose(signal["values"][0], period_days, rel_tol=1e-7, abs_tol=1e-10):
        raise ValueError(
            f"Period {period_days} does not match the pinned {koi_id} period "
            f"({signal['values'][0]} days)."
        )
    if not math.isclose(signal["values"][1], duration_hours, rel_tol=1e-7, abs_tol=1e-8):
        raise ValueError(
            f"Duration {duration_hours} does not match the pinned {koi_id} duration "
            f"({signal['values'][1]} hours)."
        )


def download_public_s3_product(
    host_id: int,
    quarter: int,
    download_dir: Path,
) -> tuple[Path, dict[str, str]]:
    """Download one public Kepler long-cadence product from the MAST AWS mirror."""
    if quarter not in QUARTER_STOP_TIMES:
        raise ValueError(f"Quarter must be between 0 and 17; received {quarter}.")

    padded_kic = f"{host_id:09d}"
    prefix = f"kepler/public/lightcurves/{padded_kic[:4]}/{padded_kic}/"
    listing_url = (
        "https://stpubdata.s3.amazonaws.com/?list-type=2&prefix="
        + quote(prefix, safe="/")
    )

    try:
        with urlopen(listing_url, timeout=30) as response:
            listing = ET.fromstring(response.read())
    except (OSError, URLError, ET.ParseError) as error:
        raise RuntimeError(f"Could not list the MAST public AWS mirror: {error}") from error

    namespace = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
    keys = [
        item.text
        for item in listing.findall("s3:Contents/s3:Key", namespace)
        if item.text
    ]
    expected_suffix = f"-{QUARTER_STOP_TIMES[quarter]}_llc.fits"
    matches = [key for key in keys if key.endswith(expected_suffix)]

    if len(matches) != 1:
        if not matches:
            raise RuntimeError(
                f"No public Kepler long-cadence FITS product exists for "
                f"KIC {host_id}, quarter {quarter}."
            )
        raise RuntimeError(
            f"Expected one public FITS product for KIC {host_id}, quarter {quarter}; "
            f"found {len(matches)}."
        )

    key = matches[0]
    filename = key.rsplit("/", 1)[-1]
    local_path = download_dir / filename
    local_path.parent.mkdir(parents=True, exist_ok=True)
    if not local_path.is_file():
        download_url = f"https://stpubdata.s3.amazonaws.com/{key}"
        try:
            with urlopen(download_url, timeout=60) as response, local_path.open("wb") as target:
                shutil.copyfileobj(response, target)
        except (OSError, URLError) as error:
            local_path.unlink(missing_ok=True)
            raise RuntimeError(f"Could not download {filename} from MAST AWS: {error}") from error

    return local_path, {
        "data_uri": f"s3://stpubdata/{key}",
        "product_filename": filename,
        "author": "Kepler",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import and phase-fold one Kepler long-cadence FITS product."
    )
    parser.add_argument(
        "--koi-id",
        required=True,
        help="KOI identifier from the pinned catalogue, e.g. K00115.03",
    )
    parser.add_argument("--role", required=True, choices=("candidate", "reference"))
    parser.add_argument("--quarter", required=True, type=int)
    parser.add_argument("--data-release", type=int, default=25)
    parser.add_argument("--fits", type=Path, help="Use a local FITS file instead of downloading from MAST AWS")
    parser.add_argument("--ephemeris-file", type=Path, default=DEFAULT_EPHEMERIS_FILE)
    parser.add_argument("--host-id", type=int, help="Optional assertion against the pinned ephemeris")
    parser.add_argument("--period-days", type=float, help="Optional assertion against the pinned catalogue")
    parser.add_argument("--epoch-bkjd", type=float, help="Optional assertion against the pinned ephemeris")
    parser.add_argument("--duration-hours", type=float, help="Optional assertion against the pinned catalogue")
    parser.add_argument("--data-uri", default="", help="Original MAST URI for a local FITS import")
    parser.add_argument("--product-filename", default="", help="Original MAST product filename for a local FITS import")
    parser.add_argument("--author", default="Local FITS import", help="Archive product author")
    parser.add_argument("--flux-column", choices=("pdcsap_flux", "sap_flux"), default="pdcsap_flux")
    parser.add_argument("--quality-bitmask", type=int, default=DEFAULT_QUALITY_BITMASK)
    parser.add_argument("--overwrite", action="store_true", help="Replace existing raw and derived files")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        signal = read_pinned_signal(args.koi_id)
        ephemeris, ephemeris_snapshot = read_pinned_ephemeris(args.koi_id, args.ephemeris_file)
        host_id = int(ephemeris["kepid"])
        period_days = float(ephemeris["koi_period"])
        epoch_bkjd = float(ephemeris["koi_time0bk"])
        duration_hours = float(ephemeris["koi_duration"])

        assertions = (
            ("host ID", args.host_id, host_id),
            ("period", args.period_days, period_days),
            ("epoch", args.epoch_bkjd, epoch_bkjd),
            ("duration", args.duration_hours, duration_hours),
        )
        for label, supplied, pinned in assertions:
            if supplied is not None and not math.isclose(
                supplied, pinned, rel_tol=1e-7, abs_tol=1e-8
            ):
                raise ValueError(
                    f"Supplied {label} {supplied} does not match the pinned "
                    f"{args.koi_id} value {pinned}."
                )

        if ephemeris["koi_disposition"] != signal["disposition"]:
            raise ValueError(
                f"Disposition mismatch for {args.koi_id}: catalogue says "
                f"{signal['disposition']}, ephemeris snapshot says {ephemeris['koi_disposition']}."
            )

        validate_signal_mapping(
            signal,
            koi_id=args.koi_id,
            host_id=host_id,
            role=args.role,
            period_days=period_days,
            duration_hours=duration_hours,
        )

        RAW_DIR.mkdir(parents=True, exist_ok=True)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        raw_path = RAW_DIR / f"{args.koi_id}-q{args.quarter:02d}.fits"
        json_path = OUTPUT_DIR / f"{args.koi_id}-q{args.quarter:02d}.json"
        if not args.overwrite and (raw_path.exists() or json_path.exists()):
            raise FileExistsError(
                f"An import already exists for {args.koi_id}, quarter {args.quarter}. "
                "Use --overwrite only if you intend to replace it."
            )

        if args.fits:
            source_path = args.fits.expanduser().resolve()
            if not source_path.is_file():
                raise FileNotFoundError(f"FITS file does not exist: {source_path}")
            source = {
                "data_uri": args.data_uri,
                "product_filename": args.product_filename or source_path.name,
                "author": args.author,
            }
        else:
            source_path, source = download_public_s3_product(
                host_id,
                args.quarter,
                ROOT / ".cache/kepler-public",
            )

        if source_path.resolve() != raw_path.resolve():
            shutil.copy2(source_path, raw_path)

        ephemeris_source = {
            **ephemeris_snapshot,
            "koi_disposition": ephemeris["koi_disposition"],
            "koi_pdisposition": ephemeris["koi_pdisposition"],
            "koi_vet_date": ephemeris["koi_vet_date"],
            "koi_disp_prov": ephemeris["koi_disp_prov"],
            "period_err_plus_days": ephemeris["koi_period_err1"],
            "period_err_minus_days": ephemeris["koi_period_err2"],
            "epoch_err_plus_days": ephemeris["koi_time0bk_err1"],
            "epoch_err_minus_days": ephemeris["koi_time0bk_err2"],
            "duration_err_plus_hours": ephemeris["koi_duration_err1"],
            "duration_err_minus_hours": ephemeris["koi_duration_err2"],
        }
        document = make_light_curve_document(
            koi_id=args.koi_id,
            host_id=host_id,
            signal_role=args.role,
            period_days=period_days,
            epoch_bkjd=epoch_bkjd,
            duration_hours=duration_hours,
            source_path=raw_path,
            source_relative_path=raw_path.relative_to(ROOT).as_posix(),
            source_uri=source["data_uri"],
            product_filename=source["product_filename"],
            quarter=args.quarter,
            cadence="long",
            author=source["author"],
            ephemeris_source=ephemeris_source,
            data_release=args.data_release,
            flux_column=args.flux_column,
            quality_bitmask=args.quality_bitmask,
        )
        json_path.write_text(
            json.dumps(document, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        print(f"Imported {args.koi_id} · KIC {host_id} · quarter {args.quarter}")
        print(f"Ephemeris: P={period_days:.8f} d · T0={epoch_bkjd:.5f} BKJD · D={duration_hours:.3f} h")
        print(f"Source: {raw_path.relative_to(ROOT)}")
        print(f"MAST URI: {source['data_uri']}")
        print(f"SHA-256: {document['source']['sha256']}")
        print(
            f"Cadences: {document['folded']['cadences_used']}/"
            f"{document['folded']['cadences_total']} retained"
        )
        print(f"Folded data: {json_path.relative_to(ROOT)}")
        return 0
    except Exception as error:
        print(f"Import failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
