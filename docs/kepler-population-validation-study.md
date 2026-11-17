# Kepler population-level validation: sample and protocol

**Status: sample frame generated; archive eligibility checks and the validation experiment have not yet been executed.** This document pre-registers the target-selection design and analysis safeguards before inspecting the selected targets' light curves. The 36-row manifest is a provisional sample frame, not a claim that all targets have suitable or retrievable observations.

## Research question

Do the observed-light-curve processing choices and diagnostic measurements used by Transit Atlas remain defensible across a deliberately varied Kepler KOI sample, rather than only the two systems used in the earlier PDCSAP studies? How do conclusions vary with archive disposition and signal-to-noise, and can the pipeline distinguish injected astrophysical transits from instrumental or non-transit structure?

The study is a validation of the light-curve evidence and processing diagnostics. It is not a new estimate of Kepler catalogue completeness, reliability, or astrophysical occurrence rates. The sample is not a random draw from the underlying planet population.

## Frozen sample frame

- Archive snapshot: NASA Exoplanet Archive `cumulative` table retrieved 14 November 2026, DOI `10.26133/NEA4`, SHA-256 recorded in the sample manifest.
- Total: 36 KOIs across 36 distinct host stars.
- Disposition strata: 12 `CONFIRMED`, 12 `FALSE POSITIVE`, 12 `CANDIDATE`.
- Within each disposition: four targets in each empirical model-SNR tertile (low, middle, high).
- Candidate rows require finite positive model SNR, period, duration and depth, plus a valid KIC identifier.
- Selection is deterministic: empirical tertiles are calculated within each disposition, then rows are ordered by SHA-256 of the frozen seed, disposition, SNR stratum and KOI identifier. Four unique host stars are selected per disposition/stratum. No host is repeated anywhere in the 36-target sample.
- Seed: `TransitAtlas-Kepler-population-v1-2026-11-17`.

The machine-readable frame is `data/studies/kepler-population-sample-2026-11-17.json`. Rebuild it from the repository root with:

```bash
python reference/design_kepler_population_sample.py
python -m unittest reference.test_kepler_population_sample -v
```

The manifest records per-disposition eligibility counts, SNR boundaries, source checksum, selected catalogue measurements and the exact selection method. SNR strata are calculated separately within each disposition; therefore an SNR value in one disposition's low stratum is not necessarily comparable to another disposition's low stratum. This balances archive classes while retaining within-class signal-strength coverage.

## Archive eligibility gate (must precede sample lock)

For each provisional target, retrieve and validate DR25 Kepler long-cadence products from MAST. Preserve source URI, product filename, KIC, quarter, pipeline version, cadence count, original FITS bytes and SHA-256. Validate host identity, time system, required FITS columns, quality flags and cadence identity using the existing importer.

Before locking the final sample, report for each target:

- Available quarters and total raw/quality-usable cadences.
- Number of observed transit events within usable data, accounting for gaps and the pinned ephemeris.
- Usable out-of-transit baseline and quarter/segment gap structure.
- Whether period, epoch and duration uncertainties are available and how they propagate over the observed time span.
- Whether ephemeris uncertainty is small enough relative to transit duration for the planned event masks and phase-folded comparison.
- Missing products, duplicate or ambiguous KOI-to-KIC mappings, and any archive or data-quality limitation.

A target failing a predeclared eligibility criterion may be replaced only by the next deterministic unique-host row in the same disposition and SNR stratum. Preserve the excluded row, reason, replacement and selection order in the manifest. Do not replace a target because its light curve is noisy, inconvenient, visually unattractive or produces an unfavourable result. If a stratum cannot supply four eligible hosts, report the shortfall and revise the design before looking at outcome metrics; do not silently rebalance it.

Proposed minimum eligibility screen: at least three individually identifiable observed transit events, at least five transit durations of usable out-of-transit baseline in aggregate, valid DR25 PDCSAP flux and uncertainty, and no ephemeris uncertainty exceeding half the transit duration over the relevant observing span. These are engineering inclusion criteria for this pilot, not universal astrophysical standards. Report all values continuously as well as pass/fail. If the screen yields fewer than 30 targets or fewer than eight in any disposition, pause and revise the protocol before analysis.

