# Kepler light curves: data contract and calculations

## Purpose

Transit Atlas ranks fitted catalogue measurements. A light curve adds the observational time series behind one signal. This document defines how a Kepler archive product is associated with a KOI, how its flux is prepared for phase-folded inspection, and what must be retained to reproduce the result offline.

A KOI identifies a transit-like signal. A KIC identifier identifies its host star. One KIC can have several KOIs, each with its own period, epoch and duration. The light curve belongs to the host; the ephemeris belongs to the individual signal. Never infer one KOI's ephemeris from another signal around the same star.

## Time and ephemeris

The first implementation uses Kepler Barycentric Julian Date (BKJD), defined as

$$
t_{\mathrm{BKJD}} = \mathrm{BJD} - 2454833.0.
$$

The period $P$ is in days and the reference transit epoch $T_0$ is in the same BKJD time system. The catalogue transit duration $D$ is in hours. The time system and zero point are recorded rather than assumed from a plot label.

For a cadence at time $t_i$, calculate its phase as

$$
\phi_i =
\frac{(t_i-T_0+P/2)\bmod P}{P}-\frac12.
$$

This centres the selected transit at phase zero and wraps the data into $[-0.5,0.5)$. The equivalent time offset from the transit centre is

$$
\Delta t_i = P\phi_i,
$$

in days. A cadence exactly half a period after the epoch maps to $-0.5$, not $+0.5$, so the plotted interval has one unambiguous boundary.

The nominal half-width of the transit window in phase units is

$$
\phi_{\mathrm{half}} = \frac{D}{48P}.
$$

This is a display guide derived from the catalogue duration, not a transit fit or a measurement of the observed event width.

## Quality filtering

Kepler light-curve files contain an integer quality flag for each cadence. A processing mask $M$ accepts cadence $i$ when

$$
\mathrm{bitand}(q_i,M)=0,
$$

where $\mathrm{bitand}(q_i,M)$ denotes the bitwise AND of the cadence quality flag and the selected mask. The current reference implementation uses Lightkurve's Kepler default quality bitmask, **1,130,799**, which removes cadences with severe quality issues. The selected mask is stored in the derived document.

The FITS source and the complete time, flux, uncertainty, quality and cadence-number arrays remain unchanged. Filtering applies only when deriving the plotted series. This allows another analyst to choose a different mask and reproduce the result.

## Flux normalisation

The selected flux column is `pdcsap_flux` by default. The importer also permits `sap_flux`, but the chosen column must be recorded. Both are archive pipeline products; neither should be described as untouched detector counts.

For one product, define the accepted finite cadence set

$$
S = \{i \mid \mathrm{bitand}(q_i,M)=0,\;\mathrm{isfinite}(t_i),\;\mathrm{isfinite}(F_i)\}.
$$

The baseline is the median accepted flux

$$
F_0 = \mathrm{median}_{i\in S}(F_i).
$$

The relative flux displayed in parts per million is

$$
f_i = 10^6\left(\frac{F_i}{F_0}-1\right),
$$

and the propagated per-cadence flux uncertainty is

$$
\sigma_{f_i}=10^6\frac{\sigma_{F_i}}{F_0}.
$$

The median is calculated separately for each product (for example, each quarter). This keeps a quarter's baseline from setting the scale of another quarter. The source flux and its units are retained. A non-finite or non-positive median is rejected rather than silently producing a misleading normalisation.

This initial method is median normalisation only. It does not flatten long-timescale variability, remove stellar activity, fit a transit model or stitch quarters. Any future detrending or stitching must be a named processing step with its own parameters and tests.

## Product identity and provenance

A reproducible imported signal records:

- KOI ID, host KIC ID and whether the signal is the selected candidate or a ranked reference.
- Period, epoch and duration, including their units and epoch definition.
- MAST data URI, product filename, author, quarter, cadence and archive product metadata.
- Local path to the original FITS bytes, file size and SHA-256 digest.
- FITS time format, time scale, time unit and flux unit.
- Reader name and version, selected flux column, quality bitmask and normalisation rule.
- Total, quality-rejected, invalid and retained cadence counts.

