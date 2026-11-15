"""Python reference for the Transit Atlas catalogue and exact KNN lookup."""

import argparse
import csv
import hashlib
import io
import json
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sklearn.preprocessing import StandardScaler


@dataclass(frozen=True)
class Feature:
    field: str
    name: str
    unit: str
    log10: bool


FEATURES = (
    Feature("koi_period", "Orbital period", "days", True),
    Feature("koi_duration", "Transit duration", "hours", True),
    Feature("koi_depth", "Transit depth", "ppm", True),
    Feature("koi_impact", "Transit impact parameter", "stellar radii (ratio)", False),
    Feature("koi_model_snr", "Transit signal-to-noise", "ratio", True),
    Feature("koi_steff", "Stellar effective temperature", "K", False),
    Feature("koi_slogg", "Stellar surface gravity", "log10(cm/s²)", False),
    Feature("koi_srad", "Stellar radius", "solar radii", True),
)
FEATURE_FIELDS = tuple(feature.field for feature in FEATURES)
CSV_FIELDS = ("kepoi_name", "kepid", "koi_disposition", *FEATURE_FIELDS)
LABELLED = {"CONFIRMED", "FALSE POSITIVE"}
DISPOSITIONS = ("CANDIDATE", "CONFIRMED", "FALSE POSITIVE")
PARTITIONS = ("train",) * 8 + ("validation", "test")
DEFAULT_QUERY = "K00115.03"
MANIFEST = Path(__file__).resolve().parents[1] / "data/raw/kepler-koi-cumulative-2026-11-14.json"


@dataclass(frozen=True)
class Observation:
    koi_id: str
    host_id: int
    disposition: str
    values: tuple[float, ...]


def parse_value(raw: str, feature: Feature) -> tuple[float, str | None]:
    if not raw.strip():
        return math.nan, "missing"
    try:
        value = float(raw)
    except ValueError:
        return math.nan, "invalid_number"
    if not math.isfinite(value):
        return value, "non_finite"
    if feature.log10 and value <= 0:
        return value, "non_positive_log_input"
    return value, None


def load_snapshot(manifest_path: Path):
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw_csv = (manifest_path.parent / manifest["file"]).read_bytes()
    if hashlib.sha256(raw_csv).hexdigest() != manifest["sha256"]:
        raise ValueError("Snapshot checksum does not match its manifest")

    reader = csv.DictReader(io.StringIO(raw_csv.decode("utf-8"), newline=""))
    if tuple(reader.fieldnames or ()) != CSV_FIELDS:
        raise ValueError("Snapshot columns do not match the feature specification")

    observations = []
    rejected = {}
    by_disposition = {label: Counter() for label in DISPOSITIONS}
    by_feature = {feature.field: {} for feature in FEATURES}
    seen = set()

    for row in reader:
        koi_id = row["kepoi_name"]
        if None in row or any(value is None for value in row.values()):
            raise ValueError(f"Invalid CSV row at line {reader.line_num}")
        if not koi_id or koi_id in seen:
            raise ValueError(f"Missing or duplicate KOI ID at line {reader.line_num}")
        seen.add(koi_id)
        host_id = int(row["kepid"])
        disposition = row["koi_disposition"]
        if host_id < 1 or disposition not in by_disposition:
            raise ValueError(f"Invalid host or disposition for {koi_id}")

        values = []
        issues = {}
        for feature in FEATURES:
            value, reason = parse_value(row[feature.field], feature)
            values.append(value)
            if reason:
                issues[feature.field] = reason
                by_feature[feature.field].setdefault(disposition, Counter())[reason] += 1
        if issues:
            rejected[koi_id] = issues
            by_disposition[disposition]["excluded"] += 1
        else:
            observations.append(Observation(koi_id, host_id, disposition, tuple(values)))
            by_disposition[disposition]["usable"] += 1

    if len(seen) != manifest["rows"]:
        raise ValueError(f"Expected {manifest['rows']} rows, got {len(seen)}")
    audit = {
        "total_rows": len(seen),
        "usable_rows": len(observations),
        "excluded_rows": len(rejected),
        "by_disposition": {
            label: {key: counts[key] for key in ("usable", "excluded")}
            for label, counts in by_disposition.items()
        },
        "feature_exclusions_by_disposition": by_feature,
    }
    return manifest, observations, rejected, audit


def host_partition(host_id: int) -> str:
    digest = hashlib.sha256(str(host_id).encode("ascii")).digest()
    bucket = int.from_bytes(digest[:8], "big") % 10
    return PARTITIONS[bucket]


def raw_measurements(observations: list[Observation]) -> np.ndarray:
    return np.asarray([row.values for row in observations], dtype=np.float64)


def transform_measurements(values: np.ndarray) -> np.ndarray:
    transformed = values.copy()
    log_columns = [feature.log10 for feature in FEATURES]
    transformed[:, log_columns] = np.log10(transformed[:, log_columns])
    return transformed


def score_vectors(query: np.ndarray, references: np.ndarray, identifiers: list[str]):
    contributions = np.square(references - query)
    squared_distances = contributions.sum(axis=1, dtype=np.float64)
    order = np.lexsort((identifiers, squared_distances))
    return order, squared_distances, contributions


