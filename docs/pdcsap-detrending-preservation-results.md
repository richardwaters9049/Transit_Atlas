# PDCSAP detrending and transit-preservation results

## Executive result

**No tested detrending configuration met all predeclared preservation and scatter criteria. Unflattened PDCSAP remains the baseline.** The experiment reduced out-of-transit median absolute deviation (MAD) in every tested configuration, sometimes substantially, but those reductions came with unacceptable changes to the measured real transit depths and/or folded transit shapes for at least one of the two targets.

This is a two-target, single-quarter method experiment. It is not evidence that the same behaviour applies to the full Kepler population or to other quarters. The numerical thresholds are engineering decision rules for this experiment, not universal astrophysical standards.

## Reproduction

From the repository root, install the pinned Python reference dependencies and run:

```bash
python -m pip install -r reference/requirements.txt
python reference/pdcsap_detrending.py
python -m unittest discover -s reference -p 'test_*.py' -v
```

The script reads only the two pinned Q4 DR25 FITS products under `data/raw/kepler-lightcurves/` and the pinned NASA Exoplanet Archive ephemerides in `data/raw/kepler-lightcurve-ephemerides-2026-11-15.json`. It writes:

- `data/generated/pdcsap-detrending/analysis.json` — checksums, software versions, cadence-level original/trend/flattened flux and uncertainty, masks, all injection recoveries, null controls, folded profiles and configuration decisions.
- `data/generated/pdcsap-detrending/report.md` — generated summary of the numerical results.
- One plot per target — original PDCSAP, six estimated trends, six flattened series and the duration-scaled folded real-transit profiles.

## Method actually executed

- Source columns: `TIME`, `CADENCENO`, `SAP_QUALITY`, `PDCSAP_FLUX` and `PDCSAP_FLUX_ERR` from each original FITS binary table. SAP flux is not used.
- Quality selection: `(SAP_QUALITY & 1130799) == 0`, with finite time and PDCSAP flux. Both products retain 4,108 selected cadences from 4,397 raw rows.
- Each time series is split at gaps greater than five times its median accepted cadence spacing. Each target has three segments (1,499, 607 and 2,002 cadences); no smoothing bridges those gaps.
- Savitzky–Golay polynomial order 2, with 101, 201 and 401 cadence windows. Each window is tested with an unmasked trend and a trend excluding the ephemeris transit windows.
- Transit masks extend 1.5 catalogue durations from each predicted centre plus propagated epoch/period uncertainty. Flattened flux and uncertainty are both divided by the same positive trend.
- Synthetic signals are deterministic trapezoids with 15% ingress/egress fractions, pinned period and duration, and depths of 0.5x, 1x and 2x the catalogue depth. Twelve phase offsets per target/depth are selected from a fixed 48-point grid. Individual events that would intersect a real-transit mask or a major data gap are skipped; accepted event counts are recorded. Injection and no-injection copies are processed in pairs.
- Recovery is calculated from the paired flux ratio at the injected cadences against the surrounding non-injected cadences. The complete per-injection ledger and no-injection phase-offset null depths are retained.

The trapezoid is a controlled signal-recovery probe, not a limb-darkened physical transit model. The fixed-window depths remain descriptive statistics, not fitted physical depths.

## Results

### Candidate K00115.03 — KIC 9579641

Unflattened PDCSAP depth is **17.864 ppm** and out-of-transit MAD is **90.223 ppm**.

| Configuration | Real depth (ppm) | Depth change | Folded half-depth width ratio | OOT MAD (ppm) | MAD improvement | Injection recovery at 0.5x / 1x / 2x |
|---|---:|---:|---:|---:|---:|---:|
| Unmasked, 101 | 22.722 | +27.20% | 0.900 | 68.153 | 24.46% | 0.867 / 0.867 / 0.867 |
| Masked, 101 | 18.189 | +1.82% | 1.350 | 68.330 | 24.27% | 0.917 / 0.956 / 0.961 |
| Unmasked, 201 | 20.025 | +12.10% | 1.350 | 68.390 | 24.20% | 0.977 / 0.977 / 0.977 |
| Masked, 201 | 28.241 | +58.09% | 1.350 | 68.557 | 24.01% | 0.947 / 0.960 / 0.975 |
| Unmasked, 401 | 28.524 | +59.67% | 1.000 | 75.494 | 16.33% | 1.016 / 1.016 / 1.016 |
| Masked, 401 | 26.068 | +45.93% | 1.250 | 75.348 | 16.49% | 0.965 / 0.976 / 0.983 |

### Confirmed reference K02961.01 — KIC 10471515

Unflattened PDCSAP depth is **46.421 ppm** and out-of-transit MAD is **225.299 ppm**.

| Configuration | Real depth (ppm) | Depth change | Folded half-depth width ratio | OOT MAD (ppm) | MAD improvement | Injection recovery at 0.5x / 1x / 2x |
|---|---:|---:|---:|---:|---:|---:|
| Unmasked, 101 | 21.153 | −54.43% | 0.808 | 59.774 | 73.47% | 0.875 / 0.875 / 0.875 |
| Masked, 101 | 17.171 | −63.01% | 0.808 | 60.020 | 73.36% | 1.003 / 0.995 / 0.997 |
| Unmasked, 201 | 24.180 | −47.91% | 0.654 | 71.977 | 68.05% | 0.974 / 0.974 / 0.974 |
| Masked, 201 | 22.807 | −50.87% | 0.500 | 72.169 | 67.97% | 0.993 / 0.996 / 0.998 |
| Unmasked, 401 | 86.283 | +85.87% | 1.115 | 127.455 | 43.43% | 1.025 / 1.025 / 1.025 |
| Masked, 401 | 88.055 | +89.69% | 1.115 | 127.386 | 43.46% | 0.966 / 0.982 / 0.991 |

The null-control depths at the selected injection phases remain in the machine-readable ledger and summary. They are useful for understanding the background phase-dependent variability, but do not rescue configurations that fail the real-signal preservation checks.

## Decision against the predeclared criteria

A configuration had to meet all of the following for both targets: median recovery between 0.90 and 1.10 at every injected depth; recovery IQR no wider than 0.20; real-signal depth change no greater than 10%; no systematic shape narrowing; and at least 5% out-of-transit MAD improvement for one target without more than 5% worsening for the other.

**None passed.** In particular, every configuration changes the reference target's descriptive real depth by more than 10% (the range is approximately −63% to +90%). Several configurations also narrow its folded half-depth width. The strong scatter reductions therefore cannot be interpreted as a useful improvement in transit-preserving data quality.

The folded half-depth width is a coarse numerical screen, not a substitute for visual expert assessment of ingress/egress morphology. The per-target plots and 31-bin duration-scaled profiles are retained for review. The decision is already negative on the real-depth criterion, so no subjective plot assessment can turn this experiment into a passing configuration.

## Scientific safeguards and scope

- Original FITS bytes and PDCSAP arrays are not modified.
- No SAP series, quarter stitching, gap filling, CBV fitting, new ephemeris fit, catalogue feature changes or scaler changes are introduced.
- The application continues to use unflattened PDCSAP. No default or KNN ranking evidence is changed.
- The experiment is limited to two Q4 targets and cannot establish quarter-to-quarter consistency or population-level performance.
- The recovery thresholds are engineering thresholds for this small controlled experiment, not universal astrophysical standards.

## Next step

Do not promote any tested flattened series into the application. The next research step should be independently designed before expanding the sample: obtain additional quarters for the same targets, define a quarter-combination strategy, and validate against a broader set of injected signals and control cases. Keep the unflattened PDCSAP product as the sole application baseline in the meantime.
