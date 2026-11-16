# PDCSAP versus SAP: processing-sensitivity experiment

## Status and purpose

**Status: paired offline analysis completed; SAP was found unsuitable for depth inference without a separately specified detrending method.**

This document specifies the first controlled comparison for research-roadmap milestone 2, step 3. It compares the two flux columns already present in each pinned Kepler DR25 Q4 FITS product:

- **Baseline:** `PDCSAP_FLUX`, the pipeline's pre-search data-conditioned aperture photometry.
- **Alternative:** `SAP_FLUX`, the simple aperture photometry before the PDC systematic-error correction.

This is a useful paired experiment because both columns come from the same target, quarter, cadence sequence and original FITS bytes. It isolates the effect of the archive's PDC conditioning more cleanly than comparing unrelated products. It is not a contest in which SAP is presumed superior: PDCSAP is designed for transit searches, while SAP retains more instrumental and long-term variation. The SAP comparison is a sensitivity diagnostic.

## Research question

For the pinned candidate/reference pair, does switching from PDCSAP to SAP materially change the empirically estimated transit depth, and does substituting that depth into the existing eight-dimensional distance calculation change the nearest-neighbour ordering?

The result must distinguish three different statements:

1. The flux series differ.
2. The depth estimator differs under the two flux products.
3. The depth difference is large enough to change a KNN ranking under the existing fixed feature scaler and eligible reference pool.

A change in (1) does not imply (2), and a change in (2) does not imply (3).

## Pinned inputs

| Role | KOI | KIC | Quarter | FITS product |
| --- | --- | ---: | ---: | --- |
| Candidate | K00115.03 | 9579641 | Q4 | `data/raw/kepler-lightcurves/K00115.03-q04.fits` |
| Reference | K02961.01 | 10471515 | Q4 | `data/raw/kepler-lightcurves/K02961.01-q04.fits` |

Both FITS files contain `SAP_FLUX`, `SAP_FLUX_ERR`, `PDCSAP_FLUX` and `PDCSAP_FLUX_ERR`. The original FITS checksums and source metadata are already pinned in the generated light-curve documents. Use the same KOI-specific period, epoch and duration for both flux columns; do not infer the ephemeris from the host or from the other KOI.

This is a single-quarter case study, not a full-mission assessment. It cannot establish how the result generalises across quarters, targets or Kepler pipeline releases.

## Controlled variables

Keep the following identical between the baseline and alternative:

- Original FITS bytes, host, quarter, cadence numbers and timestamps.
- KOI-specific period, epoch, duration, BKJD/TDB time system and phase convention.
- Kepler quality bitmask **1,130,799** and the rule `(quality & mask) == 0`.
- Cadence validity rules and the intersection of cadences with finite time and finite values in both flux columns.
- Per-product median normalisation and ppm units for the plotted folded series.
- Transit phase window, out-of-transit comparison window, estimator and all numerical tolerances.
- Catalogue reference pool, host-exclusion rule, eight feature definitions, frozen training-derived means/scales, log transforms and deterministic KOI tie-break.

The two flux columns have separate uncertainty columns. Preserve and report their uncertainties; do not silently reuse PDCSAP errors for SAP or vice versa.

## Primary depth statistic

The first pass is a transparent, robust *descriptive depth statistic*, not a transit-model fit:

1. Apply the shared quality and paired-finite-cadence selection.
2. Fold each flux series on the same pinned ephemeris.
3. Define the in-transit window from the catalogue duration: `abs(phase) <= duration_hours / (48 * period_days)`.
4. Use the remaining accepted cadences as the out-of-transit comparison set.
5. Compute the median in-transit flux and median out-of-transit flux separately for each flux column.
6. Report depth in ppm as

   `depth_ppm = 1e6 * (median_out - median_in) / median_out`.

Also report the number of in-transit and out-of-transit cadences, the median absolute deviation (MAD) of each set, the per-cadence uncertainty summary, and the depth difference (SAP minus PDCSAP) in ppm and relative percent.

The global out-of-transit median is intentionally simple and auditable. SAP can contain quarter-scale trends; those trends can bias this statistic. Therefore the result must be labelled *windowed median depth*, not a validated physical transit depth. Plot and report the time-domain trend and phase-folded points alongside it. If the SAP result is visibly dominated by a long-term trend or the comparison windows are not credible, record the measurement as unreliable rather than adding an undocumented detrending step.

