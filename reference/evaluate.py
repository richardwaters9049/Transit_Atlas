"""Evaluate catalogue label agreement on disjoint Kepler host groups."""

import argparse
import csv
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from transit_atlas import (
    DISPOSITIONS,
    FEATURE_FIELDS,
    LABELLED,
    MANIFEST,
    Observation,
    fit_reference,
    host_partition,
    load_snapshot,
    raw_measurements,
    score_vectors,
    transform_measurements,
)

K_VALUES = (3, 5, 7)
CONFIRMED, FALSE_POSITIVE = "CONFIRMED", "FALSE POSITIVE"
LABELS = (CONFIRMED, FALSE_POSITIVE)
SNR_COLUMN = FEATURE_FIELDS.index("koi_model_snr")
DEFAULT_OUTPUT = MANIFEST.parents[1] / "evaluation" / "held-out.json"


@dataclass(frozen=True)
class RankedSignal:
    query: Observation
    neighbours: tuple[Observation, ...]
    distances: tuple[float, ...]

    def votes(self, k: int) -> Counter:
        return Counter(row.disposition for row in self.neighbours[:k])

    def prediction(self, k: int) -> str:
        return self.votes(k).most_common(1)[0][0]


def rank_queries(queries, vectors, training, references) -> list[RankedSignal]:
    if len(training) < max(K_VALUES):
        raise ValueError("Training has fewer than seven labelled references")
    if {row.host_id for row in queries} & {row.host_id for row in training}:
        raise ValueError("A query host overlaps the training split")
    identifiers = [row.koi_id for row in training]
    ranked = []
    for row, vector in zip(queries, vectors, strict=True):
        order, distances_squared, _ = score_vectors(vector, references, identifiers)
        nearest = order[:max(K_VALUES)]
        ranked.append(RankedSignal(
            row,
            tuple(training[index] for index in nearest),
            tuple(float(distance) for distance in np.sqrt(distances_squared[nearest])),
        ))
    return ranked


def agreement(expected: list[str], predicted: list[str]) -> dict:
    pairs = Counter(zip(expected, predicted, strict=True))
    confusion = {
        actual: {guess: pairs[actual, guess] for guess in LABELS}
        for actual in LABELS
    }
    recalls = {
        label: confusion[label][label] / sum(confusion[label].values())
        if sum(confusion[label].values()) else None
        for label in LABELS
    }
    return {
        "rows": len(expected),
        "agreement": sum(pairs[label, label] for label in LABELS) / len(expected) if expected else None,
        "balanced_agreement": sum(recalls.values()) / len(LABELS)
        if all(recall is not None for recall in recalls.values()) else None,
        "recall": recalls,
        "confusion_actual_by_vote": confusion,
    }


def compare(ranks: list[RankedSignal], k: int, majority_label: str) -> dict:
    expected = [row.query.disposition for row in ranks]
    return {
        "knn": agreement(expected, [row.prediction(k) for row in ranks]),
        "majority_baseline": agreement(expected, [majority_label] * len(ranks)),
    }


def assess_coverage(manifest_path, manifest, rows) -> dict:
    included = {row.koi_id for row in rows}
    totals = {
        split: {label: {"raw": 0, "usable": 0} for label in DISPOSITIONS}
        for split in ("train", "validation", "test")
    }
    with (manifest_path.parent / manifest["file"]).open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            counts = totals[host_partition(int(row["kepid"]))][row["koi_disposition"]]
            counts["raw"] += 1
            counts["usable"] += row["kepoi_name"] in included
    return totals


def strongest_training_correlation(vectors) -> tuple[int, int, float]:
    with np.errstate(invalid="ignore", divide="ignore"):
        correlations = np.corrcoef(vectors, rowvar=False)
    pairs = [
        (i, j, float(correlations[i, j]))
        for i in range(len(FEATURE_FIELDS)) for j in range(i + 1, len(FEATURE_FIELDS))
        if np.isfinite(correlations[i, j])
    ]
    return max(pairs, key=lambda pair: abs(pair[2]))


