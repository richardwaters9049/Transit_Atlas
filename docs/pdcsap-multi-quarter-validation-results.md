# Multi-quarter PDCSAP validation results

## Executive result

**No tested detrending configuration meets the predeclared multi-quarter preservation criteria. Unflattened PDCSAP remains the application baseline.** The Q4 result is reproduced exactly from the newly acquired Q4 archive products, and the signal-distortion problem is not confined to Q4: across the other quarters, the tested filters frequently change the descriptive transit depth and folded shape while reducing out-of-transit scatter.

This is a two-target validation of one Kepler DR25 long-cadence pipeline product family. It is not a population-level estimate and does not establish that every Kepler target behaves the same way.

## Dataset and provenance

- 36 MAST public AWS mirror products: Q0–Q17 for K00115.03 (KIC 9579641) and K02961.01 (KIC 10471515).
- All products identify as Kepler DR25. Original FITS files are retained under `data/raw/kepler-multi-quarter/`.
- The complete product manifest records each MAST S3 URI, filename, quarter, byte count, cadence count, pipeline version and SHA-256 in `data/raw/kepler-multi-quarter-products-2026-11-17.json`.
- Both newly downloaded Q4 products are byte-for-byte identical to the original pinned Q4 FITS files used by the earlier study. Their source hashes match exactly.
- The ephemerides remain the pinned 15 November 2026 NASA Exoplanet Archive cumulative-table snapshot. The period, epoch and duration are held fixed across quarters; uncertainty is propagated to each quarter midpoint.
- Maximum propagated one-sigma epoch uncertainty is 0.545 hours for K00115.03 and 0.415 hours for K02961.01, both below half the respective catalogue transit duration. No quarter is classified as ephemeris-limited under the predeclared rule.

## Processing

Each quarter is processed independently. There is no cross-quarter stitching, quarter-baseline matching, gap filling or smoothing across boundaries. The analysis reads `TIME`, `CADENCENO`, `SAP_QUALITY`, `PDCSAP_FLUX` and `PDCSAP_FLUX_ERR` from the same FITS table; SAP flux is not used.

The quality rule is `(SAP_QUALITY & 1130799) == 0`, with finite TIME and PDCSAP flux. Each quarter is split at gaps greater than five times its median accepted cadence spacing. The comparison applies second-order Savitzky–Golay windows of 101 and 201 cadences, each with unmasked and transit-masked trend estimation. The 401-cadence setting was not included in the all-quarter comparison because it cannot be supported consistently in the short commissioning quarter and shorter gap-separated segments. Unsupported quarter/configuration combinations are recorded, not silently discarded. The 101-cadence configurations are unsupported in Q17 because one gap-separated segment has only 78 cadences; transit-masked 101-cadence processing is also unsupported in Q2 because the remaining unmasked segment data are insufficient. The 201-cadence configurations are unsupported in Q2, Q12, Q13 and Q17 because one or more segments are shorter than the window.

For every supported quarter/configuration, the analysis measures the descriptive windowed-median depth, out-of-transit MAD, folded transit profile, half-depth width, trend range and uncertainty distribution. It also performs paired injection/recovery at 0.5x, 1x and 2x catalogue depth, with 12 deterministic phase offsets per quarter/depth and no-injection phase-offset null controls. Injected events overlapping the real-transit mask or major data gaps are skipped and counted.

The injections are trapezoidal recovery probes, not physical limb-darkened transit models. The windowed depths and folded widths are descriptive statistics, not fitted physical transit parameters.

## Quarter coverage and baseline measurements

| Target | Quarter products | Maximum propagated timing uncertainty | 101-cadence unmasked support | 101-cadence masked support | 201-cadence support (either mode) |
|---|---:|---:|---:|---:|---:|
| K00115.03 | 18 | 0.545 h | 17/18 | 16/18 | 14/18 |
| K02961.01 | 18 | 0.415 h | 17/18 | 16/18 | 14/18 |

The Q4 controls reproduce the prior experiment exactly:

| Target | Q4 PDCSAP depth | Q4 out-of-transit MAD | Prior Q4 result |
|---|---:|---:|---|
| K00115.03 | 17.864 ppm | 90.223 ppm | Exact numerical match |
| K02961.01 | 46.421 ppm | 225.299 ppm | Exact numerical match |

Baseline depths vary substantially by quarter, including values close to zero and negative descriptive depths. These should not be interpreted as physical negative transit depths; they show that a fixed-window median statistic is noisy and sensitive to quarter-specific variability for these signals.

## Multi-quarter results

### Candidate K00115.03

| Configuration | Median depth change | Quarters within 10% | Median OOT MAD improvement | Injection recovery across evaluable quarters |
|---|---:|---:|---:|---|
| Unmasked, 101 | +27.20% | 2/17 | 45.38% | Fail |
| Transit-masked, 101 | +142.58% | 2/16 | 44.62% | Fail |
| Unmasked, 201 | +31.82% | 1/14 | 40.85% | Pass on recovery only; insufficient quarter coverage and preservation failure |
| Transit-masked, 201 | +33.53% | 1/14 | 40.25% | Fail |

### Confirmed reference K02961.01

| Configuration | Median depth change | Quarters within 10% | Median OOT MAD improvement | Injection recovery across evaluable quarters |
|---|---:|---:|---:|---|
| Unmasked, 101 | +17.35% | 1/17 | 57.06% | Fail |
| Transit-masked, 101 | +39.85% | 0/16 | 57.73% | Fail |
| Unmasked, 201 | +13.71% | 2/14 | 49.83% | Pass on recovery only; insufficient quarter coverage and preservation failure |
| Transit-masked, 201 | +19.36% | 1/14 | 49.91% | Pass on recovery only; insufficient quarter coverage and preservation failure |

“Pass on recovery only” means the median recovery and IQR checks were within their numerical bounds in all evaluable quarters for the three injected depths. It does not mean the configuration passed the overall experiment. The 201-cadence settings have only 14 evaluable quarters, below the 15-quarter minimum, and fail the real-depth and folded-shape criteria.

All four configurations fail the overall criteria for both targets. The 101-cadence settings have sufficient quarter coverage but preserve the descriptive depth in only 0–2 of the evaluable quarters, far below the required 90%. The 201-cadence settings lack sufficient coverage and also fail depth/shape preservation. Every configuration substantially reduces median out-of-transit MAD, but that improvement is accompanied by unacceptable signal changes.

The machine-readable `analysis.json` retains per-quarter values, per-configuration metrics, 4,392 paired injection/recovery and null-control records for supported configurations, cadence selection counts, gap segments, source checksums and propagated ephemeris uncertainties. The two target summary plots show the quarter-by-quarter depth and scatter behaviour.

## Decision

**Do not use any tested flattened series in the application. Keep unflattened PDCSAP as the sole baseline.** This multi-quarter result strengthens the Q4 finding: the scatter reduction is not sufficient evidence of better scientific data when the measured transit signal changes so substantially.

No application default, catalogue feature, frozen scaler, KNN ranking or saved-study format has changed.

## Reproduction

From the repository root:

```bash
python -m pip install -r reference/requirements.txt
python reference/pdcsap_multi_quarter.py
python -m unittest discover -s reference -p 'test_*.py' -v
```

The analysis is offline after the 36 original FITS products and pinned ephemeris snapshot are present. Every FITS file is checksum-verified before analysis. Outputs are under `data/generated/pdcsap-multi-quarter/`.

## Limitations and next research step

The same two targets are followed across quarters, so the 36 products are repeated observations of two systems, not 36 independent astrophysical targets. The analysis uses one fixed archive ephemeris per target and does not fit transit timing variations. The trapezoid injection model is deliberately simple. The descriptive window-depth statistic can become unstable when the true signal is small relative to the quarter's variability. These limitations are retained rather than hidden by pooling quarters.

The next scientifically useful extension is a pre-registered broader target sample containing confirmed planets, false positives and ambiguous candidates, selected across signal-to-noise and transit-count ranges. That study should add physical transit injection/recovery and appropriate instrumental/null controls before any processing method is reconsidered. Until then, unflattened PDCSAP remains the only application baseline.