The catalogue duration defines the measurement window; this experiment does not independently measure duration. It does not infer impact parameter, refit period/epoch, or claim a new planetary solution.

## KNN sensitivity calculation

The existing catalogue depth is the third of eight features. For each KOI independently:

- Keep all seven non-depth feature values at their existing catalogue values.
- Replace only the depth coordinate with the PDCSAP-derived windowed median depth, then repeat with the SAP-derived depth.
- Apply the existing `log10` transform and the exact frozen training mean and scale from `data/generated/catalogue.json`. Do not refit the scaler on the two examples or on the alternative measurements.
- Rank against the same eligible catalogue reference pool, excluding every row with the query's host ID, using the current deterministic distance and tie rules.
- Report the nominal catalogue ranking as context, then the PDCSAP-depth ranking and SAP-depth ranking, including the first five KOI IDs, full eight-dimensional distances and the depth-coordinate contribution to squared distance.

This is deliberately a **one-coordinate substitution experiment**. It tests whether a light-curve-derived depth change can influence the existing 8D ranking while preventing unrelated feature changes from being attributed to the flux-processing choice. It is not a complete refit of all eight features. If either measured depth is non-positive or otherwise outside the feature's valid log domain, mark that ranking unavailable; do not clamp or fabricate a value.

Report both candidate and reference analyses. Do not interpret a ranking swap as evidence that either object is or is not a planet.

## Required diagnostics and acceptance criteria

The experiment is complete only when its output includes:

- Source FITS SHA-256, product filename, quarter, release, host, KOI, ephemeris and flux-column names.
- Software versions and exact processing configuration, including quality mask and phase convention.
- Cadence counts at every selection stage, including paired valid cadences.
- PDCSAP and SAP time-series and phase-folded comparisons with identical axes.
- Per-column in/out medians, MAD, uncertainty summaries and windowed median depth.
- Depth delta in ppm and percent, plus a clear caveat about long-term SAP trends.
- Frozen scaler identity, reference-pool identity, nominal ranking, both substituted rankings and distance contributions.
- A reproducible command and machine-readable output that can be regenerated offline from the pinned FITS files.

Tests must prove that the two variants use the same cadence identities and ephemeris; that changing the flux column updates its recorded provenance and flux-derived outputs while leaving every ranking input outside the depth coordinate unchanged; that missing/invalid depth prevents log scaling; and that rerunning against the same bytes produces identical numerical output.

A ranking change is a finding, not a success criterion. A stable ranking is equally reportable.

## Scope boundaries

Do not change the application's default from PDCSAP. Do not introduce flattening, polynomial detrending, CBV correction, quarter stitching, transit fitting or a new scaler as part of this first comparison. Each would introduce additional assumptions and should be a separately specified experiment. Do not treat the catalogue's period, duration, impact parameter or SNR as newly measured by this statistic.

A later study may compare leave-one-quarter-out results, but the current pinned example contains only Q4 for each host. A valid leave-one-quarter-out experiment requires multiple quarter products for the same KOI and explicit rules for combining or comparing quarters.

## Scientific references

