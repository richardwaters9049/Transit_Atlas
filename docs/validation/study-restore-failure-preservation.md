# Study restore failure preservation

## Purpose

A saved investigation must not replace the currently active investigation unless its saved evidence has been replayed and verified successfully. A failed file parse, unavailable source product, changed catalogue or processing fingerprint, changed evidence, missing selected neighbour, or stale search must leave the active investigation untouched.

## Commit boundary

`desktop/src/main.ts` performs study restoration in two phases:

1. **Prepare and verify:** open and parse the file; validate the catalogue snapshot; recompute the saved candidate's nominal neighbours and selected view; reload each recorded Kepler light-curve product; compare product provenance and processing fingerprints; compare the complete saved evidence; resolve the selected neighbour's verified rank; and confirm that no newer search has superseded the restore request.
2. **Commit:** only after all checks succeed does the application advance its request generation and replace the active investigation, then restore the saved view and camera.

The small `commitVerifiedRestore` helper makes this ordering an explicit, testable contract. It runs verification before invoking the state-commit callback. If verification throws, the callback is never called.

## Automated regression tests

`desktop/tests/study-restore.test.ts` checks that:

- a processing-fingerprint verification failure leaves the active investigation unchanged;
- a stale-search failure leaves the active investigation unchanged;
- successful verification runs before the commit callback and commits the prepared investigation.

These tests exercise the actual helper used by the restore path. They are state-boundary unit tests, not a claim that the native macOS open-file dialog or complete GUI interaction has been visually tested.

## Verification commands

From `desktop/`:

```sh
bun run test
bun run build
```

From `desktop/src-tauri/`:

```sh
cargo test --locked
cargo fmt --all -- --check
```
