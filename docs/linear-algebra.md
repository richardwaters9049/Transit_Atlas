# Linear algebra behind Transit Atlas

Transit Atlas uses linear algebra to turn a set of eight differently measured catalogue fields into a comparable geometric representation, rank similar signals, and project the data into a three-dimensional scene. This guide introduces the mathematics and explains where each operation appears in the code.

- [Why linear algebra is needed](#why-linear-algebra-is-needed)
- [A signal as a vector](#a-signal-as-a-vector)
- [Transforming and standardising coordinates](#transforming-and-standardising-coordinates)
- [Distance, norms and feature contributions](#distance-norms-and-feature-contributions)
- [The catalogue as a matrix](#the-catalogue-as-a-matrix)
- [PCA and the three-dimensional display](#pca-and-the-three-dimensional-display)
- [What the projection loses](#what-the-projection-loses)
- [Implementation map](#implementation-map)

## Why linear algebra is needed

A catalogue row contains several measurements: orbital period in days, transit depth in parts per million, stellar temperature in kelvin, and so on. These quantities have different units and very different numerical ranges. Comparing their raw values directly would let large-numbered units dominate the result. Linear algebra gives us a consistent way to represent each signal as a point, transform the coordinates, calculate distances and project the data for visual exploration.

The important distinction is that the resulting geometry is a **feature space**, not ordinary physical space. Its axes represent catalogue measurements, not directions in the sky. A distance of 1.0 in this space is a dimensionless distance under the model's chosen scaling; it is not a physical length.

## A signal as a vector

A vector is an ordered collection of numbers. Transit Atlas represents one Kepler signal as an eight-element column vector:

$$
\mathbf{x}=\begin{bmatrix}
x_1\\x_2\\x_3\\x_4\\x_5\\x_6\\x_7\\x_8
\end{bmatrix}\in\mathbb{R}^{8}.
$$

Each position has a fixed meaning and order: period, duration, depth, impact parameter, signal-to-noise, effective temperature, surface gravity and stellar radius. The order is part of the data contract. Changing it in one part of the application without changing the others would compare the wrong measurements.

A vector is useful because operations can be applied coordinate by coordinate. For example, two signals \(\mathbf{x}\) and \(\mathbf{r}\) can be subtracted to produce a difference vector. Each entry then tells us how far apart the two records are on one measurement axis.

## Transforming and standardising coordinates

First, Transit Atlas applies a transform \(g_j\) to each raw measurement. Five coordinates use base-10 logarithms: orbital period, transit duration, transit depth, signal-to-noise and stellar radius. Impact parameter, effective temperature and the already-logarithmic surface-gravity field use the identity transform.

Write the transformed vector as \(\mathbf{g}(\mathbf{x})\). For each feature, the training reference set supplies a mean \(\mu_j\) and population standard deviation \(s_j\). The standardised coordinate is

$$
z_j=\frac{g_j(x_j)-\mu_j}{s_j}.
$$

In matrix form, let \(\boldsymbol{\mu}\) contain the eight means and let \(D\) be the diagonal matrix of scales:

$$
D=\begin{bmatrix}
s_1&0&\cdots&0\\
0&s_2&\cdots&0\\
\vdots&\vdots&\ddots&\vdots\\
0&0&\cdots&s_8
\end{bmatrix},\qquad
\mathbf{z}=D^{-1}\bigl(\mathbf{g}(\mathbf{x})-\boldsymbol{\mu}\bigr).
$$

A standardised coordinate measures how many training standard deviations the transformed value lies above or below its training mean. A one-standard-deviation difference therefore has the same squared contribution on any one axis. A constant training feature uses a scale of 1 to avoid division by zero.

The means and scales are fitted using only the 5,783 labelled training references. They are exported once to `data/generated/catalogue.json` and then reused by Rust. Queries, uncertainty scenarios and historical release measurements use these same frozen parameters; the scaler is not refitted for each query.

The mean cancels when two standardised vectors are subtracted. Consequently, the pairwise coordinate difference can also be written as

$$
z_j(q)-z_j(r)=\frac{g_j(q_j)-g_j(r_j)}{s_j}.
$$

This makes clear why both the feature transform and its fitted scale affect the geometry.

## Distance, norms and feature contributions

The Euclidean norm of a vector is its length. For an eight-dimensional difference vector \(\Delta=\mathbf{z}(q)-\mathbf{z}(r)\), the norm is

$$
\|\Delta\|_2=\sqrt{\Delta_1^2+\Delta_2^2+\cdots+\Delta_8^2}.
$$

Transit Atlas uses this Euclidean distance to rank a query against each eligible reference:

$$
d_8(q,r)=\|\mathbf{z}(q)-\mathbf{z}(r)\|_2,
\qquad
d_8^2(q,r)=\sum_{j=1}^{8}[z_j(q)-z_j(r)]^2.
$$

The square root is monotonic, so sorting by squared distance produces exactly the same order as sorting by distance. The implementation ranks using squared distance and takes the square root for display.

Each squared coordinate difference is retained as a contribution:

$$
c_j=[z_j(q)-z_j(r)]^2,\qquad
p_j=\frac{c_j}{d_8^2}.
$$

For a non-zero distance, the eight shares \(p_j\) sum to 1 (apart from display rounding). They show how this particular pair's squared distance is distributed across the eight measurements. They are not feature importance scores for the model as a whole. If the two vectors are identical, the total distance is zero and the shares are undefined.

### Worked example: K00115.03

For candidate `K00115.03`, the nearest eligible reference is `K02961.01`. Their squared coordinate contributions are:

| Feature | Squared contribution |
| --- | ---: |
| Orbital period | 0.002815729 |
| Transit duration | 0.008297009 |
| Transit depth | 0.021718466 |
| Impact parameter | 0.042902088 |
| Signal-to-noise | 0.040330516 |
| Effective temperature | 0.086924139 |
| Surface gravity | 0.000989440 |
| Stellar radius | 0.031190014 |
| **Total** | **0.235167401** |

The distance is \(\sqrt{0.235167401}=0.484940616\). Effective temperature contributes about 36.96% of this pair's squared distance. This is a decomposition of one distance calculation, not a claim that temperature is universally the most important feature.

## The catalogue as a matrix

A matrix is a rectangular arrangement of numbers. Stack the standardised training vectors row by row to form

$$
Z\in\mathbb{R}^{n\times8},
$$

where each row is one training signal and each column is one standardised feature. In the current snapshot, \(n=5{,}783\). This matrix is the input to principal component analysis (PCA).

Thinking in matrices makes the separation of roles clearer:

- rows represent catalogue signals;
- columns represent the eight measurements;
- the scaler acts on columns;
- PCA finds directions of variation across the rows;
- the exact neighbour metric still uses all eight standardised columns.

## PCA and the three-dimensional display

Eight dimensions cannot be shown directly on a conventional three-dimensional screen. Transit Atlas therefore uses principal component analysis (PCA) to find three orthogonal directions that capture as much training-set variance as possible.

PCA first centres the standardised training matrix by subtracting its column mean \(\mathbf{m}\):

$$
X=Z-\mathbf{1}\mathbf{m}^{\mathsf{T}}.
$$

A full singular value decomposition (SVD) factors this matrix into

$$
X=U\Sigma V^{\mathsf{T}}.
$$

The columns of \(V\) are orthonormal directions in the original eight-dimensional feature space. Transit Atlas takes the first three directions and arranges their transposes as the rows of a projection matrix \(P\in\mathbb{R}^{3\times8}\). A standardised signal is displayed at

$$
\mathbf{y}=P(\mathbf{z}-\mathbf{m})\in\mathbb{R}^{3}.
$$

This is ordinary, unwhitened PCA: the components are not divided by their singular values. The three components explain 27.60%, 23.95% and 18.40% of training variance, respectively, for a total of 69.955%.

PCA is a display transform. It does not replace the original eight measurements, and the exact neighbour lookup does not use the three projected coordinates. The scene uses the projection to make patterns and relationships easier to explore; the ranking inspector uses the full-dimensional calculation.

## What the projection loses

Let \(\mathbf{v}=\mathbf{z}(q)-\mathbf{z}(r)\) be the difference between two standardised signals. The projected distance is \(d_3=\|P\mathbf{v}\|_2\). Because the three rows of \(P\) are orthonormal, the projected part and the omitted part are perpendicular. The Pythagorean theorem gives

$$
d_8^2=d_3^2+\|(I-P^{\mathsf{T}}P)\mathbf{v}\|_2^2.
$$

For a non-zero full distance, the share of squared distance omitted from the display is

$$
\text{omitted share}=1-\frac{d_3^2}{d_8^2}.
$$

The 69.955% figure describes the fraction of total training-set variance represented by the three PCA axes. It does **not** mean that 69.955% of every pairwise distance is preserved. A particular pair can have most of its separation in the five discarded directions.

The catalogue-wide audit demonstrates this directly. For `K00115.03`, `K08264.01` is closest in the 3D display at \(d_3=0.162258465\), but its full eight-dimensional distance is \(d_8=2.014583158\), placing it 1,836th in the full ranking. About 99.35% of that pair's squared distance lies outside the displayed components. Across all 1,872 candidates, the 3D and 8D top-five lists have no references in common for 601 candidates. The first-ranked reference changes for 1,642 candidates.

This is why Transit Atlas never treats visual closeness in the 3D scene as the exact KNN result. Use [Projection audit](methods.md#projection-audit) to inspect the difference for every candidate.

## Implementation map

| File | Linear-algebra responsibility |
| --- | --- |
| [`reference/transit_atlas.py`](../reference/transit_atlas.py) | Feature order, log transforms, training scaler and vector distance reference |
| [`reference/export_desktop.py`](../reference/export_desktop.py) | Fits the scaler and PCA, computes display coordinates and exports the frozen model |
| [`crates/atlas-core/src/lib.rs`](../crates/atlas-core/src/lib.rs) | Applies the eight transforms/scales, calculates squared deltas and exact Euclidean distances |
| [`crates/atlas-core/src/projection_audit.rs`](../crates/atlas-core/src/projection_audit.rs) | Compares projected and full-dimensional distances and calculates omitted shares |
| [`data/generated/catalogue.json`](../data/generated/catalogue.json) | Frozen feature statistics, PCA centre/components, variance ratios and projected observations |
| [`docs/mathematics.md`](mathematics.md) | Extended derivations for PCA, sensitivity, release comparison and evaluation |

Further reading: [The eight-dimensional feature space](eight-dimensional-space.md) · [K-nearest neighbours](knn.md) · [Data and methods](methods.md).
