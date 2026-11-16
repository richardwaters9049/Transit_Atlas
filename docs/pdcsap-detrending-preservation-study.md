# PDCSAP detrending and transit-preservation experiment

## Status and purpose

**Status: experiment designed; no processing results generated.**

This study is the next controlled processing-sensitivity experiment for the pinned Kepler Q4 DR25 products. It asks whether a transparent, local trend estimate can reduce residual low-frequency variation in PDCSAP without attenuating a transit-shaped signal. It does not assume that additional flattening is beneficial: PDCSAP is already conditioned for transit searches, so leaving it unchanged is the essential control.

The study is deliberately limited to the two existing products:

- Candidate: K00115.03, KIC 9579641, Q4.
- Confirmed reference: K02961.01, KIC 10471515, Q4.

Both have 4,397 raw FITS rows and approximately 90 days of coverage. Their pinned durations are 3.133 hours and 2.924 hours respectively. This is a two-target, single-quarter method study, not a population-level validation.

## Research question

Does a masked, local Savitzky–Golay trend estimate improve the out-of-transit stability of the existing PDCSAP series while preserving the depth and shape of known and injected transit signals?

The experiment must answer separately:

1. How much low-frequency variation is removed?
2. How much does the measured depth and shape of the real folded signal change?
3. Does the method recover synthetic transit injections at known depths and durations?
4. Is any improvement large enough to justify keeping a detrended series as an optional analysis product?

A lower scatter statistic alone is not evidence of a better light curve. A filter that suppresses both noise and transits has failed.

## Pinned inputs and controls

Use the original, checksummed Q4 FITS files and read PDCSAP_FLUX and PDCSAP_FLUX_ERR only. Keep the current baseline untouched. Do not substitute SAP in this experiment.

Hold constant:

- FITS bytes, target identity, quarter, release, cadence numbers and timestamps.
- Pinned KOI-specific period, epoch and duration, including the recorded ephemeris provenance.
- Existing quality bitmask 1,130,799 and the rule `(quality & mask) == 0`.
- Finite-value selection and cadence identity.
- Original PDCSAP flux and uncertainty arrays.
- Transit phase convention, depth estimator and all comparison windows.
- No quarter stitching, gap filling, CBV fitting, new ephemeris fit or catalogue/scaler changes.

Keep the original time series in memory and in the output. Detrending is a derived branch, never an overwrite of the archive data.

## Candidate detrending method

Use a second-order Savitzky–Golay filter as a deliberately simple, reproducible local trend estimator. This is the method wrapped by Lightkurve's `LightCurve.flatten`; its window length is measured in samples and must be a positive odd integer. Lightkurve also supports a transit mask so masked points are excluded from the trend fit and interpolated across for trend estimation.

Evaluate these predeclared windows:

| Window | Approximate duration at Kepler long cadence | Relative to a 3-hour transit |
| ---: | ---: | ---: |
| 101 cadences | 2.06 days | about 16 transit durations |
| 201 cadences | 4.12 days | about 33 transit durations |
| 401 cadences | 8.24 days | about 66 transit durations |

The exact cadence spacing must be measured from each FITS product and recorded; the day values above are nominal planning values. Use polynomial order 2 for all three windows. Split the series at large time gaps using a declared threshold of five times the median accepted cadence spacing. Do not silently bridge data gaps.

Run two variants for each window:

- **Unmasked diagnostic:** estimate the trend using all accepted cadences. This measures how much a conventional flattening pass can absorb transit signal.
- **Transit-masked candidate:** exclude the known ephemeris transit windows from trend fitting. Pad each mask to 1.5 times the catalogue duration on either side of transit centre, and include the recorded epoch/period uncertainty in the mask extent at the relevant cadence time. Document the exact mask equation and count of excluded cadences.

Return the trend as a separate series. Flatten by dividing PDCSAP flux and its uncertainty by the same positive trend estimate. Reject a run if any trend value used for normalization is non-finite or non-positive. Do not fill missing flux cadences or alter the quality selection.

This is an experiment with one candidate filter family and a small, predeclared window grid. Do not tune the window separately until a preferred-looking plot appears. If all windows fail the preservation checks, report that and retain the unflattened PDCSAP baseline.

## Transit-preservation tests

### 1. Real-signal comparison

For the real ephemeris, measure the existing descriptive windowed-median depth on:

- Unflattened PDCSAP (control).
- Each unmasked flattened series.
- Each transit-masked flattened series.

Use the same fixed transit window and out-of-transit definition as the SAP/PDCSAP sensitivity study. Report depth in ppm, in/out counts, MAD and uncertainty summaries. Also compare the folded transit shape in duration-scaled phase coordinates. These are descriptive measurements, not fitted physical depths.

### 2. Synthetic injection and recovery

A filter can look smooth while attenuating transits. Test that directly by injecting synthetic periodic transit trains into copies of the original PDCSAP series.

