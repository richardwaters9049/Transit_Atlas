# Data and methods

For derivations, a worked Kepler calculation and reproduction commands, see [The mathematics of Transit Atlas](mathematics.md).

## Catalogue and distance

The bundled CSV is the NASA Exoplanet Archive’s cumulative Kepler Objects of Interest table as retrieved on 14 November 2026. Its [manifest](../data/raw/kepler-koi-cumulative-2026-11-14.json) records the exact TAP query, row count, data DOI and SHA-256 checksum. All 9,564 rows were retrieved. Of those, 9,199 have usable values for all eight features.

| Archive disposition | Usable | Excluded |
| --- | ---: | ---: |
| Candidate | 1,872 | 105 |
| Confirmed | 2,746 | 2 |
| False positive | 4,581 | 258 |

The [audit command](../README.md#verify-the-calculations) reports exclusion counts by field and disposition. A single row can contribute to several field counts. Blanks, invalid or non-finite numbers, and non-positive values in log-transformed fields cause row exclusion. Catalogue values stay in their original units for inspection.

| Archive field | Measurement | Transform |
| --- | --- | --- |
| `koi_period` | Orbital period, days | log₁₀ |
| `koi_duration` | Transit duration, hours | log₁₀ |
| `koi_depth` | Transit depth, ppm | log₁₀ |
| `koi_impact` | Transit impact parameter, relative to the stellar radius | Identity |
| `koi_model_snr` | Transit signal-to-noise ratio | log₁₀ |
| `koi_steff` | Stellar effective temperature, K | Identity |
| `koi_slogg` | Stellar surface gravity, log₁₀(cm/s²) | Identity |
| `koi_srad` | Stellar radius, solar radii | log₁₀ |

For repeatable evaluation, each labelled host has a stable partition. Take the first eight bytes of SHA-256 of the decimal `kepid`, read them as a big-endian integer, and take the remainder modulo 10. Buckets 0–7 are training, 8 is validation and 9 is test. This gives 5,783 training, 768 validation and 776 test references after filtering. The scaler fits population means and standard deviations on the training references only and uses a scale of 1 for constant features. The report records those parameters for the desktop implementation.

The search ranks by the sum of the eight squared differences between scaled coordinates and breaks ties by KOI ID. The displayed distance is the square root of that sum. Each feature’s share is its squared difference divided by the total. A zero-distance match has undefined shares, shown as JSON `null`. Labelled signals from the query’s host are excluded from ranking. A candidate can share a host with scaler training rows during exploratory lookup. The [held-out evaluation](evaluation.md) uses disjoint host partitions.

## Verified example

`K00115.03` has catalogue disposition `CANDIDATE`. The search excluded `K00115.01` and `K00115.02` because both share its host, `kepid` 9579641.

| Rank | KOI | Archive disposition | Distance |
| ---: | --- | --- | ---: |
| 1 | K02961.01 | Confirmed | 0.484941 |
| 2 | K03172.02 | False positive | 0.510942 |
| 3 | K06871.01 | False positive | 0.515677 |
| 4 | K02636.01 | Confirmed | 0.519177 |
| 5 | K07709.01 | False positive | 0.548691 |

The closest examples span both dispositions. Effective temperature accounts for about 37% of the first neighbour’s squared distance, and orbital period accounts for about 48% of the second’s. The ranking describes similarity in the selected measurements. Planet confirmation requires independent evidence.

The synthetic fixture ranks **C, A, B** in eight dimensions and **B, C, A** using coordinates 1–3. Its fourth coordinate accounts for 4 of B’s 4.04 squared distance. The Kepler scene uses a PCA projection and highlights neighbours from the full eight-dimensional search.

## Measurement uncertainty

The stability analysis joins a separate [NASA error extract](../data/raw/kepler-koi-errors-2026-11-15.json) to the pinned measurements by exact KOI, host and central values. A deterministic Halton sequence explores the joint box defined by the signed catalogue offsets. Signal-to-noise and measurements with missing or invalid bounds stay fixed. Ranks use the original scaler and reference set. Recurrence describes those scenarios, with unknown measurement correlations and fixed references. Planet confirmation requires independent evidence. Regenerate the ranges with `python reference/export_uncertainties.py`. [Archive column definitions](https://exoplanetarchive.ipac.caltech.edu/docs/API_kepcandidate_columns.html)

## Projection audit

For each of the 1,872 usable candidates, rank references twice using the same training pool and same-star exclusion. The 8D ranking uses the standardised measurements. The projected ranking uses Euclidean distance across the three frozen PCA coordinates. Both rankings break ties by KOI ID.

The inspector reports the full 8D rank for each of the five closest references in the projection. Because the retained components are orthonormal, the share of squared distance outside the projection is `1 − d₃²/d₈²`. A zero 8D distance has an undefined share. The strongest mismatch is the candidate whose first projected neighbour has the lowest 8D placement among candidates with zero common top-five neighbours. Ties are broken by candidate KOI ID. [PCA reference](https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.PCA.html)

| Shared top-five references | Candidates |
| ---: | ---: |
| 0 | 601 |
| 1 | 667 |
| 2 | 406 |
| 3 | 150 |
| 4 | 42 |
| 5 | 6 |

The first-ranked reference changes for 1,642 candidates. These counts measure the effect of projecting this snapshot and reference pool.

## Catalogue release comparison

The [DR24 extract](../data/raw/kepler-koi-dr24-2026-11-15.json) covers 1,202 of the 1,872 usable candidates, matched by KOI and Kepler host ID with eight usable measurements. The comparison applies the same scaler, PCA and reference pool to both releases. The line in 3D connects the two projected catalogue positions. The inspector reports each measurement in its original units, signed changes after scaling, and the eight-dimensional shift. [Archive release notes](https://exoplanetarchive.ipac.caltech.edu/docs/PurposeOfKOITable.html)
