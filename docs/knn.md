# K-nearest neighbours in Transit Atlas

This guide explains the K-nearest neighbours (KNN) method, why Transit Atlas uses it, and exactly what the application does with it. It separates the application's neighbour search from the supervised classification experiment used to evaluate the method.

- [KNN in plain language](#knn-in-plain-language)
- [What a neighbour means here](#what-a-neighbour-means-here)
- [The lookup process](#the-lookup-process)
- [Why five neighbours](#why-five-neighbours)
- [The classification evaluation](#the-classification-evaluation)
- [What the result does and does not mean](#what-the-result-does-and-does-not-mean)
- [Implementation and reproduction](#implementation-and-reproduction)

## KNN in plain language

K-nearest neighbours is a method for comparing a new record with a collection of records whose measurements are already known. It has two common uses:

1. **Neighbour retrieval:** find the `k` reference records most similar to a query.
2. **Classification:** assign a label to a query by taking a majority vote among those `k` neighbours.

The two uses are related, but they are not the same. Transit Atlas always performs neighbour retrieval in the desktop application. It displays the five closest labelled Kepler signals and their archive dispositions so that a person can inspect the evidence. It does **not** automatically declare the unresolved candidate confirmed or false positive.

The separate held-out evaluation uses the same neighbour geometry as a classifier: it predicts a label by majority vote. That experiment measures how well the local neighbourhood agrees with known archive labels. The distinction matters because a nearby confirmed signal is evidence of similarity under the selected measurements, not proof that the query is a planet.

KNN is often called a *lazy* or instance-based method. Rather than learning a complex decision boundary during fitting, it retains reference examples and compares a query with them when needed. Transit Atlas does fit and freeze preprocessing parameters first; those parameters make the comparisons consistent.

## What a neighbour means here

A Kepler signal is represented by eight catalogue measurements. Before comparing signals, Transit Atlas applies a feature-specific transform and standardises every feature using statistics fitted on the training references. The resulting eight numbers form a point in an eight-dimensional feature space.

For a query vector \(q\) and reference vector \(r\), the squared Euclidean distance is

$$
d^2(q,r)=\sum_{j=1}^{8}(q_j-r_j)^2.
$$

The displayed Euclidean distance is \(d(q,r)=\sqrt{d^2(q,r)}\). A smaller value means the two records are closer under this particular transformed and standardised metric. It is not a distance in kilometres, nor is it a probability.

Each coordinate contributes a non-negative amount:

$$
c_j(q,r)=(q_j-r_j)^2,\qquad d^2(q,r)=\sum_{j=1}^{8}c_j(q,r).
$$

The inspector reports these eight contributions and their share of the total squared distance. This makes the ranking inspectable: a user can see whether a pair is close because of its stellar temperature, orbital period, transit depth, or another measurement. See [The eight-dimensional feature space](eight-dimensional-space.md) and [Linear algebra behind the metric](linear-algebra.md) for the full construction.

## The lookup process

The current catalogue snapshot was retrieved from the NASA Exoplanet Archive on 14 November 2026. The pinned manifest records its query, row count, DOI and checksum. The complete-case reference contains 9,199 signals with all eight usable measurements. The labelled records are partitioned by **host star**, not by individual KOI:

| Partition | Labelled references | Purpose |
| --- | ---: | --- |
| Training | 5,783 | Fit feature scaling and provide neighbour references |
| Validation | 768 | Select the value of `k` and the review-distance threshold |
| Test | 776 | Final held-out evaluation |

The partition is deterministic. Transit Atlas hashes the decimal Kepler host ID with SHA-256, interprets the first eight digest bytes as a big-endian integer and takes the remainder modulo 10. Buckets 0–7 are training, bucket 8 is validation and bucket 9 is test. Keeping every signal from one host in the same partition reduces the risk that signals around the same star appear in both training and evaluation.

For a candidate lookup, the application performs these steps:

1. **Read the eight catalogue values.** The original values and units are retained for display and audit.
2. **Validate and transform.** Missing, invalid, non-finite and non-positive log inputs are excluded. Period, duration, depth, signal-to-noise and stellar radius are transformed with \(\log_{10}\); the other three features use the identity transform.
3. **Standardise.** Apply the training means and population standard deviations frozen in `data/generated/catalogue.json`.
4. **Build the eligible reference set.** Include labelled training signals and exclude every signal associated with the query's host star. This prevents a candidate from being compared with another signal around the same star.
5. **Calculate all eligible distances.** Sum the eight squared coordinate differences for each reference.
6. **Order deterministically.** Sort by squared distance, then by KOI ID in ascending order to break exact ties.
7. **Return the first five.** The square root is used for the displayed distance. The inspector also shows the eight squared-distance contributions.

The Rust desktop implementation uses a partial selection operation to identify the five smallest distances, then sorts those five using the same ordering rule. This avoids fully sorting the entire reference pool while preserving the exact top-five result.

One nuance: for an exploratory candidate lookup, the scaler was fitted once using the full training partition before the query's host is removed from the reference list. If the candidate's host has other training signals, those signals can therefore have influenced the fitted means and scales, even though they cannot appear as neighbours. The held-out evaluation avoids this overlap because its host partitions are disjoint.

## Why five neighbours

The desktop displays five neighbours. Five is not an arbitrary claim that five records are scientifically sufficient. It is the value selected by a documented validation experiment.

The evaluation compared \(k\in\{3,5,7\}\). For each value, it predicted the archive disposition by majority vote among the first `k` references and measured **balanced agreement** on the validation hosts. Balanced agreement is the mean of the recall for confirmed objects and the recall for false positives. The value with the highest validation balanced agreement was selected; a smaller `k` breaks a tie. The selected value was `k = 5`.

The application then uses five consistently for its neighbour inspector, projection audit and related comparisons. The evaluation's majority vote is a separate diagnostic use of those same five neighbours.

## The classification evaluation

The held-out test set contains 776 usable labelled signals from hosts excluded from training and validation. With `k = 5`, the majority-vote classifier agreed with 704 labels:

- Overall agreement: \(704/776=90.7\%\).
- Confirmed-object recall: \(295/313\).
- False-positive recall: \(409/463\).
- Balanced agreement: approximately 91.3%.
- Training-majority baseline agreement: \(463/776=59.7\%\).

These are agreement figures against the archive dispositions in this particular complete-case snapshot. They are not a measured probability that an unresolved candidate is a planet, and they do not establish that the archive labels are error-free. The evaluation also records cases where KNN disagrees with the archive, performance by signal-to-noise band, and a sensitivity test that removes one of the strongly correlated features.

See [Held-out Kepler evaluation](evaluation.md) for the full protocol, confusion counts, coverage and failure cases. The machine-readable result is [held-out.json](../data/evaluation/held-out.json).

## What the result does and does not mean

**It does mean:** the returned records are the closest labelled references under the frozen eight-feature transform, scaling and Euclidean metric. Their measurements and archive dispositions can be inspected, compared and reproduced.

**It does not mean:**

- the query has been confirmed as an exoplanet;
- the distance is a probability, confidence score or calibrated likelihood;
- archive disposition is independent physical ground truth;
- the eight measurements are statistically independent;
- the five neighbours are the only scientifically relevant evidence.

KNN is sensitive to its feature set, scaling, correlations, missing-data policy and distance metric. Transit Atlas makes those choices explicit and provides uncertainty, projection and release comparisons so that the user can examine how the result changes. The quoted measurement ranges are not a full joint probability model; their correlations are not known in the current uncertainty explorer.

## Implementation and reproduction

The main implementation and supporting evidence are here:

| File | Responsibility |
| --- | --- |
| [`reference/transit_atlas.py`](../reference/transit_atlas.py) | Feature definitions, snapshot validation, host partitioning, Python reference scaling and exact distance calculation |
| [`reference/evaluate.py`](../reference/evaluate.py) | Validation selection of `k`, held-out classifier evaluation, baselines and failure analysis |
| [`reference/export_desktop.py`](../reference/export_desktop.py) | Fits the scaler and PCA, then freezes the parameters and catalogue for the desktop app |
| [`crates/atlas-core/src/lib.rs`](../crates/atlas-core/src/lib.rs) | Rust scaling, host exclusion, exact top-five search, tie-breaking and contribution values |
| [`data/fixtures/K00115.03.json`](../data/fixtures/K00115.03.json) | Full-precision Python reference result for a real candidate lookup |
| [`docs/evaluation.md`](evaluation.md) | Evaluation design and results |

Run the following from the repository root after installing the [Python requirements](../reference/requirements.txt) and Rust toolchain:

```bash
python reference/transit_atlas.py --query K00115.03
python reference/evaluate.py --output /tmp/transit-atlas-held-out.json
python -m unittest discover -s reference -v
cargo test -p atlas-core --locked
```

The Rust test compares the real candidate's five neighbours and all 40 feature contributions with the Python fixture to a tolerance of \(10^{-12}\). The Python evaluation independently calculates the validation and test results from the pinned catalogue snapshot.

Further reading: [Data and methods](methods.md) · [Mathematics](mathematics.md) · [Research roadmap](research-roadmap.md).
