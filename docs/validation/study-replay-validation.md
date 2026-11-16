# Study replay validation

## Scope

This validation covers the version 2 study-file provenance path for the bundled Kepler Q4 products selected by the application:

- Candidate: `K00115.03` (host `9579641`)
- Reference: `K02961.01` (host `10471515`)

The bundled products each contain 4,159 source cadences, of which 4,108 are retained after quality and validity filtering. Their original FITS source checksums are recorded in the study provenance.

## Fingerprint contract

The native Tauri command calculates SHA-256 over a JSON object containing `schema`, `version`, `identity`, `ephemeris`, `source`, `processing`, and `folded`, serialized by the pinned `serde_json` implementation. The fingerprint is deterministic for the bundled document representation; it is not a digital signature. The raw cadence array is intentionally excluded from the UI document; the source FITS SHA-256 and byte count bind the processed result to its source product.

Rust tests assert fixed native fingerprints for both bundled products. TypeScript integration tests independently verify the selected product identities, host IDs, FITS checksums, and cadence counts. A change to native serialization, product metadata, processing settings, ephemeris, or folded output must be reviewed as a provenance change.

## Automated validation

The following checks are automated:

- Version 1 studies remain readable without being represented as replay-verified.
- Version 2 studies reject malformed provenance, duplicate or mismatched roles, and missing required candidate/reference products.
- The real bundled candidate and reference product identities, host IDs, FITS checksums, cadence counts, and pinned native fingerprints match the pinned expectations.
- Native tests confirm that altering a processing setting or folded output changes the processing fingerprint.
- Altering the fingerprint presented during replay is rejected by `checkStudy`.
- Native tests verify that the bundled products load, fingerprints are reproducible, and changes to processing configuration or folded output change the digest.
- Native study-file tests cover atomic save/reopen behaviour and version 2 document validation.

## Results (16 November 2026)

- Bun study tests: 7 passed.
- TypeScript check and Vite production build: passed.
- Rust/Tauri tests: 7 passed, including fixed fingerprint regression checks for both products.

## Explicitly not claimed

The native macOS file-dialog workflow has not been exercised through the visible application window in this validation environment. The automated checks do not claim that a person has completed the GUI sequence of saving a study, reopening it, and inspecting the restored scene.

The restore implementation performs parsing, data reload, provenance/evidence comparison, and request-staleness checks before it mutates the active investigation. Failure-path UI preservation is supported by this ordering, but a full end-to-end UI interaction test remains outstanding.
