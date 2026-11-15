# Working on Transit Atlas

Transit Atlas is a local Kepler signal explorer. Keep the app focused on inspectable catalogue similarity. Describe archive dispositions as catalogue metadata and ground planet confirmation in independent evidence.

## Project layout

- `reference/` holds the Python data audit, reference KNN, tests and desktop data export.
- `data/raw/` holds the pinned NASA extracts and provenance manifests.
- `data/fixtures/` holds the checked Python lookup that Rust tests against.
- `data/generated/` holds the offline catalogue consumed by the Rust app.
- `crates/atlas-core/` contains Rust scaling, neighbour lookup and tests.
- `desktop/` contains the TypeScript and Three.js interface. `desktop/src-tauri/` owns the native window and application commands.
- `docs/` contains the scientific methods, evaluation, macOS screenshots and walkthroughs.

## Numerical invariants

- Keep feature order, units and transforms in sync with the Python reference.
- Fit frozen scaling and display PCA on labelled training hosts only. Keep all signals from a host in the same partition for evaluation.
- Rank in the eight-dimensional standardised space using squared Euclidean distance, then KOI ID for ties. Exclude the query’s entire host from the ranked references.
- Treat the three-component PCA as display geometry. Use Rust’s ranked IDs for highlights and show the retained variance.
- Keep the original measurements and units available in the distance breakdown. Reconcile each squared distance with its eight feature contributions.
- Document the extraction query, version and SHA-256 for any new snapshot. Regenerate the desktop export through `reference/export_desktop.py` when the snapshot or feature definition changes. Keep GUI builds offline at runtime.

## Before handing off

Run the project's checks in the existing iTerm tab at the project root so the output is visible.

From the project root, run `python -m unittest discover -s reference -v` and `cargo test -p atlas-core --locked`. From `desktop/`, install the locked dependencies and run `bun run build`. Verify the default KOI, a second candidate and the teaching projection when changing the desktop workflow. Record only observed completion and evidence in the Transit Atlas project tracker.