- Use a deterministic trapezoidal transit profile with the pinned period and duration. State explicitly that this is a controlled signal-recovery probe, not a limb-darkened physical transit model.
- Inject at phase offsets separated from the real ephemeris. Validate every selected offset against the real transit mask and reject any injection whose in-transit cadences overlap the real transit mask or a major data gap.
- Use depths of 0.5x, 1x and 2x the catalogue depth for each target.
- Use at least 12 deterministic, evenly distributed valid phase offsets per depth/target, recording the exact offsets and random-free construction.
- For every injection, process paired copies: no detrending, unmasked detrending and transit-masked detrending. The injection mask must be included in the trend-exclusion mask for the masked run; otherwise the method is not being given the preservation protection it claims to use.
- Recover the injected depth with the same fixed-window statistic, after subtracting the matching no-injection control at the same phase. This paired difference avoids attributing pre-existing stellar variability to the injected signal.

Report per-injection recovered depth, recovery ratio, scatter and failures, then median and spread by target, injected depth, window and mask mode. Keep the complete injection ledger in machine-readable output.

### 3. Negative and null controls

Include a no-injection run through every processing configuration. It must not produce a synthetic detection at the injected phase. Also include a phase-offset null test outside all injected and real transit windows. These controls help expose bias from the windowed estimator or residual stellar variability.

## Metrics and predeclared decision rules

Report all metrics per target and per filter configuration:

- Robust out-of-transit scatter: MAD of normalized relative flux in ppm, excluding real and injected transit masks.
- Real-signal depth change relative to unflattened PDCSAP.
- Injection recovery ratio (recovered depth divided by injected depth), median and interquartile range.
- Transit-shape comparison at matched phase bins, including ingress/egress and duration-scaled width.
- Trend positivity, finite cadence count, number and size of time gaps, mask coverage and boundary effects.
- Uncertainty propagation using flux_err / trend, with the original and transformed uncertainty distributions reported.

A configuration is **eligible for further consideration**, not automatically accepted, only if:

1. Median injection recovery is between 0.90 and 1.10 at all three injected depths for both targets.
2. The interquartile range of recovery ratios is no wider than 0.20.
3. Real-signal depth changes by no more than 10% relative to unflattened PDCSAP, unless the injection evidence demonstrates that the baseline estimator itself is biased and the discrepancy is explained.
4. No systematic transit-shape narrowing or ingress/egress loss is visible in the binned injection comparisons.
5. Out-of-transit MAD improves by at least 5% for at least one target, without worsening by more than 5% for the other.

If no configuration meets all preservation criteria, the conclusion is that additional flattening is not justified for these products. If a configuration passes preservation but does not materially improve scatter, keep unflattened PDCSAP as the sole baseline. Even a passing result does not change the application's default processing: it can only support an explicitly labelled optional derived view pending broader validation.

These thresholds are engineering decision rules for this small experiment, not universal astrophysical standards. State that limitation prominently.

## Reproducibility and required outputs

The implementation must be deterministic and runnable offline from the pinned FITS bytes. Record:

- FITS SHA-256, product metadata, KOI/KIC/quarter/release and ephemeris provenance.
- Python, Lightkurve, SciPy, NumPy and Astropy versions.
- Quality mask, cadence selection, cadence spacing, gap segmentation and all filter parameters.
- Transit mask definition, padded windows and exact excluded cadence IDs.
- Every injection phase, depth, duration, template definition and overlap validation.
- Per-cadence original flux, trend, flattened flux, uncertainty and transit/injection flags.
- Per-configuration metrics, all injection recoveries and null controls.
- A plot showing original PDCSAP, estimated trend, flattened series and real/injected phase-folded comparisons.

Add tests for deterministic masks, gap splitting, trend positivity, uncertainty division, injected depth recovery on a noiseless synthetic series, no cadence identity changes, and no mutation of source arrays. The report must be regenerated from the machine-readable analysis, not manually edited.

## Scope boundaries

Do not change the desktop's PDCSAP default, the KNN catalogue feature values, the frozen scaler or any ranking evidence in this experiment. Do not claim that flattening recovers a more physically accurate planet radius or transit depth. Do not treat a synthetic trapezoid as a validated transit model.

Only Q4 is currently pinned for these two targets. This study cannot establish quarter-to-quarter consistency, long-baseline stability or general performance across the Kepler population. A later multi-quarter experiment needs additional quarters for the same KOIs and a predeclared quarter-combination strategy.

## Scientific references

- [Lightkurve `LightCurve.flatten`](https://lightkurve.github.io/lightkurve/reference/api/lightkurve.LightCurve.flatten.html) — documents Savitzky–Golay flattening, window length, gap splitting and the transit-mask option.
- [NASA Exoplanet Archive: Kepler Data Products Overview](https://exoplanetarchive.ipac.caltech.edu/docs/Kepler_Data_Products_Overview.html) — describes cotrending basis vectors and their use in mitigating common-mode instrumental effects.
- [Kepler Science Operations: Data pipeline](https://keplergo.github.io/KeplerScienceWebsite/pipeline.html) — explains how PDC identifies astrophysical events and the different treatment of variable and quiet stars.
- [Kepler Data Processing Handbook](https://archive.stsci.edu/kepler/manuals/KSCI-19081-003-KDPH.pdf) — describes PDC-MAP's constrained cotrending and the importance of avoiding over-fitting.

## Decision after design

The next implementation step is to build the offline reference experiment and its synthetic injection/recovery tests against the two pinned Q4 products. No scientific result should be claimed until those tests and the complete analysis have run successfully.