- [Lightkurve: Using Kepler light-curve products](https://lightkurve.github.io/lightkurve/tutorials/1-getting-started/using-light-curve-file-products.html) — describes SAP as aperture-summed flux still subject to mission systematics and PDCSAP as the conditioned product intended to remove systematics while preserving transits.
- [NASA Exoplanet Archive: Kepler data products overview](https://exoplanet.ipac.caltech.edu/docs/Kepler_Data_Products_Overview.html) — describes the relation between SAP inputs, cotrending basis vectors and PDCSAP outputs.
- [Kepler Science Operations: Data pipeline](https://keplergo.github.io/KeplerScienceWebsite/pipeline.html) — documents PDC processing and cautions users to compare calibrated and corrected light curves.
- [Kepler Data Characteristics Handbook](https://archive.stsci.edu/files/live/sites/mast/files/home/missions-and-data/kepler/_documents/Data_Characteristics.pdf) — describes systematic effects and the corrected PDCSAP product.

## Decision after this design

The paired-flux analysis has now been run against the pinned FITS bytes. Its measured results, reliability assessment, ranking comparisons and reproducible outputs are recorded below.


## Executed results · 16 November 2026

The paired analysis was run offline against the two pinned FITS files. The shared cadence selection retained **4,108 of 4,397 cadences** for each target: 4,116 passed the quality mask, 281 were quality-rejected, and 8 additional cadences were excluded because at least one of time/SAP/PDCSAP was non-finite. The same 4,108 cadence numbers and phase values were used for both flux variants.

| KOI | Catalogue depth (ppm) | PDCSAP windowed median (ppm) | SAP windowed median (ppm) | SAP − PDCSAP (ppm) |
| --- | ---: | ---: | ---: | ---: |
| K00115.03 | 23.2 | 17.8638 | 22.3829 | +4.5191 |
| K02961.01 | 33.5 | 46.4210 | 111.6763 | +65.2553 |

The SAP values are **not reliable transit-depth estimates**. Visual review of the shared-axis time-series and phase-folded plot shows large coherent variations that are absent or strongly reduced in PDCSAP. The normalized flux MAD ratio (SAP / PDCSAP) was 6.46x in transit and 6.56x out of transit for K00115.03; for K02961.01 it was 8.01x and 7.43x respectively. The median reported per-cadence uncertainty remained approximately 84 ppm and 74 ppm for the two targets, respectively, in both flux columns. This supports the interpretation that SAP's much larger scatter is not explained by the quoted cadence uncertainties alone. Because the global out-of-transit median is affected by these broad trends, the SAP depth and SAP-derived ranking are retained as diagnostic outputs only.

The PDCSAP windowed medians are also descriptive statistics, not fitted physical transit depths. They differ from the catalogue depths, which are independently catalogued measurements. This experiment does not establish that either estimate is more physically accurate.

### KNN results

The existing catalogue ranking and the ranking after substituting the PDCSAP windowed-median depth were compared using the same frozen training scaler, labelled training pool, host exclusion, and all seven unchanged non-depth features.

- **K00115.03:** the nearest neighbour remained K02961.01. The top-five order changed from K02961.01, K03172.02, K06871.01, K02636.01, K07709.01 to K02961.01, K06871.01, K02636.01, K03172.02, K04288.03.
- **K02961.01:** the nearest neighbour remained K06871.01. The top-five order changed from K06871.01, K04383.01, K06419.01, K07709.01, K02623.01 to K06871.01, K04383.01, K02722.03, K07709.01, K02623.01.

The SAP-only rankings move more substantially, but they are not scientifically interpretable because the SAP depth inputs fail the variability diagnostic above. They must not be presented as an alternative trustworthy ranking.

### Reproducible outputs

The analysis is implemented in reference/flux_sensitivity.py and tested in reference/test_flux_sensitivity.py. Run from the repository root:

    .venv/bin/python reference/flux_sensitivity.py
    .venv/bin/python -m unittest reference.test_flux_sensitivity

Generated outputs:

- data/generated/flux-sensitivity/analysis.json — source FITS checksums and product metadata, selection counts, both complete cadence series, per-window flux MAD and uncertainty summaries, processing configuration, frozen scaler values, and full top-five KNN distances/contributions.
- data/generated/flux-sensitivity/report.md — concise results and interpretation.
- data/generated/flux-sensitivity/sap-pdcsap-comparison.png — shared-axis time-series and phase-folded comparison.

Seven dedicated tests cover paired cadence identity, common phase selection, invalid flux/depth handling, missing uncertainties, host exclusion, distance evidence, and deterministic numerical output. The full reference suite also passes.

### Scientific conclusion and next experiment

This comparison demonstrates that raw SAP is not an appropriate alternative depth input for the current global-median estimator without additional trend treatment. The application should continue to use PDCSAP. Do not add an improvised detrending step to make SAP appear comparable.

The next useful scientific comparison should therefore be separately designed around a validated alternative, such as a controlled PDCSAP detrending/flattening method with explicit window selection and transit-preservation checks, or a multi-quarter consistency analysis after additional quarters for the same KOIs have been imported. The current two-target Q4 dataset cannot support leave-one-quarter-out validation.