## Processing arms and controls

1. **Primary observed-data control:** original, unflattened DR25 PDCSAP flux with the existing quality mask. Each quarter and each gap-separated segment is processed independently. No stitching, gap filling, quarter-baseline matching or cross-boundary smoothing.
2. **Candidate detrending arms:** second-order Savitzky–Golay windows of 101 and 201 cadences, unmasked and ephemeris-transit-masked. Retain the earlier multi-quarter rules and report unsupported segments; no configuration becomes an application default on the strength of this study alone.
3. **Independent pipeline check:** where a suitable Kepler Data Validation product exists, compare its recorded model/diagnostic products without treating the DV model as ground truth. Explicitly map the KOI to its TCE and record the mapping source.
4. **Negative controls:** inverted-flux events, phase-scrambled event times and transit-free windows. Keep each control type separate; an inverted light curve is not assumed to reproduce every instrumental false alarm.
5. **Instrumental controls:** retain quality-flagged cadences as a separate diagnostic-only set, inspect known discontinuity/gap boundaries, and quantify whether apparent detections cluster around quality events. Never mix rejected cadences into the primary science series.

## Physical transit injections

The previous studies used trapezoidal probes. This population study must add limb-darkened physical transit injections before making a broad preservation claim. Use a named, version-pinned transit-model implementation and record its version, parameters, units and numerical settings. The injection generator must support physically plausible impact parameter, scaled semi-major axis, radius ratio, limb-darkening coefficients and exposure-time integration. Do not infer missing stellar or orbital parameters silently: use documented catalogue values where suitable, otherwise use a declared parameter grid and label it as synthetic.

For each eligible target, generate paired no-injection and injection series on the same observed cadence timestamps and with the same noise, quality mask and processing path. Predeclare injection depths/radius ratios spanning the target's observed signal regime, impact parameters including grazing cases where geometrically valid, and several deterministic phase offsets. Exclude injected events that overlap real transits or major data gaps and report accepted/skipped counts. Preserve the unmodified observed series; injections are analysis copies only.

Measure recovery of injected depth, duration, ingress/egress shape and uncertainty, plus false-positive response in the paired no-injection series. Injection recovery is a controlled diagnostic, not a claim that synthetic noise perfectly reproduces astrophysical populations or all instrumental systematics.

## Outcomes and statistical unit

The target is the primary replication unit; quarters and individual transit events are nested observations, not independent targets. Report per-target outcomes, then stratify by disposition and SNR. Avoid treating thousands of cadences or injection events as independent sample size.

Primary outcomes:

- Real-event depth and duration preservation relative to unflattened PDCSAP.
- Physical injection depth/duration/shape recovery and uncertainty calibration.
- False-positive detections in each negative/instrumental control.
- Processing-induced changes to transit significance and diagnostic classification.
- Fraction of targets/quarters for which a processing arm is unsupported, and reasons.

Secondary outcomes include out-of-transit robust scatter, cadence retention, transit count, ephemeris phase drift and rank/feature sensitivity. Show distributions and individual target plots; publish failures and missingness. Confidence intervals must respect target-level clustering (for example, bootstrap by host star), and class-specific conclusions must state their small sample sizes.

## Decision safeguards

- Unflattened PDCSAP remains the application baseline throughout this study.
- No catalogue feature, frozen scaler, KNN reference pool, ranking threshold or desktop default changes as part of the experiment.
- Predeclare exact numerical pass/fail thresholds in a follow-up protocol amendment before generating injection outcomes. Thresholds must be justified against model precision and the intended triage use, not chosen after seeing results.
- A positive result supports a further independent validation, not automatic deployment.
- A negative or inconclusive result is reported without changing the baseline.
- Archive disposition is a label for sample stratification, not a physical ground-truth label for every transit event; false positives can contain astrophysical variability and candidates can include real planets.

## Current status and next step

The deterministic 36-target sample frame is generated and tested. The next implementation milestone is the archive-eligibility audit: retrieve the required MAST products, validate target/product identity and quantify coverage before locking the final sample. Only after that gate should the physical injection model and outcome thresholds be frozen.
