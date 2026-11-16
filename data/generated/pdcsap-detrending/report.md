# PDCSAP detrending and transit-preservation results

**Status:** completed offline two-target Q4 method experiment. Results are descriptive; trapezoidal injections are controlled recovery probes, not physical transit models.

## Method

- Quality bitmask: `1130799`; selected finite TIME/PDCSAP_FLUX cadences.
- Savitzky–Golay polynomial order: `2`; windows: `101, 201, 401` cadences.
- Time series split at gaps greater than five times median accepted cadence spacing.
- Masked trend excludes ephemeris transits padded by 1.5 durations plus propagated epoch/period uncertainty.
- Injection design: 12 deterministic phase offsets per target and depth; 0.5x, 1x and 2x catalogue depth.
- Flattened uncertainty is PDCSAP_FLUX_ERR divided by the same positive trend.
- Null controls measure the no-injection processed series at each deterministic injection phase; folded shape profiles are stored in the JSON output and shown in the plots.

## Results

### K00115.03

- Cadences: 4108; segments: 3; real-mask cadences: 257.
- Baseline depth: 17.864 ppm; baseline out-of-transit MAD: 90.223 ppm.

| Configuration | Depth (ppm) | Depth change | Shape width ratio | OOT MAD (ppm) | MAD improvement | 0.5x / 1x / 2x median recovery | Null depth (ppm) |
|---|---:|---:|---:|---:|---:|---:|---:|
| unmasked_101 | 22.722 | 27.20% | 0.900 | 68.153 | 24.46% | 0.867 / 0.867 / 0.867 | 0.469 |
| transit_masked_101 | 18.189 | 1.82% | 1.350 | 68.330 | 24.27% | 0.917 / 0.956 / 0.961 | 3.211 |
| unmasked_201 | 20.025 | 12.10% | 1.350 | 68.390 | 24.20% | 0.977 / 0.977 / 0.977 | -1.059 |
| transit_masked_201 | 28.241 | 58.09% | 1.350 | 68.557 | 24.01% | 0.947 / 0.960 / 0.975 | -0.109 |
| unmasked_401 | 28.524 | 59.67% | 1.000 | 75.494 | 16.33% | 1.016 / 1.016 / 1.016 | -1.231 |
| transit_masked_401 | 26.068 | 45.93% | 1.250 | 75.348 | 16.49% | 0.965 / 0.976 / 0.983 | -1.736 |

### K02961.01

- Cadences: 4108; segments: 3; real-mask cadences: 219.
- Baseline depth: 46.421 ppm; baseline out-of-transit MAD: 225.299 ppm.

| Configuration | Depth (ppm) | Depth change | Shape width ratio | OOT MAD (ppm) | MAD improvement | 0.5x / 1x / 2x median recovery | Null depth (ppm) |
|---|---:|---:|---:|---:|---:|---:|---:|
| unmasked_101 | 21.153 | -54.43% | 0.808 | 59.774 | 73.47% | 0.875 / 0.875 / 0.875 | -0.974 |
| transit_masked_101 | 17.171 | -63.01% | 0.808 | 60.020 | 73.36% | 1.003 / 0.995 / 0.997 | 2.136 |
| unmasked_201 | 24.180 | -47.91% | 0.654 | 71.977 | 68.05% | 0.974 / 0.974 / 0.974 | 5.218 |
| transit_masked_201 | 22.807 | -50.87% | 0.500 | 72.169 | 67.97% | 0.993 / 0.996 / 0.998 | 8.507 |
| unmasked_401 | 86.283 | 85.87% | 1.115 | 127.455 | 43.43% | 1.025 / 1.025 / 1.025 | -0.098 |
| transit_masked_401 | 88.055 | 89.69% | 1.115 | 127.386 | 43.46% | 0.966 / 0.982 / 0.991 | 2.532 |

## Interpretation and limitations

The predeclared eligibility rules are engineering decision thresholds for this small experiment, not universal astrophysical standards. A configuration is eligible only when every depth's median recovery is 0.90–1.10 for both targets, each recovery IQR is at most 0.20, real depth changes by at most 10%, shape checks show no systematic narrowing, and out-of-transit MAD improves by at least 5% for one target without worsening by more than 5% for the other.

The machine-readable output includes duration-scaled folded shape profiles, half-depth width ratios, no-injection phase-offset null depths and the complete injection ledger. The half-depth width is a coarse descriptive diagnostic; inspect the supplied time-series plots and phase profiles before any eligibility decision. This is a two-target, single-quarter study and cannot establish population-wide or multi-quarter behaviour.

**Experiment decision:** No tested configuration meets all predeclared engineering criteria; retain unflattened PDCSAP as the baseline.
The numerical shape-width screen is a conservative coarse check, not a replacement for expert review of ingress/egress morphology. No application default, catalogue feature, scaler or KNN ranking is changed.
