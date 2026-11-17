# Multi-quarter PDCSAP validation results

**Decision:** No tested configuration meets the multi-quarter preservation criteria; retain unflattened PDCSAP as the application baseline.

The 36 DR25 long-cadence products are processed independently by quarter. The same pinned NASA Exoplanet Archive ephemerides are used throughout; propagated timing uncertainty is reported and ephemeris-limited quarters are not counted as clean preservation successes.

## Target-quarter results

### K00115.03 — candidate

| Q | Cadences | Segments | Ephemeris σ (h) | Baseline depth (ppm) | Baseline OOT MAD (ppm) |
|---:|---:|---:|---:|---:|---:|
| 0 | 469 | 1 | 0.264 | 150.547 | 171.168 |
| 1 | 1624 | 1 | 0.264 | 68.084 | 160.036 |
| 2 | 4070 | 5 | 0.265 | 62.856 | 216.415 |
| 3 | 4134 | 5 | 0.270 | 32.649 | 89.580 |
| 4 | 4108 | 3 | 0.278 | 17.864 | 90.223 |
| 5 | 4486 | 3 | 0.289 | 38.114 | 98.214 |
| 6 | 4272 | 3 | 0.303 | 1.665 | 88.444 |
| 7 | 4226 | 4 | 0.319 | 9.004 | 86.508 |
| 8 | 3106 | 2 | 0.337 | 35.499 | 116.039 |
| 9 | 4608 | 4 | 0.356 | 22.760 | 129.068 |
| 10 | 4441 | 3 | 0.379 | 2.693 | 132.623 |
| 11 | 4473 | 5 | 0.402 | 2.833 | 102.720 |
| 12 | 3550 | 6 | 0.425 | -2.060 | 129.493 |
| 13 | 4241 | 4 | 0.448 | -2.607 | 273.779 |
| 14 | 4269 | 4 | 0.473 | -15.386 | 132.703 |
| 15 | 4366 | 4 | 0.501 | 19.433 | 432.316 |
| 16 | 3534 | 3 | 0.527 | 2.144 | 178.270 |
| 17 | 1284 | 3 | 0.545 | 5.531 | 199.748 |

| Configuration | Median depth change | Quarters within 10% | Median OOT MAD improvement | Injection recovery pass across quarters |
|---|---:|---:|---:|---|
| unmasked_101 | 27.20% | 2/17 | 45.38% | fail / insufficient |
| transit_masked_101 | 142.58% | 2/16 | 44.62% | fail / insufficient |
| unmasked_201 | 31.82% | 1/14 | 40.85% | fail / insufficient |
| transit_masked_201 | 33.53% | 1/14 | 40.25% | fail / insufficient |

### K02961.01 — reference

| Q | Cadences | Segments | Ephemeris σ (h) | Baseline depth (ppm) | Baseline OOT MAD (ppm) |
|---:|---:|---:|---:|---:|---:|
| 0 | 469 | 1 | 0.195 | 95.384 | 72.428 |
| 1 | 1624 | 1 | 0.195 | 84.283 | 114.150 |
| 2 | 4070 | 5 | 0.196 | 56.720 | 125.452 |
| 3 | 4134 | 5 | 0.200 | 38.898 | 160.562 |
| 4 | 4108 | 3 | 0.206 | 46.421 | 225.299 |
| 5 | 4486 | 3 | 0.215 | 37.453 | 189.876 |
| 6 | 4272 | 3 | 0.226 | 23.088 | 179.933 |
| 7 | 4226 | 4 | 0.239 | 10.098 | 105.888 |
| 8 | 3106 | 2 | 0.253 | 4.936 | 102.588 |
| 9 | 4614 | 4 | 0.268 | 45.810 | 90.629 |
| 10 | 4441 | 3 | 0.285 | 23.036 | 138.821 |
| 11 | 4477 | 5 | 0.303 | 30.211 | 106.511 |
| 12 | 3550 | 6 | 0.321 | -15.584 | 117.581 |
| 13 | 4245 | 4 | 0.339 | 41.440 | 160.760 |
| 14 | 4271 | 4 | 0.359 | -52.703 | 229.685 |
| 15 | 4367 | 4 | 0.381 | -30.650 | 130.596 |
| 16 | 3538 | 3 | 0.401 | -76.589 | 130.484 |
| 17 | 1285 | 3 | 0.415 | -130.574 | 133.428 |

| Configuration | Median depth change | Quarters within 10% | Median OOT MAD improvement | Injection recovery pass across quarters |
|---|---:|---:|---:|---|
| unmasked_101 | 17.35% | 1/17 | 57.06% | fail / insufficient |
| transit_masked_101 | 39.85% | 0/16 | 57.73% | fail / insufficient |
| unmasked_201 | 13.71% | 2/14 | 49.83% | fail / insufficient |
| transit_masked_201 | 19.36% | 1/14 | 49.91% | fail / insufficient |

## Decision details

The decision rules and their engineering (non-universal) status are defined in [the protocol](../../docs/pdcsap-multi-quarter-validation.md). Q0–Q17 are independent quarter-level units; cadences and injection offsets are not treated as independent target replications. The trapezoidal injections are recovery probes, not physical transit models. No application default, catalogue feature, scaler or KNN ranking is changed.
