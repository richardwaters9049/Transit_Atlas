# Held-out Kepler evaluation

Transit Atlas compares neighbour votes with the archive dispositions in the pinned 14 November 2026 snapshot. The experiment uses the 7,587 rows labelled **Confirmed** or **False positive**. Unresolved candidates are available in the app for comparison and have no target label in this experiment.

Kepler host IDs determine the three disjoint partitions. Scaling and the exact distance search use only the 5,783 usable training references. Three.js projects the data for display. The evaluation measures label agreement using the same eight-dimensional geometry as the desktop app.

## Select k on validation stars

The 768 usable validation signals come from 667 hosts. Balanced agreement is the mean of the two class recalls. The baseline predicts **False positive**, the majority disposition in the training set, for every signal. Higher balanced agreement wins, with smaller k breaking ties. [Balanced accuracy definition](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.balanced_accuracy_score.html)

| Method | Agreement | Balanced agreement |
| --- | ---: | ---: |
| Training majority baseline | 60.5% | 50.0% |
| k = 3 | 90.6% | 90.5% |
| **k = 5** | **91.4%** | **91.8%** |
| k = 7 | 91.3% | 91.4% |

## Measure agreement on test stars

Of 796 labelled test signals, 776 had all eight usable measurements and came from 668 hosts. The selected vote matched 704 of 776 catalogue labels (90.7%, with 91.3% balanced agreement). The baseline matched 463 of 776 (59.7%, with 50.0% balanced agreement).

| Archive label | Vote Confirmed | Vote False positive | Recall |
| --- | ---: | ---: | ---: |
| Confirmed | 295 | 18 | 94.2% |
| False positive | 54 | 409 | 88.3% |

| Transit signal-to-noise | Complete test rows | Confirmed / false positive | k = 5 agreement | k = 5 balanced | Baseline agreement |
| --- | ---: | ---: | ---: | ---: | ---: |
| Below 10 | 79 | 5 / 74 | 83.5% | 63.2% | 93.7% |
| 10 to below 20 | 206 | 92 / 114 | 89.3% | 89.7% | 55.3% |
| 20 and above | 491 | 216 / 275 | 92.5% | 92.8% | 56.0% |

The low-signal bin has only five confirmed signals. The neighbour vote found two of them and also voted confirmed for ten false positives. The majority baseline had higher raw agreement in that bin because 74 of 79 signals already belonged to its predicted class.

## Coverage and failure cases

| Disposition | Snapshot rows | Usable rows | Complete-case coverage |
| --- | ---: | ---: | ---: |
| Confirmed | 2,748 | 2,746 | 99.9% |
| False positive | 4,839 | 4,581 | 94.7% |
| Candidate | 1,977 | 1,872 | 94.7% |

All 20 excluded labelled test rows were false positives (20 of 483). Test coverage was 97.5% for labelled rows overall and 93.8% for unresolved candidates (181 of 193). The confidence of conclusions for rows with missing or invalid measurements remains unknown.

On the usable test set the app’s rules would flag 244 rows for mixed dispositions and 28 for a fifth-neighbour distance above 1.430. These counts overlap. The 505 unflagged rows had 97.4% agreement. Thirteen unflagged votes still disagreed, including these close unanimous votes:

| KOI | Archive label | Five-neighbour vote | Fifth distance |
| --- | --- | --- | ---: |
| K04053.01 | Confirmed | 5 false positive | 0.410 |
| K02621.01 | False positive | 5 confirmed | 0.306 |

Planet confirmation depends on independent evidence. The flags describe the retrieved neighbours and their agreement with one another.

## Correlated measurements

The strongest absolute training Pearson correlation is between stellar surface gravity and log₁₀ stellar radius (r = −0.981). A fixed sensitivity check omitted radius, the second feature in the pair, and kept the original test partition and k = 5. The five-neighbour set changed for 480 of 776 rows and the vote changed for 14. Overall agreement was 90.7% in both configurations. Balanced agreement moved from 91.3% to 91.2%. The app keeps its eight-feature ranking.

## Reproduce

Run this from the project root after installing `reference/requirements.txt`.

```bash
python reference/evaluate.py
python -m unittest discover -s reference -v
```

The [machine-readable result](../data/evaluation/held-out.json) has the confusion counts, complete-case denominators by partition and the real neighbour IDs and exact distances for four disagreements. The [desktop demo](videos/Transit_Atlas_Demo.mp4) records the candidate search, distance breakdown, teaching example and second KOI on macOS.
