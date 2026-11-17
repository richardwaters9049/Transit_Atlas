# Multi-quarter PDCSAP validation

**Status: executed; no tested configuration met the predeclared multi-quarter preservation criteria.** See [the executed results and decision](pdcsap-multi-quarter-validation-results.md). This study extends the Q4 detrending-preservation experiment across all available Kepler long-cadence quarters for the same two targets. It tests whether the Q4 result is repeatable across observing quarters; it does not broaden the target population.

## Research question

Does additional Savitzky–Golay detrending reduce out-of-transit variability while preserving the observed and injected transit signals consistently across Kepler Q0–Q17, or do the Q4 distortions recur across quarters?

## Scope and sample

- Candidate: `K00115.03`, KIC `9579641`.
- Confirmed reference: `K02961.01`, KIC `10471515`.
- Archive products: Kepler long-cadence DR25 PDCSAP FITS products, Q0–Q17, one product per target/quarter (36 products total).
- Archive source: MAST public AWS mirror (`s3://stpubdata/kepler/public/lightcurves/...`). Original FITS bytes are stored under `data/raw/kepler-multi-quarter/`; product URI, filename, size, quarter, pipeline version, cadence count and SHA-256 are recorded in `data/raw/kepler-multi-quarter-products-2026-11-17.json`.
- Ephemerides: the already pinned NASA Exoplanet Archive cumulative-table snapshot from 15 November 2026. The same period, epoch and duration are used for all quarters. Propagated period/epoch uncertainty is calculated at each quarter's time span and reported; no per-quarter refitting is silently introduced.

This is a two-target, single-instrument, long-cadence DR25 study. It is not a population-level reliability estimate, a comparison of pipeline releases, or a claim that the archive ephemerides are exact.

## Data handling and controls

1. Keep every quarter as an independent time series. Do not concatenate flux for detrending, stitch quarter baselines, fill gaps or smooth across quarter boundaries.
2. Read `TIME`, `CADENCENO`, `SAP_QUALITY`, `PDCSAP_FLUX` and `PDCSAP_FLUX_ERR` from the same FITS binary table. SAP flux is not part of this study.
3. Validate KIC, quarter, DR25 release, BKJD/TDB time convention, required columns and unique increasing selected cadence identity.
4. Apply the existing quality rule `(SAP_QUALITY & 1130799) == 0`, plus finite TIME and PDCSAP flux. Preserve the original cadence numbers and report raw, quality-rejected, invalid and selected counts.
5. Split within each quarter at gaps greater than five times the median accepted cadence spacing. No interpolation or filter operation crosses a segment boundary.
6. Retain the original Q4 FITS files and compare their checksums with the downloaded Q4 products. The Q4 reference results must be reproducible from the exact same bytes.

## Processing comparison

The primary control is unflattened PDCSAP. Apply second-order Savitzky–Golay trends with 101- and 201-cadence windows, each in two modes:

- **Unmasked:** estimate the trend from all valid flux cadences.
- **Transit-masked:** exclude the ephemeris-predicted transit windows, padded by 1.5 transit durations plus propagated period/epoch uncertainty.

The 401-cadence window from the Q4-only experiment is intentionally not part of the all-quarter primary comparison: Q0 is a short commissioning quarter, and requiring a 401-cadence segment would make the full-quarter comparison incomplete. The 101/201 cadence configurations are held constant across Q0–Q17. Report nominal window duration per quarter from its measured cadence spacing.

Flattening is division by a positive trend. Divide PDCSAP uncertainty by the same trend. Record trend range, segment lengths, mask coverage and any configuration that cannot be evaluated; do not silently omit failed quarters.

## Measurements

For every target and quarter, record:

- FITS checksum and archive provenance; cadence and quality accounting; quarter time span and segment/gap summary.
- Propagated ephemeris uncertainty at the quarter midpoint, in hours and as a fraction of transit duration.
- Unflattened and derived descriptive windowed-median transit depths, in/out-of-transit MAD, folded 31-bin transit profiles and half-depth width diagnostics.
- Per-configuration change in depth and shape relative to that quarter's unflattened PDCSAP control.
- Uncertainty distributions before and after division by the trend.
- Deterministic injection/recovery at 0.5x, 1x and 2x the pinned catalogue depth, using 12 fixed phase offsets per target/quarter/depth. The injection train skips individual events overlapping real-transit masks or major data gaps; accepted and skipped event counts are retained. Injection and no-injection series are processed as pairs.
- No-injection phase-offset null controls for every configuration.

The synthetic signals are controlled trapezoidal probes with 15% ingress/egress fractions. They are not limb-darkened physical transit models. Windowed-median depths and folded half-depth widths are descriptive diagnostics, not fitted physical transit parameters.

## Predeclared decision rules

The primary unit of replication is the target-quarter pair, not an individual cadence or injection. Summaries must show each quarter as well as target-level distributions; do not pool all cadences and present them as independent replicates.

A configuration is considered preservation-eligible only if, for each target:

- At least 15 of 18 quarters are evaluable; all exclusions and reasons are listed.
- In every evaluable quarter, median injection recovery at each of the three depths is 0.90–1.10 and recovery IQR is at most 0.20.
- At least 90% of evaluable quarters have absolute descriptive real-depth change no greater than 10%, and no quarter has a change greater than 20% without an identified data/ephemeris limitation.
- At least 90% of evaluable quarters have folded half-depth width ratio between 0.90 and 1.10; any apparent ingress/egress distortion is reported for visual review.
- Out-of-transit MAD improves by at least 5% in the median quarter, without a median worsening greater than 5% for the other target.

These are predeclared engineering screens for this small validation, not universal astrophysical standards. If a target's propagated ephemeris uncertainty exceeds half its transit duration, that quarter is marked ephemeris-limited and cannot count as a clean preservation success; it remains in the report. If too few quarters pass the data/ephemeris checks, the outcome is inconclusive rather than a detrending pass.

A pass would justify only a further independent validation with more targets and quarters. It would not change the application default. A failure or inconclusive result keeps unflattened PDCSAP as the sole application baseline.

## Reproduction

From the repository root:

```bash
python -m pip install -r reference/requirements.txt
python reference/pdcsap_multi_quarter.py
python -m unittest discover -s reference -p 'test_*.py' -v
```

The script is offline after the raw FITS products and pinned ephemeris snapshot have been acquired. It verifies every raw product checksum before analysis. Generated results are written to `data/generated/pdcsap-multi-quarter/` and include a machine-readable analysis, Markdown report, per-target quarter plots and the complete injection/null-control ledger.

## Scientific safeguards

- Original FITS files are immutable inputs; their SHA-256 values are retained.
- Q0–Q17 remain independent; no quarter stitching, baseline matching or gap filling is performed.
- No SAP series, CBV fitting, new ephemeris fit, catalogue feature changes, scaler changes or KNN ranking changes are introduced.
- Q4 is retained as an internal replication point and must agree with the already published Q4 analysis when the same settings are selected.
- No detrended product is promoted into the desktop application as a result of this experiment.

## Next step

The offline Q0–Q17 analysis has been executed for both targets. All four configurations fail the overall preservation criteria; Q4 reproduces the earlier study exactly. See [the executed results](pdcsap-multi-quarter-validation-results.md). Keep unflattened PDCSAP as the baseline. The next study should use a broader, pre-registered target sample and stronger physical injection/null controls.
