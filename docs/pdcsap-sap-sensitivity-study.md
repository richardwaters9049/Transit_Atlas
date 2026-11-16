# PDCSAP versus SAP: processing-sensitivity experiment

## Status and purpose

**Status: experiment design; no alternative processing results have been claimed.**

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

Proceed to an offline paired-flux analysis using the pinned FITS bytes. Keep the estimator and ranking substitution exactly as specified above unless a concrete data-quality failure is found; if it is, document the failure and revise the protocol before inspecting comparative ranking outcomes.
