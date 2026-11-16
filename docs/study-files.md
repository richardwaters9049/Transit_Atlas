# Portable investigation studies

## Purpose

A Transit Atlas study preserves an investigation selection and the evidence used to display it. Version 2 extends the .atlas.json format so a saved investigation can also identify the Kepler light-curve products that were selected and verify that the same derived curves are available when the study is reopened.

The study stores references and fingerprints, not a second copy of the FITS cadence arrays. The original FITS files remain the source data, and the bundled light-curve documents remain the app's offline display inputs.

## Version 2 provenance

The root document retains its existing schema identifier and model identifier, and increments the study version to 2. The provenance.light_curves field is an array. It contains one entry for each selected product that is actually available:

- Signal identity: KOI ID, host KIC ID and candidate/reference role.
- Product identity: archive, mission, MAST data URI, product filename, original FITS SHA-256 and byte count, author, quarter, data release, cadence and time units.
- Signal ephemeris: period in days, epoch in BKJD, duration in hours and epoch definition.
- processing_fingerprint: SHA-256 digest of the exact product, signal and derived folded result.

The candidate and reference are recorded separately. A host KIC identifies the star, while the KOI and ephemeris identify the signal being folded. A reference product is not inferred merely because the host has other signals.

An empty array means that no bundled light-curve product was selected for that study. An unavailable reference curve is not recorded as if it had been loaded.

## Processing fingerprint

The desktop backend computes a SHA-256 fingerprint over a deterministic JSON object containing:

1. Light-curve schema and version.
2. Signal identity.
3. Signal ephemeris, including its source metadata.
4. Complete archive product metadata, including the original FITS SHA-256.
5. Processing configuration: reader and version, flux column, quality mask and rule, normalisation and phase-folding convention.
6. Folded output: normalisation baseline, cadence counts, transit display width and every ordered folded point.

JSON object keys are serialised deterministically by serde_json; array order is retained. The raw cadence arrays are not duplicated into this fingerprint input because their original file is already bound by the source FITS SHA-256. The folded points are included, so a change to the derived series changes the fingerprint even if the source and settings are unchanged.

The fingerprint is a reproducibility checksum, not a digital signature or proof of scientific validity. It does not establish that the chosen ephemeris is physically correct.

## Replay validation

When a version 2 study is opened, Transit Atlas:

1. Parses and validates the stored product identity, ephemeris and fingerprint.
2. Requests each saved KOI and quarter from the app's bundled light-curve catalogue.
3. Reconstructs the product identity and ephemeris metadata from the returned document.
4. Compares the reconstructed metadata and processing fingerprint with the saved values.
5. Continues restoring the catalogue investigation only if the light-curve replay matches.

A missing product, changed FITS source, changed ephemeris, changed processing configuration or changed folded output prevents the study from being silently restored as if it were identical.

Version 1 studies remain readable for compatibility. They predate light-curve provenance, so their original catalogue and investigation evidence are still checked, but they cannot receive the additional light-curve replay check.

## Current scope and limitations

The desktop bundle currently includes the Q4 long-cadence products for candidate K00115.03 and reference K02961.01. Other selected references may not have a bundled curve; in that case the study records only the available candidate product.

The .atlas.json file does not embed the FITS files. Reopening on another installation therefore requires the same bundled product to be present. A future external-product workflow would need an explicit portable attachment or a user-selected local source file, followed by the same checksum and processing checks.

## Implementation and verification

- Study schema, parsing and replay checks: [study-file.ts](../desktop/src/study-file.ts)
- Fingerprint generation and bundled product command: [Tauri backend](../desktop/src-tauri/src/main.rs)
- FITS reading and phase-fold reference implementation: [kepler_lightcurve.py](../reference/kepler_lightcurve.py)
- Offline source-to-folded-series tests: [test_kepler_lightcurve_archive.py](../reference/test_kepler_lightcurve_archive.py)
- Study schema and replay tests: [study-file.test.ts](../desktop/tests/study-file.test.ts) (`cd desktop && bun run test`)
- Light-curve data contract and equations: [light-curves.md](light-curves.md)
