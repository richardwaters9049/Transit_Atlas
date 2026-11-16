# Research roadmap

## The first research use case

Develop Transit Atlas for researchers triaging Kepler candidates for further vetting. Start with one question. **Can plausible changes in the fitted measurements change which archived signals are most comparable, and what does the underlying light curve show in that case?**

The desktop already exposes why one reference ranks above another and how much the 3D view hides. The current benchmark measures agreement with cumulative archive labels. A research workflow needs to take a flagged comparison back to measured flux, identify the processing choices on which it depends, and let another analyst rerun the case. Kepler Data Validation already supplies pipeline light curves, models and diagnostic reports. The proposed contribution is a reproducible link between those products and an auditable claim about ranking sensitivity. [Kepler Data Validation](https://exoplanetarchive.ipac.caltech.edu/docs/KeplerDV.html) · [Current evaluation](evaluation.md)

## Archive access and offline replay

Keep the analysis local. Add explicit archive import so an analyst can fetch a chosen Kepler light curve or Data Validation product, or open a FITS file they already have. Cache the exact bytes and record the source product URI, SHA-256, archive release, quarter or cadence where applicable, Kepler host ID, and the signal-to-product mapping used. A saved study should replay those same bytes, processing settings and results without a connection. Let users select a new archive release as a separate input so an update is a named comparison.

Offline operation makes a reviewed case portable and reproducible. The limiting factor today is the packaged catalogue’s scope. It contains fitted summary measurements, while MAST archives the photometry and NASA’s Data Validation products provide associated models and diagnostics. On-demand retrieval adds that evidence without making archive availability a dependency of reopening a study. [MAST Kepler product types](https://archive.stsci.edu/kepler/data_products.html) · [MAST archive manual](https://archive.stsci.edu/files/live/sites/mast/files/home/missions-and-data/k2/_documents/MAST_Kepler_Archive_Manual_2020.pdf)

## First milestone · exact rank sensitivity

Implemented as **Check exact bounds**. The app determines when the nearest reference stays first throughout the declared measurement ranges or produces a specific set of measurements that changes it. The calculation uses all eight dimensions with the same fixed scaler and eligible reference pool.

For nominal nearest reference $a$, challenger $b$, and standardised query $z$, the difference between squared distances is affine in $z$.

$$
G_{a,b}(z)=\|z-b\|^2-\|z-a\|^2
          =2z^\mathsf{T}(a-b)+\|b\|^2-\|a\|^2.
$$

Each coordinate’s transform is monotone on its valid domain. Transform both ends of each finite admissible interval to obtain bounds $[\ell_j,u_j]$ in standardised space. A fixed coordinate has equal bounds. Minimise $G$ by choosing $\ell_j$ where $a_j-b_j\geq 0$ and $u_j$ where it is negative. Doing this for every eligible challenger gives the complete nearest-neighbour check for the declared box. A positive minimum means $a$ remains closer than that challenger everywhere. A negative minimum gives an explicit point where $b$ beats $a$. Rerank all references there to find the actual new winner. Treat equality according to the KOI tie rule, and flag ambiguous floating-point comparisons for closer review. If a logged interval reaches zero, the finite-box calculation needs a justified positive lower bound for that coordinate.

### Checked example from the current data

For `K00100.01`, all 64 scenarios keep the nominal winner `K03457.01`. The exact check against challenger `K00121.01` gives a squared-distance gap of **+0.664367** at the nominal measurements and **−0.516418** at the minimising corner. Reranking the whole pool at that corner makes **`K00121.01`** first. This is a concrete ranking change that the sampling missed. Its physical plausibility depends on how the measurements covary.

Run the desktop's existing scenario calculation from the repository root to check the 64/64 result.

```bash
cargo run --locked -p atlas-core --example stability -- K00100.01
```

Run this independent calculation from the repository root. It uses the existing packaged data and Python’s standard library.

```python
import json
import math
from pathlib import Path

data = Path("data/generated")
catalogue = json.loads((data / "catalogue.json").read_text())
ranges = json.loads((data / "uncertainties.json").read_text())["ranges"]
rows = {row["koi_id"]: row for row in catalogue["observations"]}

def scale(values):
    return [
        ((math.log10(value) if feature["log10"] else value)
         - feature["mean"]) / feature["scale"]
        for value, feature in zip(values, catalogue["features"], strict=True)
    ]

query = rows["K00100.01"]
baseline = scale(rows["K03457.01"]["values"])
challenger = scale(rows["K00121.01"]["values"])
corner = scale([
    (bounds[0] if a >= b else bounds[1]) if bounds else value
    for a, b, value, bounds in zip(
        baseline, challenger, query["values"], ranges[query["koi_id"]], strict=True
    )
])

def gap(z):
    return math.dist(z, challenger) ** 2 - math.dist(z, baseline) ** 2

references = [
    row for row in rows.values()
    if row["host_id"] != query["host_id"] and row["disposition"] != "CANDIDATE"
]
winner = min(references, key=lambda row: (
    math.dist(corner, scale(row["values"])), row["koi_id"]
))
print(f"{gap(scale(query['values'])):+.6f}")
print(f"{gap(corner):+.6f}")
print(winner["koi_id"])
```

The desktop shows the measurement ranges and the witness ranking side by side. A saved study stores both positions, the range digest and the checked evidence, and reruns the calculation on open. The Rust tests compare the corner method with exhaustive enumeration and exercise an equal-distance boundary, fixed coordinates and a real logarithmic boundary. A future evaluation can measure how often the 64 scenarios miss a change across the catalogue and assess the role of measurement covariance. [Current sensitivity method](mathematics.md#measurement-sensitivity)

## Second milestone · replay the observational evidence (in progress)

1. Match each selected KOI to the correct archive product. Where a Data Validation file contains several signals for one host, require an explicit Threshold Crossing Event mapping. Preserve the original time system, flux units, quality flags and source metadata.
2. Display the folded light curve and individual transit windows for the candidate and a selected reference. Reuse established FITS and light-curve tooling. Record the flux column, ephemeris and any quality mask or detrending settings. Cross-check reference outputs in a Lightkurve notebook.
3. Compare a documented baseline with one alternative processing choice or a leave-one-quarter-out run. Show the measurements and rank changes alongside the flux comparison. When inputs are insufficient, report which calculation is unavailable.
4. Export the source manifest, settings, relevant numerical series and rank evidence so collaborators can inspect the figures and regenerate them.

### Implementation status · 16 November 2026

The first implementation slice covers archive ingestion, reproducible phase folding, the desktop inspector and portable version 2 studies. Fixed-fingerprint replay, failure-preserving restore, a manual native macOS save/open smoke test and a repeatable Accessibility-driven GUI harness now cover the pinned candidate/reference case. The experiment is now specified, but comparative numerical results have not yet been produced. The remaining scientific work is to run the paired SAP/PDCSAP analysis (or a multi-quarter leave-one-quarter-out study when those inputs are available), then export the source manifest, settings, numerical series and ranking evidence:

- [x] Add a versioned `transit-atlas.kepler-lightcurve` JSON contract with the KOI, KIC, ephemeris, MAST product identity, FITS checksum, source cadence arrays and derived folded series.
- [x] Add a Lightkurve FITS reader that preserves all cadences and quality flags before applying a recorded mask.
- [x] Implement deterministic phase folding, per-product median normalisation, uncertainty propagation and cadence accounting.
- [x] Add a public MAST AWS mirror download path and an offline FITS import path.
- [x] Validate KOI role, KIC host, period and duration against the pinned catalogue/ephemeris, and validate FITS host, quarter, data release, BKJD format and TDB time scale.
- [x] Document the time system, equations, quality-mask rule, units, provenance and current limitations in [light-curves.md](light-curves.md).
- [x] Verify the importer against two real MAST public AWS mirror FITS products: Q4 long-cadence DR25 files for K00115.03 (KIC 9579641) and K02961.01 (KIC 10471515). Both original FITS files are pinned under data/raw/kepler-lightcurves/.
- [x] Pin the two signal ephemerides from the NASA Exoplanet Archive cumulative table, including period, epoch and duration uncertainties, in data/raw/kepler-lightcurve-ephemerides-2026-11-15.json.
- [x] Generate versioned offline JSON documents under data/generated/lightcurves/. Each product contains 4,159 source cadences; 4,108 remain after the declared quality and finite-value checks.
- [x] Add an offline replay test that re-reads each pinned FITS file, recalculates the folded series and compares every point with the saved document.
- [x] Add a desktop inspector panel that loads the bundled candidate and selected reference, and draws their independently folded Q4 series.
- [x] Launch the desktop app and visually review the two curves, chart scaling and narrow transit-duration window. The candidate and reference plots were inspected in the native macOS app; the user also checked the application at multiple window sizes.
- [x] Add study-file schema version 2 with selected light-curve product identity, signal ephemeris and processing fingerprint alongside the existing ranking evidence. Reopening a v2 study reloads the recorded KOI/quarter and rejects a changed product or folded result. Version 1 studies remain readable.
- [x] Complete a native macOS save/open smoke test with the pinned candidate and reference products. Verify native Save/Open dialogs, candidate and selected-neighbour restoration, both light-curve provenance records, camera restoration, and rejection of a tampered processing fingerprint without replacing the active investigation. The observed sequence and limits are recorded in [study-replay-validation.md](validation/study-replay-validation.md).
- [x] Add a repeatable macOS GUI harness for the native Save/Open flow. It checks candidate/reference restoration, both Q4 provenance records, cadence summaries, camera orientation restoration by comparing plot captures, and active-investigation preservation after a tampered fingerprint. See [macos-study-ui-harness.md](validation/macos-study-ui-harness.md).
- [x] Specify the first controlled processing-sensitivity experiment: paired SAP versus PDCSAP flux from the same pinned Q4 FITS products, a fixed windowed-median depth statistic, and a one-coordinate substitution into the frozen 8D KNN feature space. See [pdcsap-sap-sensitivity-study.md](pdcsap-sap-sensitivity-study.md).

The importer has been exercised through the public MAST AWS mirror for both pinned products. The Python suite has 28 passing tests, including checksum verification and offline recomputation of every folded point from each original FITS file. The desktop plots have been visually reviewed, and a screenshot of the candidate/reference inspector is included in the README. Study-file v2 persistence, fixed-fingerprint replay checks, failure-preserving restore tests, the native macOS save/open smoke test and the repeatable macOS GUI harness are complete for the documented candidate/reference case. Broader saved-view, missing-product, cancellation and failure-path coverage remains outstanding.

[Kepler cadence and quality flags](https://lightkurve.github.io/lightkurve/tutorials/2-creating-light-curves/2-2-kepler-noise-1-data-gaps-and-quality-flags.html) · [Lightkurve documentation](https://lightkurve.github.io/lightkurve/)

## What would demonstrate research value

- **Independent numerical reproduction.** Review a fixed set of confirmed, false-positive and ambiguous cases from disjoint hosts. Compare time and flux transformations with a named notebook and show where the conclusions disagree.
- **Useful triage.** In a pilot with researchers who vet transit candidates, compare the app with their archive-and-notebook workflow on the same tasks. Record time to a defensible explanation, missed known issues and misleading flags. Agree the success measures before the pilot and publish failures alongside successes.
- **Scientific evidence quality.** Report performance by signal strength, data gaps and number of observed transits. For claims about sensitivity or reliability, test against suitable injected transits and instrumental false-alarm controls. Kepler’s DR25 study provides examples of using injections, inverted light curves and scrambled light curves for validation. [Thompson et al. (2018)](https://doi.org/10.3847/1538-4365/aab4f9) · [DR25 validation products](https://exoplanetarchive.ipac.caltech.edu/docs/Kepler_completeness_reliability.html)

The strongest portfolio demonstration would be one real candidate with a repeatable ranking change, the archive observations behind it, an independent numerical cross-check and a clear assessment of how the result affects a vetting decision.
