# The mathematics of Transit Atlas

Transit Atlas compares fitted Kepler catalogue measurements. This guide follows a signal from its original catalogue values through the eight-dimensional ranking, the 3D projection and the sensitivity checks.

- [Data and host partitions](#data-and-host-partitions)
- [Transforms and standardisation](#transforms-and-standardisation)
- [Exact neighbours and distance contributions](#exact-neighbours-and-distance-contributions)
- [Principal component analysis](#principal-component-analysis)
- [Measurement sensitivity](#measurement-sensitivity)
- [Release comparison](#release-comparison)
- [Held-out evaluation](#held-out-evaluation)
- [Reproduce the results](#reproduce-the-results)

## Data and host partitions

A Kepler Object of Interest (KOI) identifies a transit-like signal. A Kepler host ID identifies the star associated with it. One star can have several signals, so a split by KOI could put observations sharing stellar properties in both training and test. The Python reference groups rows by Kepler host ID. It hashes the decimal host ID with SHA-256, interprets the first eight digest bytes as an unsigned big-endian integer and takes the remainder modulo 10. Buckets 0–7 train the model, bucket 8 selects settings, and bucket 9 tests the selected setting. [NASA KOI tables](https://exoplanetarchive.ipac.caltech.edu/docs/Kepler_KOI_docs.html) · [Python reference](../reference/transit_atlas.py)

The cumulative snapshot contains 9,564 rows, of which 9,199 have all eight usable measurements. Among the complete cases, 5,783 labelled rows form the training reference pool, 768 labelled rows are reserved for validation and 776 for test. The other 1,872 rows are unresolved candidates, which are the queries in the desktop app. The order, selection query, date and SHA-256 are pinned in the [snapshot manifest](../data/raw/kepler-koi-cumulative-2026-11-14.json). [Data coverage and feature order](methods.md#catalogue-and-distance)

During a lookup, the app excludes all references from the query’s star. For a candidate on a training host, the scaler and PCA may still reflect the other signals from that host because they were fitted before the query. In the held-out evaluation, separation by host prevents this overlap even during fitting.

## Transforms and standardisation

Let $x_j$ be measurement $j$ in its original catalogue unit, and $g_j$ the transform for that coordinate. Transit Atlas uses $g_j(x)=\log_{10}(x)$ for period, duration, depth, signal-to-noise and stellar radius, and $g_j(x)=x$ for impact parameter, effective temperature and surface gravity. The surface gravity column already contains a logarithm. For a logged coordinate, a fixed ratio always creates the same difference. For example, doubling the orbital period adds $\log_{10}(2)$ whether the period goes from 2 to 4 days or 20 to 40. Logarithms require positive values. The importer excludes rows with a missing, invalid or non-finite measurement or a non-positive log input. [Archive column definitions](https://exoplanetarchive.ipac.caltech.edu/docs/API_kepcandidate_columns.html)

For the $n$ training references, fit a mean and population standard deviation independently for each transformed coordinate.

$$
\mu_j=\frac1n\sum_{i=1}^n g_j(x_{ij}),\qquad
s_j=\sqrt{\frac1n\sum_{i=1}^n[g_j(x_{ij})-\mu_j]^2},\qquad
z_j(x)=\frac{g_j(x_j)-\mu_j}{s_j}.
$$

The scaler uses a scale of 1 for a constant column. A difference of one training standard deviation contributes the same squared distance in any coordinate. Dependencies between coordinates remain. For example, training surface gravity and log stellar radius have Pearson $r=-0.981$. Giving both coordinates a term in the distance can give a shared physical trend more influence. The existing evaluation tests the effect of dropping radius. [StandardScaler conventions](https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.StandardScaler.html) · [Correlation sensitivity](evaluation.md#correlated-measurements)

The exporter freezes the means, scales, PCA centre and components in `data/generated/catalogue.json`. Python fits these once. Rust reads the parameters and applies the same transforms to catalogue rows, scenarios and matched release measurements. [Python exporter](../reference/export_desktop.py) · [Rust implementation](../crates/atlas-core/src/lib.rs)

## Exact neighbours and distance contributions

For query $q$ and reference $r$, the app computes a squared difference per coordinate and adds the eight values.

$$
c_j(q,r)=[z_j(q)-z_j(r)]^2,\qquad
d_8^2(q,r)=\sum_{j=1}^{8}c_j(q,r),\qquad
d_8(q,r)=\sqrt{d_8^2(q,r)}.
$$

The mean cancels out in each pairwise difference. The corresponding term in transformed units is $[g_j(q_j)-g_j(r_j)]^2/s_j^2$. An equal raw difference can therefore contribute differently by feature or, in a logged coordinate, by the ratio between the two original values.

The exact search evaluates every eligible reference against the same query. It orders by $d_8^2$ and then by KOI ID for equal scores. The desktop selects and sorts the five smallest scores. Taking the square root for display preserves their order. For $d_8^2>0$, the inspector reports $c_j/d_8^2$ as a percentage. These shares explain the chosen metric. For identical vectors the shares are undefined, shown as a dash in the app and as `null` in the Python report.

### Worked Kepler example

The query `K00115.03` has 5,781 eligible references after excluding two signals from its own host. Its first-ranked reference is `K02961.01`. Their effective temperatures are 5,779 K and 6,017 K. The fitted scale for that coordinate is 807.247592 K. Thus the temperature contribution is $(238/807.247592)^2=0.086924139$. Their periods are 3.43591631 and 3.7847507 days. That contribution is $[\log_{10}(3.7847507/3.43591631)/0.791405476]^2=0.002815729$.

| Coordinate | Squared difference |
| --- | ---: |
| Orbital period | 0.002815729 |
| Transit duration | 0.008297009 |
| Transit depth | 0.021718466 |
| Impact parameter | 0.042902088 |
| Signal-to-noise | 0.040330516 |
| Effective temperature | 0.086924139 |
| Surface gravity | 0.000989440 |
| Stellar radius | 0.031190014 |
| **Sum before rounding** | **0.235167401** |

The distance is 0.484940616. Temperature accounts for $0.086924139/0.235167401\approx36.96\%$ of its squared distance. This describes why these two records rank where they do under this metric. Scientific vetting uses the underlying observations and other diagnostic evidence. [Full-precision fixture](../data/fixtures/K00115.03.json) · [Kepler Data Validation products](https://exoplanetarchive.ipac.caltech.edu/docs/KeplerDV.html)

## Principal component analysis

The exporter takes the standardised training matrix $Z$ and subtracts its column mean $m$, giving $X$. A full singular value decomposition gives $X=U\Sigma V^\mathsf{T}$. The rows of $P\in\mathbb{R}^{3\times8}$ are the first three right singular vectors, transposed. These directions are orthonormal. The display coordinate for a standardised signal $z$ is $y=P(z-m)$. This is ordinary, unwhitened PCA. The associated training variance along component $i$ is $\sigma_i^2/(n-1)$. The three components account for 27.60%, 23.95% and 18.40% of training variance, respectively, or 69.955% in total. [PCA conventions](https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.PCA.html) · [Frozen PCA export](../reference/export_desktop.py)

For a difference vector $v=z(q)-z(r)$, its visible component is $P^\mathsf{T}Pv$ and the remainder is orthogonal to it. The Pythagorean theorem gives the fraction of the pair’s squared distance outside the view.

$$
d_3^2=\|Pv\|^2,\qquad
d_8^2=d_3^2+\|(I-P^\mathsf{T}P)v\|^2,\qquad
\text{omitted share}=1-\frac{d_3^2}{d_8^2}.
$$

This share is specific to a pair of signals. The roughly 70% retained variance describes the entire training set. The packaged display coordinates are rounded to seven decimal places. The audit uses those values for projected distances, clamps rounding excursions in the omitted share to $[0,1]$, and leaves the share undefined when $d_8=0$. The eight-dimensional ranking always uses the unrounded standardised coordinates. [Rust projection audit](../crates/atlas-core/src/projection_audit.rs)

For `K00115.03`, `K08264.01` is closest in the display at $d_3=0.162258465$. Its full distance is $d_8=2.014583158$, putting it 1,836th in eight dimensions. About 99.35% of this pair’s squared distance lies outside the three displayed components. The audit repeats the comparison with the same eligible pool for every candidate. [Catalogue-wide overlap results](methods.md#projection-audit)

## Measurement sensitivity

The uncertainty exporter joins the error extract on KOI ID, host ID and exact agreement of all eight central values. For a valid pair of signed errors, it starts with $L_j=x_j+e_{j,-}$ and $H_j=x_j+e_{j,+}$. It clips the lower bound at zero for log-transformed columns, impact parameter and effective temperature. It keeps a coordinate fixed if its bounds are unavailable or invalid. Signal-to-noise is always fixed. [Range exporter](../reference/export_uncertainties.py) · [Error extract and provenance](../data/raw/kepler-koi-errors-2026-11-15.json)

The desktop uses 64 deterministic points from an unscrambled Halton sequence. For each coordinate $j$, take the digits $a_0,a_1,\ldots$ of the scenario number $t$ in prime base $b_j$, starting with the least significant digit. Reverse them across the radix point to obtain $u_j(t)$.

$$
u_j(t)=\sum_{m\geq0}\frac{a_m}{b_j^{m+1}},\qquad
x^{(t)}_j=L_j+(H_j-L_j)u_j(t).
$$

For $t=1,\dots,64$, the prime bases in feature order are 2, 3, 5, 7, 11, 13, 17 and 19. These points are interior to the interval on each varying coordinate. For example, the effective temperature interval for `K00115.03` is 5,664 to 5,883 K. That coordinate uses base 13, so scenario 1 sets it to $5664+219/13=5680.846$ K. The app samples raw values before transforming and standardising them. [Halton construction](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.qmc.Halton.html) · [Rust stability analysis](../crates/atlas-core/src/stability.rs)

The model, reference measurements and exclusion rule stay fixed. **Same nearest** counts scenarios whose first reference matches the nominal first reference. **Same top five** compares membership, so reordering the same five counts as retained. For `K00115.03`, those counts are 16/64 and 0/64, respectively. This is a sensitivity check over the specified box. The joint distribution and covariance of the fitted parameters are unknown here. Treat recurrence as a count under this design. Other points in the box can produce different rankings.

## Release comparison

The historical extract has usable DR24 measurements for 1,202 of the 1,872 candidates in the cumulative snapshot, matched on KOI and host. For each match, the app transforms both sets of measurements with the same cumulative scaler. The signed vector $\delta=z_{\mathrm{cum}}-z_{\mathrm{DR24}}$ gives the change in each coordinate. The full and projected shifts are $\|\delta\|$ and $\|P\delta\|$. Each snapshot’s five neighbours are computed against the same training pool. Releases can change reported fits and stellar parameters, so this is a comparison of catalogue measurements. [NASA release definitions](https://exoplanetarchive.ipac.caltech.edu/docs/PurposeOfKOITable.html) · [Rust release comparison](../crates/atlas-core/src/release.rs)

For `K00005.01`, the full shift is approximately 0.2324 standardised units. The nearest reference changes from `K00356.01` to `K01090.01`, and two of the five references are shared between releases. [Pinned DR24 extract](../data/raw/kepler-koi-dr24-2026-11-15.json)

## Held-out evaluation

For evaluation only, the KNN classifier takes the majority archive label among the first $k$ references. Choose among $k\in\{3,5,7\}$ by balanced agreement on validation hosts, with smaller $k$ breaking ties. Balanced agreement averages the two class recalls. Each class recall is the number correctly matched in that class divided by the number of evaluated records actually in that class. The majority baseline always predicts the most frequent training label.

The chosen $k=5$ matched 704 of 776 usable test labels. The recalls were $295/313$ for confirmed objects and $409/463$ for false positives. This gives $704/776=90.7\%$ agreement and $(295/313+409/463)/2=91.3\%$ balanced agreement. The overall majority baseline matched $463/776=59.7\%$. Below a signal-to-noise ratio of 10, it matched 93.7% versus 83.5% for KNN. These figures measure agreement with recorded archive labels in the complete-case subset.

For exploration, the desktop flags mixed neighbour dispositions and fifth-neighbour distances strictly above the 95th percentile of validation fifth-neighbour distances, approximately 1.4301 for this snapshot. This threshold describes distance under the fitted metric. Both flags can be absent even when every neighbour disagrees with the archive result. [Evaluation protocol and failure cases](evaluation.md) · [Machine-readable results](../data/evaluation/held-out.json)

## Reproduce the results

Run these commands from the repository root with the [Python dependencies and Rust installed](../README.md#verify-the-calculations).

```bash
python reference/transit_atlas.py --query K00115.03
python reference/transit_atlas.py --synthetic
atlas_report=$(mktemp)
python reference/evaluate.py --output "$atlas_report"
cargo test -p atlas-core --locked
cargo run --locked -p atlas-core --example stability -- K00115.03 K00005.01
```

The Rust suite checks the five ordered neighbours and all 40 feature contributions against the Python fixture, the projection-audit counts against an independent NumPy calculation, and the real scenarios and release shifts. The tolerance for the fixture’s distances and contributions is $10^{-12}$. A saved `.atlas.json` study records the relevant data fingerprints and the selected view’s comparison evidence. Reopening the file reruns the calculation and checks the stored result. [Rust checks](../crates/atlas-core/src/lib.rs) · [Study replay](../desktop/src/study-file.ts)