The KOI-to-KIC association and the KOI ephemeris must be checked against the pinned cumulative catalogue extract. When a host has several KOIs, selecting a light curve for the host does not resolve which signal is being folded: the explicit KOI ID and its ephemeris do.

## Portable document

The first JSON data contract is `transit-atlas.kepler-lightcurve`, version 1. It contains the identity, ephemeris, MAST provenance, processing settings, original cadence arrays and derived folded points. The original FITS file remains alongside it and is referenced by a repository-relative path and SHA-256.

Offline replay must use the local FITS bytes and the saved processing settings. It must not silently download a newer archive product. A changed product or ephemeris is a new analysis input and must produce a new fingerprint.

## Current limitations

- A phase-folded curve is an inspection view, not evidence that a planet is confirmed.
- The catalogue period, epoch and duration are fitted archive measurements; their uncertainties and covariance are not yet propagated into the folded view.
- A single product does not represent the complete multi-quarter Kepler baseline.
- The first normalisation is deliberately simple. It can leave instrumental or astrophysical trends in the display.
- A correct host match is not sufficient by itself: each displayed curve must retain its signal-level KOI mapping and ephemeris.
- The first UI integration must display the selected candidate and reference independently, and expose the product and processing metadata beside each curve.

## References

- [Lightkurve: using Kepler light-curve products](https://lightkurve.github.io/lightkurve/tutorials/1-getting-started/using-light-curve-file-products.html)
- [Lightkurve: reading FITS light curves](https://lightkurve.github.io/lightkurve/reference/api/lightkurve.io.read.html)
- [MAST Kepler data-product documentation](https://archive.stsci.edu/kepler/data_products.html)
- [MAST Kepler archive manual](https://archive.stsci.edu/files/live/sites/mast/files/home/missions-and-data/k2/_documents/MAST_Kepler_Archive_Manual_2020.pdf)

## Pinned Q4 case study

The first offline example uses two Kepler Data Release 25 long-cadence light-curve products. Their original FITS bytes are stored in the repository, not fetched at application runtime.

| Role | KOI | KIC | Period (days) | Epoch (BKJD) | Duration (hours) |
| --- | --- | ---: | ---: | ---: | ---: |
| Candidate | K00115.03 | 9579641 | 3.43591631 | 132.66240 | 3.133 |
| Reference | K02961.01 | 10471515 | 3.78475070 | 133.50785 | 2.924 |

The period, epoch and duration values come from the committed NASA Exoplanet Archive cumulative table snapshot. Their asymmetric uncertainties and disposition provenance are retained in each JSON document. The host identifiers and period/duration values are checked against the pinned Transit Atlas catalogue before import.

The source products are:

- kplr009579641-2010078095331_llc.fits — s3://stpubdata/kepler/public/lightcurves/0095/009579641/kplr009579641-2010078095331_llc.fits
- kplr010471515-2010078095331_llc.fits — s3://stpubdata/kepler/public/lightcurves/0104/010471515/kplr010471515-2010078095331_llc.fits

Both FITS headers identify quarter 4, DATA_REL=25, TIMESYS=TDB, and the Kepler BKJD zero point BJDREFI=2454833. Each file contains 4,159 source cadences. With the recorded quality bitmask and finite-value checks, 4,108 are retained, 43 are rejected by quality flags and 8 are rejected as invalid measurements.

Rebuild the two derived documents from the repository root:

~~~bash
python reference/import_kepler_lightcurve.py --koi-id K00115.03 --role candidate --quarter 4 --overwrite
python reference/import_kepler_lightcurve.py --koi-id K02961.01 --role reference --quarter 4 --overwrite
~~~

The importer uses the committed ephemeris snapshot and the public MAST AWS mirror. For a manually downloaded product, pass --fits /path/to/product_llc.fits; the source URI and product filename can also be supplied explicitly.