def fit_reference(observations: list[Observation]):
    group_counts = {partition: Counter() for partition in dict.fromkeys(PARTITIONS)}
    group_hosts = {partition: set() for partition in group_counts}
    training = []
    for row in observations:
        if row.disposition not in LABELLED:
            continue
        partition = host_partition(row.host_id)
        group_counts[partition][row.disposition] += 1
        group_hosts[partition].add(row.host_id)
        if partition == "train":
            training.append(row)
    if not training:
        raise ValueError("No usable training references")

    reference_values = transform_measurements(raw_measurements(training))
    scaler = StandardScaler().fit(reference_values)
    partition_audit = {
        name: {"hosts": len(group_hosts[name]), "rows_by_disposition": counts}
        for name, counts in group_counts.items()
    }
    return training, scaler, scaler.transform(reference_values), partition_audit


def describe_observation(row: Observation) -> dict:
    return {
        "koi_id": row.koi_id,
        "host_id": row.host_id,
        "disposition": row.disposition,
        "measurements": dict(zip(FEATURE_FIELDS, row.values, strict=True)),
    }


def candidate_lookup(manifest_path: Path, query_id: str, k: int = 5) -> dict:
    manifest, observations, rejected, audit = load_snapshot(manifest_path)
    if query_id in rejected:
        reasons = ", ".join(f"{field} ({reason})" for field, reason in rejected[query_id].items())
        raise ValueError(f"{query_id} has unusable measurements: {reasons}")
    query = next((row for row in observations if row.koi_id == query_id), None)
    if query is None or query.disposition != "CANDIDATE":
        raise ValueError(f"{query_id} is not an unresolved candidate in this snapshot")
    if k < 1:
        raise ValueError("k must be positive")

    training, scaler, scaled_references, partitions = fit_reference(observations)
    eligible = [index for index, row in enumerate(training) if row.host_id != query.host_id]
    same_host = [row.koi_id for row in training if row.host_id == query.host_id]
    if k > len(eligible):
        raise ValueError(f"k exceeds the {len(eligible)} eligible references")

    scaled_query = scaler.transform(transform_measurements(raw_measurements([query])))[0]
    references = [training[index] for index in eligible]
    order, squared, contributions = score_vectors(
        scaled_query, scaled_references[eligible], [row.koi_id for row in references]
    )
    neighbours = []
    for rank, index in enumerate(order[:k], start=1):
        distance_squared = float(squared[index])
        neighbours.append({
            "rank": rank,
            **describe_observation(references[index]),
            "distance": math.sqrt(distance_squared),
            "distance_squared": distance_squared,
            "feature_contributions": {
                field: {
                    "squared_delta": float(delta),
                    "share": float(delta) / distance_squared if distance_squared else None,
                }
                for field, delta in zip(FEATURE_FIELDS, contributions[index], strict=True)
            },
        })

    return {
        "snapshot": manifest,
        "audit": audit,
        "labelled_partitions": partitions,
        "training_references": len(training),
        "eligible_references": len(references),
        "same_host_references_excluded": same_host,
        "features": [
            {
                "field": feature.field,
                "name": feature.name,
                "unit": feature.unit,
                "transform": "log10" if feature.log10 else "identity",
                "training_mean": float(scaler.mean_[index]),
                "training_scale": float(scaler.scale_[index]),
                "constant": bool(scaler.var_[index] == 0),
            }
            for index, feature in enumerate(FEATURES)
        ],
        "query": describe_observation(query),
        "neighbours": neighbours,
    }


def synthetic_lookup() -> dict:
    identifiers = ["A", "B", "C"]
    vectors = np.array([
        [1, 0, 0, 0, 0, 0, 0, 0],
        [0.2, 0, 0, 2, 0, 0, 0, 0],
        [0.7, 0.6, 0, 0, 0, 0, 0, 0],
    ])
    query = np.zeros(8)
    full_order, full_squared, contributions = score_vectors(query, vectors, identifiers)
    display_order, display_squared, _ = score_vectors(query[:3], vectors[:, :3], identifiers)
    return {
        "full_order": [identifiers[index] for index in full_order],
        "display_order": [identifiers[index] for index in display_order],
        "examples": {
            label: {
                "vector": vectors[index].tolist(),
                "full_distance": math.sqrt(full_squared[index]),
                "display_distance": math.sqrt(display_squared[index]),
                "feature_squared_deltas": contributions[index].tolist(),
            }
            for index, label in enumerate(identifiers)
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--query", default=DEFAULT_QUERY, help="unresolved candidate KOI ID")
    mode.add_argument("--synthetic", action="store_true", help="run the 3D-vs-8D example")
    parser.add_argument("--k", type=int, default=5, help="number of neighbours for a real query")
    parser.add_argument("--snapshot", type=Path, default=MANIFEST, help="path to a snapshot manifest")
    args = parser.parse_args()
    try:
        report = synthetic_lookup() if args.synthetic else candidate_lookup(
            args.snapshot, args.query.strip().upper(), args.k
        )
    except (OSError, ValueError, KeyError) as error:
        parser.exit(2, f"{parser.prog}: {error}\n")
    print(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
