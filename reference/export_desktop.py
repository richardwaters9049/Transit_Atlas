"""Freeze the Python reference model and the display-only PCA for the desktop."""

import json
from pathlib import Path

import numpy as np
from scipy.spatial.distance import cdist
from sklearn.decomposition import PCA

from transit_atlas import (
    DEFAULT_QUERY,
    FEATURES,
    LABELLED,
    MANIFEST,
    fit_reference,
    host_partition,
    load_snapshot,
    raw_measurements,
    synthetic_lookup,
    transform_measurements,
)


def main() -> None:
    manifest, rows, _, _ = load_snapshot(MANIFEST)
    training, scaler, scaled_training, partitions = fit_reference(rows)
    display_rows = sorted(
        [*training, *(row for row in rows if row.disposition == "CANDIDATE")],
        key=lambda row: row.koi_id,
    )
    pca = PCA(n_components=3, svd_solver="full").fit(scaled_training)
    display_vectors = scaler.transform(transform_measurements(raw_measurements(display_rows)))
    positions = pca.transform(display_vectors)

    validation = [
        row for row in rows if row.disposition in LABELLED and host_partition(row.host_id) == "validation"
    ]
    scaled_validation = scaler.transform(transform_measurements(raw_measurements(validation)))
    distances = cdist(scaled_validation, scaled_training, metric="euclidean")
    fifth_distances = np.partition(distances, 4, axis=1)[:, 4]
    output = {
        "snapshot": manifest,
        "default_query": DEFAULT_QUERY,
        "training_references": len(training),
        "validation_hosts": partitions["validation"]["hosts"],
        "distance_threshold": float(np.quantile(fifth_distances, 0.95)),
        "features": [
            {
                "field": feature.field,
                "name": feature.name,
                "unit": feature.unit,
                "log10": feature.log10,
                "mean": float(scaler.mean_[index]),
                "scale": float(scaler.scale_[index]),
            }
            for index, feature in enumerate(FEATURES)
        ],
        "variance_ratios": pca.explained_variance_ratio_.tolist(),
        "projection": {"mean": pca.mean_.tolist(), "components": pca.components_.tolist()},
        "teaching_example": synthetic_lookup(),
        "observations": [
            {
                "koi_id": row.koi_id,
                "host_id": row.host_id,
                "disposition": row.disposition,
                "values": row.values,
                "position": position.round(7).tolist(),
            }
            for row, position in zip(display_rows, positions, strict=True)
        ],
    }
    path = Path(__file__).resolve().parents[1] / "data/generated/catalogue.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(output, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
