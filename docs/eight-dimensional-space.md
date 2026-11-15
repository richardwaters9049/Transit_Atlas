# The eight-dimensional feature space

Every Kepler signal in Transit Atlas is represented by eight catalogue measurements. Together, these measurements define a point in an eight-dimensional (8D) feature space. This document explains what those dimensions are, how a catalogue row becomes a vector, why the values are transformed and standardised, and how the space is used by the application.

- [What an eight-dimensional space means](#what-an-eight-dimensional-space-means)
- [The eight axes](#the-eight-axes)
- [From catalogue row to 8D point](#from-catalogue-row-to-8d-point)
- [Why transform and standardise](#why-transform-and-standardise)
- [How the application uses the space](#how-the-application-uses-the-space)
- [What the space does not represent](#what-the-space-does-not-represent)
- [Reproducibility and source files](#reproducibility-and-source-files)

## What an eight-dimensional space means

In everyday geometry, a point in two dimensions is described by two coordinates, such as \((x,y)\). A point in three dimensions has three coordinates, such as \((x,y,z)\). The same idea extends to eight dimensions: a point is an ordered list of eight numbers.

For Transit Atlas, each coordinate is one measured or fitted property from the NASA Exoplanet Archive's Kepler Objects of Interest (KOI) catalogue. A signal is represented as

$$
\mathbf{x}=\bigl(x_1,x_2,x_3,x_4,x_5,x_6,x_7,x_8\bigr)\in\mathbb{R}^{8}.
$$

The space is called *eight-dimensional* because eight values are needed to locate a signal in this representation. It is not eight dimensions of physical space, and it is not a map of where a planet is in the universe. It is a mathematical space whose axes describe catalogue properties.

Two signals are close in this space when their transformed and standardised values are similar across the selected measurements. The exact distance calculation is described in [Linear algebra behind Transit Atlas](linear-algebra.md).

## The eight axes

The order below is fixed in the Python reference, generated catalogue and Rust application. The archive field names are retained so that the calculation can be traced back to its source data.

| Index | Archive field | Measurement | Catalogue unit | Transform |
| ---: | --- | --- | --- | --- |
| 1 | `koi_period` | Orbital period | days | \(\log_{10}\) |
| 2 | `koi_duration` | Transit duration | hours | \(\log_{10}\) |
| 3 | `koi_depth` | Transit depth | ppm | \(\log_{10}\) |
| 4 | `koi_impact` | Transit impact parameter | stellar radii (ratio) | Identity |
| 5 | `koi_model_snr` | Transit signal-to-noise | ratio | \(\log_{10}\) |
| 6 | `koi_steff` | Stellar effective temperature | K | Identity |
| 7 | `koi_slogg` | Stellar surface gravity | \(\log_{10}(\mathrm{cm}/\mathrm{s}^{2})\) | Identity |
| 8 | `koi_srad` | Stellar radius | solar radii | \(\log_{10}\) |

The first five fields describe fitted properties of the transit signal and its detection strength. The final three describe properties of the host star. The surface-gravity field is already expressed logarithmically in the catalogue, so Transit Atlas leaves it unchanged rather than taking another logarithm.

These are catalogue estimates, not eight independent direct observations. The feature set is a modelling choice that makes the current comparison reproducible; it is not claimed to capture every physical factor relevant to whether a signal is a planet.

## From catalogue row to 8D point

A raw catalogue row starts as eight values in their original units. Before calculating distances, Transit Atlas performs three operations:

1. **Check validity.** All eight fields must be present, numeric and finite. Values supplied to a logarithmic transform must be strictly positive. A row that fails any of these checks is excluded from the complete-case model.
2. **Transform selected axes.** The five fields marked `log10` in the table are transformed with the base-10 logarithm. The other three are unchanged.
3. **Standardise every axis.** Subtract the training mean and divide by the training population standard deviation for that field.

For feature \(j\), the final coordinate is

$$
z_j=\frac{g_j(x_j)-\mu_j}{s_j},
$$

where \(x_j\) is the original catalogue value, \(g_j\) is its transform, and \(\mu_j\) and \(s_j\) are the mean and population standard deviation fitted on the training references. A zero-variance training feature uses a scale of 1.

The eight standardised values form the point \(\mathbf{z}\in\mathbb{R}^{8}\). These are the coordinates used by the exact neighbour search. The application retains the original measurements and units so that users can inspect the scientific values rather than seeing only standardised numbers.

## Why transform and standardise

### Logarithms for strongly varying positive quantities

Period, duration, depth, signal-to-noise and stellar radius can span broad positive ranges. A logarithmic transform makes ratios more directly comparable: doubling a value adds the same amount, \(\log_{10}(2)\), whether the original value is small or large.

Logarithms cannot be applied to zero or negative values. Such rows are not silently repaired; they are excluded from the complete-case feature set and counted in the data audit.

### Standardisation for comparable scales

After the logarithms, the eight columns still have different spreads and units. Standardisation expresses each transformed value relative to the training distribution. A difference of one training standard deviation contributes one squared unit to the Euclidean distance, regardless of whether that feature is temperature or orbital period.

The scaler is fitted only on the 5,783 labelled training references. The same frozen means and scales are used for every query and reference, including uncertainty scenarios and release comparisons. This prevents each query or catalogue release from silently changing the coordinate system.

Standardisation does not remove correlation. In this training set, surface gravity and log stellar radius have a Pearson correlation of approximately \(-0.981\). Both therefore remain separate terms in the current distance, and a shared physical trend can influence the metric more than once. The held-out evaluation includes a feature-removal sensitivity analysis; see [Correlated measurements](evaluation.md#correlated-measurements).

## How the application uses the space

### Exact neighbour ranking

For a candidate \(q\) and a labelled reference \(r\), the application calculates

$$
d_8^2(q,r)=\sum_{j=1}^{8}[z_j(q)-z_j(r)]^2.
$$

It compares the candidate with every eligible labelled training reference, excludes signals from the same host star, and returns the five smallest distances. Equal squared distances are ordered by KOI ID. The inspector shows the distance and the contribution from each of the eight axes. See [K-nearest neighbours in Transit Atlas](knn.md).

### The three-dimensional scene

A screen can show three spatial axes, not eight. Transit Atlas uses PCA to project the standardised eight-dimensional points into three dimensions. This makes the catalogue explorable as a 3D scene, but it necessarily discards information.

The three displayed components retain 69.955% of the variance in the training set. That is a statement about the distribution of the training points, not a guarantee that an individual pair's distance or neighbour rank is preserved. In the projection audit, 601 of 1,872 candidates have no overlap at all between their 3D and 8D top-five neighbour sets. The exact ranking therefore always comes from the full eight-dimensional vectors, never from visual proximity alone.

### Sensitivity and comparisons

The uncertainty explorer changes the candidate's raw measurements within the available quoted ranges, then transforms and standardises each scenario using the same frozen scaler before recalculating its eight-dimensional neighbours. Release comparison applies that same scaler and reference pool to matched catalogue measurements from different releases. This keeps the geometry fixed while the candidate values change.

## What the space does not represent

The eight-dimensional representation is useful, but it has limits:

- **It is not physical 3D space.** The axes are catalogue features, not positions or directions in the sky.
- **Its distance is not a probability.** A small distance means similar values under the current metric, not a probability of planetary confirmation.
- **Its features are not independent.** Standardisation adjusts each column's scale but does not decorrelate the columns or account for a full covariance matrix.
- **It is not a complete astrophysical model.** Other observations, stellar properties, instrumental effects and validation diagnostics can matter.
- **The 3D projection is lossy.** The screen is an exploratory view; it cannot replace the full eight-dimensional ranking.
- **Measurement uncertainty is not fully probabilistic.** The current explorer samples the declared coordinate ranges, but the joint distribution and covariance of the fitted parameters are not known.

These limitations are why Transit Atlas exposes distance contributions, uncertainty scenarios, exact rank-sensitivity checks, catalogue release comparisons and a catalogue-wide projection audit.

## Reproducibility and source files

| File | What it defines or contains |
| --- | --- |
| [`reference/transit_atlas.py`](../reference/transit_atlas.py) | Canonical feature names, order, units, transforms, validity checks and Python distance calculation |
| [`reference/export_desktop.py`](../reference/export_desktop.py) | Training scaler, PCA fit and generated desktop catalogue |
| [`data/raw/kepler-koi-cumulative-2026-11-14.json`](../data/raw/kepler-koi-cumulative-2026-11-14.json) | Source snapshot manifest with retrieval metadata and checksum |
| [`data/generated/catalogue.json`](../data/generated/catalogue.json) | Frozen means, scales, PCA parameters, variance ratios and display coordinates |
| [`crates/atlas-core/src/lib.rs`](../crates/atlas-core/src/lib.rs) | Rust application feature transform and full 8D distance calculation |
| [`crates/atlas-core/src/projection_audit.rs`](../crates/atlas-core/src/projection_audit.rs) | Comparison between 3D projected distances and 8D distances |
| [`docs/mathematics.md`](mathematics.md) | Full derivations and worked calculations |
| [`docs/methods.md`](methods.md) | Catalogue coverage, evaluation protocol and projection-audit results |

To reproduce the reference lookup from the repository root:

```bash
python reference/transit_atlas.py --query K00115.03
python reference/export_desktop.py
cargo test -p atlas-core --locked
```

The generated catalogue is committed so the desktop application can run offline. Regenerating it should produce the same frozen feature statistics and PCA output from the pinned snapshot and the declared Python dependencies.

Further reading: [Linear algebra behind Transit Atlas](linear-algebra.md) · [K-nearest neighbours](knn.md) · [Mathematics](mathematics.md) · [Data and methods](methods.md).