def disagreements(ranks, k: int) -> list[dict]:
    cases = []
    for label in LABELS:
        mismatches = [
            row for row in ranks if row.query.disposition == label and row.prediction(k) != label
        ]
        ordered = sorted(mismatches, key=lambda row: (
            -max(row.votes(k).values()), row.distances[k - 1], row.query.koi_id
        ))
        for row in ordered[:2]:
            cases.append({
                "koi_id": row.query.koi_id,
                "host_id": row.query.host_id,
                "archive_label": label,
                "vote": row.prediction(k),
                "signal_to_noise": row.query.values[SNR_COLUMN],
                "neighbours": [
                    {"koi_id": neighbour.koi_id, "archive_label": neighbour.disposition, "distance": distance}
                    for neighbour, distance in zip(row.neighbours[:k], row.distances[:k], strict=True)
                ],
            })
    return cases


def evaluate(manifest_path: Path) -> dict:
    manifest, rows, _, audit = load_snapshot(manifest_path)
    training, scaler, references, partitions = fit_reference(rows)
    majority_label = Counter(row.disposition for row in training).most_common(1)[0][0]
    first, second, correlation = strongest_training_correlation(references)

    def split_vectors(name):
        subset = [
            row for row in rows if row.disposition in LABELLED and host_partition(row.host_id) == name
        ]
        vectors = scaler.transform(transform_measurements(raw_measurements(subset)))
        return subset, vectors

    validation, validation_vectors = split_vectors("validation")
    validation_ranks = rank_queries(validation, validation_vectors, training, references)
    comparisons = {k: compare(validation_ranks, k, majority_label) for k in K_VALUES}
    selected = max(K_VALUES, key=lambda k: (comparisons[k]["knn"]["balanced_agreement"], -k))
    threshold = float(np.quantile([rank.distances[selected - 1] for rank in validation_ranks], 0.95))

    test, test_vectors = split_vectors("test")
    test_ranks = rank_queries(test, test_vectors, training, references)
    test_metrics = compare(test_ranks, selected, majority_label)
    bands = {}
    for label, lower, upper in (("below 10", 0, 10), ("10 to below 20", 10, 20), ("20 and above", 20, np.inf)):
        cohort = [row for row in test_ranks if lower <= row.query.values[SNR_COLUMN] < upper]
        bands[label] = compare(cohort, selected, majority_label)

    mixed = [len(row.votes(selected)) > 1 for row in test_ranks]
    distant = [row.distances[selected - 1] > threshold for row in test_ranks]
    unflagged = [
        row for row, has_mixed, is_distant in zip(test_ranks, mixed, distant, strict=True)
        if not (has_mixed or is_distant)
    ]
    reduced_ranks = rank_queries(
        test, np.delete(test_vectors, second, axis=1), training, np.delete(references, second, axis=1)
    )
    return {
        "snapshot": manifest,
        "audit": audit,
        "labelled_partitions": partitions,
        "complete_case_coverage": assess_coverage(manifest_path, manifest, rows),
        "majority_label": majority_label,
        "selection": "Highest validation balanced agreement, with smaller k breaking ties",
        "validation": comparisons,
        "selected_k": selected,
        "test": test_metrics,
        "test_signal_to_noise_bands": bands,
        "exploratory_review_flags": {
            "validation_percentile": 95,
            "kth_distance_threshold": threshold,
            "mixed_rows": sum(mixed),
            "distant_rows": sum(distant),
            "unflagged": compare(unflagged, selected, majority_label),
        },
        "correlation_sensitivity": {
            "strongest_absolute_training_pearson_pair": [FEATURE_FIELDS[first], FEATURE_FIELDS[second]],
            "pearson_r": correlation,
            "omitted_field": FEATURE_FIELDS[second],
            "neighbour_sets_changed": sum(
                {neighbour.koi_id for neighbour in full.neighbours[:selected]}
                != {neighbour.koi_id for neighbour in reduced.neighbours[:selected]}
                for full, reduced in zip(test_ranks, reduced_ranks, strict=True)
            ),
            "votes_changed": sum(
                full.prediction(selected) != reduced.prediction(selected)
                for full, reduced in zip(test_ranks, reduced_ranks, strict=True)
            ),
            "test_without_field": compare(reduced_ranks, selected, majority_label)["knn"],
        },
        "test_disagreements": disagreements(test_ranks, selected),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = evaluate(args.snapshot)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
