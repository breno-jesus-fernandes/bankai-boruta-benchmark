# Dependency licenses

`LICENSE` covers new benchmark code. Third-party components keep their own
licenses and notices; the lockfile records the resolved distributions.

| Component | License |
|---|---|
| bankai-boruta and the native-control patch | GPL-3.0-or-later; upstream/COPYING |
| bankai-random-forest | GPL-3.0-or-later |
| BorutaPy | BSD-3-Clause |
| NumPy, SciPy, scikit-learn, pandas, joblib | BSD family |
| LightGBM | MIT |
| psutil | BSD-3-Clause |
| boto3, botocore | Apache-2.0 |
| pytest | MIT |

The committed development source archive and wheel contain upstream code under
GPL, not code relicensed by the benchmark's MIT file. Their bundled notices are
preserved. Transitive and system libraries carry their distribution notices;
consult installed `.dist-info` metadata for exact version-specific terms.
