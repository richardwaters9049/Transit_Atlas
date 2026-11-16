# Transit Atlas documentation

This directory contains the scientific, mathematical and implementation documentation for Transit Atlas. Start with the guides below, then use the detailed methods and research records to reproduce the calculations.

## Scientific foundations

| Guide | Start here if you want to understand… |
| --- | --- |
| [K-nearest neighbours](knn.md) | What KNN is, how the five nearest references are selected, why `k = 5`, how the validation experiment works, and what a neighbour result can and cannot tell you. |
| [Linear algebra](linear-algebra.md) | Vectors, matrices, transforms, standardisation, Euclidean distance, squared contributions, PCA, SVD and the 3D projection. |
| [The eight-dimensional feature space](eight-dimensional-space.md) | What the eight axes represent, their archive fields and units, how raw values become an 8D point, and how the full-dimensional geometry is used. |

## Methods, evidence and reproducibility

| Document | Contents |
| --- | --- |
| [Mathematics](mathematics.md) | Detailed derivations for standardisation, exact distance contributions, PCA, uncertainty sampling, exact rank sensitivity and release comparison. |
| [Data and methods](methods.md) | NASA catalogue provenance, complete-case coverage, feature definitions, verified neighbour example and projection audit. |
| [Held-out evaluation](evaluation.md) | Host-based train/validation/test protocol, selection of `k`, baselines, confusion counts and failure analysis. |
| [Research roadmap](research-roadmap.md) | Research milestones, exact rank-sensitivity derivation, reproducible witness and remaining scientific work. |
| [Kepler light curves](light-curves.md) | FITS provenance, quality filtering, flux normalisation, phase folding and cadence-level reproduction. |
| [PDCSAP versus SAP sensitivity study](pdcsap-sap-sensitivity-study.md) | Controlled experiment design for measuring flux-processing sensitivity and its effect on the 8D KNN ranking. |
| [Portable investigation studies](study-files.md) | Version 2 study provenance, selected light-curve identity, processing fingerprints, replay validation and version 1 compatibility. |
| [Native macOS study UI harness](validation/macos-study-ui-harness.md) | Repeatable native Save/Open, camera restoration and failure-preservation checks through macOS Accessibility. |

## Visual evidence

The [`screenshots/`](screenshots/) directory contains current application captures used by the README. The [`videos/`](videos/) directory contains the desktop walkthrough and demo.

## Reproducing the project

The repository [README](../README.md#verify-the-calculations) contains the installation and verification commands. The scientific documents link to the corresponding Python reference, Rust implementation, pinned data and machine-readable results so that explanations can be checked against the code.
