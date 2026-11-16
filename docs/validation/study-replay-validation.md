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

The native macOS GUI sequence below was exercised manually through the bundled Tauri application. It is a recorded GUI smoke test, not a repeatable automated GUI test or a substitute for the automated checks above.

## Native macOS GUI save/open smoke test (16 November 2026)

### Conditions

- Repository branch: `test/native-study-replay-validation`, at `4483560` (`test: preserve active study on failed replay`).
- Built and launched the macOS app bundle from the repository using `cd desktop && bun run tauri build --bundles app --config '{"bundle":{"active":true}}'`; the generated bundle was `target/release/bundle/macos/Transit Atlas.app`. The configuration override was a command-line build setting and did not modify the tracked Tauri configuration.
- Interacted with the visible app window and native macOS Save/Open dialogs using the desktop UI automation bridge.
- The bundled catalogue snapshot shown by the app was dated 14 November 2026. The source products were the pinned Q4 products described above.
- The successful study was saved to `/tmp/K00115.03.gui-validation.atlas.json`; the deliberately altered copy was `/tmp/K00115.03.gui-validation-invalid.atlas.json`. These temporary files are test artifacts, not catalogue inputs.

### Observed sequence and results

1. Launched the app. The default investigation was `K00115.03`; selected neighbour `K02961.01` was rank 1. Both candidate and reference Q4 light curves were displayed with 4,108 of 4,159 cadences and their source checksums.
2. Saved through **Save Study** and the native Save dialog. The app reported `Saved K00115.03.gui-validation.atlas.json`. The resulting file was 9,426 bytes and parsed as schema `transit-atlas.study`, version 2, with candidate `K00115.03`, selected neighbour `K02961.01`, and two light-curve provenance entries. The entries carried the pinned FITS hashes and native fingerprints `b2c5aae1…e18440e` (candidate) and `2d64ea1d…b33c9239d` (reference).
3. Changed the active candidate to `K00005.01` and confirmed its different ranking (rank 1 `K01090.01`). Reopened the saved study through the native Open dialog. The app reported `Opened study for K00115.03`; the query, selected neighbour, distance breakdown, both product provenance summaries and folded curves returned to the saved state.
4. Rotated the 3D scene by dragging, then reopened the same study. The scene returned to its saved orientation, visibly distinct from the intervening rotated view. The saved camera position was `[7.243387427662842, 5.05887375900262, 11.497440361369593]`, target `[0, 0, 0]`, with neighbour focus off.
5. Changed the active investigation back to `K00005.01`. Created a copy of the saved file with the candidate light-curve `processing_fingerprint` replaced by 64 zeroes, then selected it in the native Open dialog. The app rejected replay with `The saved Kepler light-curve products or processing fingerprints differ from the current replay.` The active query remained `K00005.01`, with rank 1 `K01090.01` and its distance breakdown still present.

### Limits

This was one successful visible macOS run, not a deterministic automated GUI test, and it did not exercise every study view or every possible failure class. It validates the native dialog route and the concrete success/failure state-preservation cases above. The temporary study files were stored outside the repository. A repeatable GUI harness remains future work if these interactions need continuous integration coverage.
