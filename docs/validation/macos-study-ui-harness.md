# Native macOS study UI harness

## Purpose

This is a repeatable, interactive macOS GUI test for the version 2 study save/open workflow. It drives the built Tauri application and the native macOS file dialogs through Accessibility, rather than calling the save and restore functions directly.

Run it from the repository root:

```bash
bun run test:macos-ui
```

The command builds the macOS application bundle with a command-line `bundle.active` override. It does not change the tracked Tauri configuration.

## Prerequisites

- macOS with the Xcode command-line tools, Rust/Cargo, Bun and Python 3.
- An interactive logged-in desktop session. This is not a headless or CI test.
- Accessibility permission for the terminal or automation host running the script. Enable it under **System Settings → Privacy & Security → Accessibility**.
- Transit Atlas must be closed before starting. The harness checks for an existing `transit-atlas` process and exits rather than taking over a user's running app.
- The application window should be on the main display at its normal 1440 × 940 layout.

No third-party GUI automation package is required. The harness uses AppleScript/System Events, Swift, macOS Accessibility, CoreGraphics and the built-in `screencapture` utility.

## Test sequence

1. Build and launch the actual `Transit Atlas.app` bundle.
2. Save the default `K00115.03` investigation through the native Save dialog into a fresh temporary directory.
3. Validate the resulting JSON: schema version 2, candidate `K00115.03`, selected neighbour `K02961.01`, two Q4 provenance records and a three-dimensional saved camera position and target.
4. Capture the plot, drag to a visibly different 3D orientation, and capture it again.
5. Change the active candidate to `K00005.01`, then open the saved study through the native Open dialog.
6. Assert that the app restores `K00115.03`, selected neighbour `K02961.01`, both Q4 light-curve product labels and their 4,108/4,159 cadence summaries.
7. Capture the plot after replay and compare it with the original and rotated captures. The rotated capture must differ by a mean sampled RGB difference above 1.5; the restored capture must be below 0.5. The cursor is moved outside the plot before capture so hover state does not contaminate the comparison.
8. Create a copy with the candidate processing fingerprint replaced by 64 zeroes. Change the active candidate back to `K00005.01`, open the tampered copy through the native Open dialog, and assert that replay is rejected while `K00005.01`, its `K01090.01` nearest neighbour and distance breakdown remain visible.
9. Close the app and retain the temporary JSON and PNG test artefacts for inspection.

## Scope and limitations

The harness covers one pinned candidate/reference pair, schema version 2, the catalogue view, native Save/Open dialogs, selected light-curve provenance, camera restoration and preservation of the active investigation after a processing-fingerprint mismatch.

It does not yet cover version 1 studies, every saved view type, missing archive products, every native-dialog cancellation/error path, multiple display arrangements or a headless CI runner. It also does not replace the Python/Rust/TypeScript tests or the manual GUI smoke-test record in [study-replay-validation.md](study-replay-validation.md).

## Results · 16 November 2026

The full `bun run test:macos-ui` command completed successfully twice on the target Mac. The second run also verified that the harness preserves the pre-test clipboard contents, exits cleanly and leaves no Transit Atlas process running.

- Tauri release app bundle built successfully. Vite retained its existing non-blocking warning that the Three.js chunk is slightly above 500 kB.
- Native Save/Open restored `K00115.03`, selected neighbour `K02961.01`, both Q4 product records and the 4,108/4,159 cadence summaries.
- The camera image difference was **10.085** after the deliberate drag and **0.000** after replay on the latest run, passing the configured thresholds.
- A copy with the candidate processing fingerprint replaced by 64 zeroes was rejected. The active `K00005.01` investigation, rank-1 neighbour `K01090.01` and distance breakdown remained visible.
- The latest full-run artefacts were retained at `/tmp/transit-atlas-study-ui.i0Fegg/` (study JSON, tampered JSON and three plot captures).
