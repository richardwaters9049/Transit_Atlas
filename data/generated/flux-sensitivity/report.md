# SAP versus PDCSAP sensitivity results

**Status:** completed offline analysis. Measurements are descriptive, not transit-model fits.

## Method

- Shared quality mask: 1130799.
- Both flux columns are read from each same FITS file and restricted to paired finite cadences.
- Both variants use identical cadence IDs, quality flags, ephemeris and transit window.
- KNN substitutes only depth and retains the frozen training scaler and host-excluded pool.

## Measurements

| KOI | Cadences | PDCSAP depth (ppm) | SAP depth (ppm) | SAP − PDCSAP (ppm) | Relative change | SAP/PDCSAP MAD ratio (in/out) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| K00115.03 | 4108 | 17.8638 | 22.3829 | 4.5191 | 25.30% | 6.46x / 6.56x |
| K02961.01 | 4108 | 46.4210 | 111.6763 | 65.2553 | 140.57% | 8.01x / 7.43x |

## Scatter and quoted uncertainties

| KOI | Flux | In-transit MAD (ppm) | Out-of-transit MAD (ppm) | Median uncertainty (ppm) |
| --- | --- | ---: | ---: | ---: |
| K00115.03 | PDCSAP | 81.74 | 90.22 | 84.29 |
| K00115.03 | SAP | 527.92 | 591.59 | 84.27 |
| K02961.01 | PDCSAP | 193.29 | 225.30 | 74.04 |
| K02961.01 | SAP | 1547.44 | 1673.92 | 74.09 |

## KNN ranking sensitivity

### K00115.03

Catalogue depth: 23.2000 ppm.

| Depth input | Top five KOIs (distance; depth squared contribution) |
| --- | --- |
| Catalogue | K02961.01 (0.48494; 0.02172); K03172.02 (0.51094; 0.05307); K06871.01 (0.51568; 0.02207); K02636.01 (0.51918; 0.03225); K07709.01 (0.54869; 0.15598) |
| PDCSAP measured | K02961.01 (0.52637; 0.06361); K06871.01 (0.55504; 0.06422); K02636.01 (0.56408; 0.08089); K03172.02 (0.56600; 0.11236); K04288.03 (0.60283; 0.00698) |
| SAP diagnostic (unreliable) | K02961.01 (0.48950; 0.02616); K03172.02 (0.51759; 0.05990); K06871.01 (0.52000; 0.02655); K02636.01 (0.52433; 0.03762); K07709.01 (0.55913; 0.16755) |

### K02961.01

Catalogue depth: 33.5000 ppm.

| Depth input | Top five KOIs (distance; depth squared contribution) |
| --- | --- |
| Catalogue | K06871.01 (0.35712; 0.00000); K04383.01 (0.46399; 0.09865); K06419.01 (0.48564; 0.00423); K07709.01 (0.49094; 0.06129); K02623.01 (0.49282; 0.03554) |
| PDCSAP measured | K06871.01 (0.37992; 0.01681); K04383.01 (0.38757; 0.03358); K02722.03 (0.43190; 0.09575); K07709.01 (0.43971; 0.01362); K02623.01 (0.45897; 0.00333) |
| SAP diagnostic (unreliable) | K02722.03 (0.30432; 0.00182); K02333.01 (0.37525; 0.00150); K04383.01 (0.38100; 0.02852); K01589.04 (0.39351; 0.02016); K00929.02 (0.41359; 0.00013) |

## Interpretation and limitations

The SAP series is visibly dominated by large coherent variation in both targets. Its normalized in-transit/out-of-transit MAD is 6.46x/6.56x PDCSAP for K00115.03 and 8.00x/7.43x for K02961.01. The SAP windowed-median depths and corresponding rankings are therefore retained as diagnostics only and are not reliable transit-depth estimates. No detrending or transit model was introduced. PDCSAP measurements are also descriptive windowed medians, not validated physical transit fits.

Only one Q4 product per KOI was analysed. The result does not establish multi-quarter repeatability or generalisation to other targets.

## Reproducibility

Run from the repository root:

    .venv/bin/python reference/flux_sensitivity.py
    .venv/bin/python -m unittest reference.test_flux_sensitivity

Python 3.14.5; NumPy 2.3.5; Astropy 8.0.2; scikit-learn 1.8.0; Matplotlib 3.11.2.

Machine-readable cadence series, FITS SHA-256 values, selection counts, scaler parameters and full top-five distance evidence are in analysis.json.
