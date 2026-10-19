# Native shadows on AMD: four profiles against BorutaPy, 2026-10-19

Protocol `native-shadow-max40-v1` (`scripts/native_shadow_pilot.py`). Candidate:
the public **bankai-boruta 0.1.0a8** and **bankai-random-forest 0.1.0a17**,
installed over the locked comparator stack: Boruta 0.4.3, scikit-learn 1.9.1,
LightGBM, NumPy 2.4.6 and Python 3.11.17.

## Setup

- **Host:** one EC2 c7a.4xlarge per run (16 physical AMD cores, SMT off, 32 GiB) running on ECS, 16 threads.
- **Methods:**
  - Bankai exact Extra Trees;
  - Bankai binned Extra Trees (63 bins);
  - BorutaPy + scikit-learn `ExtraTreesClassifier` (BP/E);
  - BorutaPy + the suite's LightGBM random forest (BP/L: 63 bins, subsample 0.8, per-tree columns at sqrt of the augmented width).
- **Shared settings:** each profile's trees, depth and feature fraction (Bioinformática uses 150 trees, depth 8 and fraction 0.15), plus bootstrap, `perc=100`, `alpha=0.05`, `two_step=True`, and at most 40 rounds with the natural stop.
- **Data:** float32, seeds 42–46.
- **Measurement:**
  - every fit runs in a fresh process that first generates the data;
  - the reported memory is the fit's peak RSS above that loaded baseline, sampled externally every 5 ms;
  - downstream ROC AUC comes from `scripts/native_shadow_auc.py`, the suite's 200-tree balanced ExtraTrees trained on the confirmed features and run outside every timing window;
  - `summary.json` comes from `scripts/native_shadow_summary.py`.

| Run | Profiles / methods | Repeats | Image | State |
|---|---|---:|---|---|
| `20261019T063357Z` | Industrial, three methods | 3 (rotated order) | `sha256:6dc15f28…293f` | `../native-shadow-max40-amd-20261019.json` |
| `20261019T072031Z` | Crédito, Cibersegurança, Bioinformática; four methods | 1 | `sha256:a8909f1f…823e` | `../native-shadow-profiles-amd-20261019.json` |
| `20261019T084559Z` | Industrial, BP/L | 3 | `sha256:a8909f1f…823e` | `../native-shadow-industrial-lgbm-amd-20261019.json` |

- **Same data across runs:** the Industrial BP/L artifacts (`*-lgbm.json`) have the same data SHA256 as the first run.
- **Integrity:** every artifact was checked against its S3 SHA256 metadata.
- **Cost:** host time was about 21 + 66 + 20 minutes. Each run armed its shutdown before any capacity and reserved its hours in the supplemental USD 150 ledger (USD 3 + 6 + 1.50). Every fleet returned to zero and its idle stack was deleted.

## Results (medians over five seeds of per-seed medians)

| Profile (train n × p, relevant) | Method | Time (s) | RSS (MiB) | Precision | Recall | AUC |
|---|---|---:|---:|---:|---:|---:|
| Industrial 200k × 500 (12) | Bankai exact | 22.5 | 1,283 | 1.00 | 0.67 | 0.837 |
| | Bankai binned | 15.6 | 667 | 1.00 | 0.67 | 0.837 |
| | BP/E | 37.5 | 1,817 | 1.00 | 0.67 | 0.837 |
| | BP/L | 75.1 | 4,865 | 1.00 | 0.67 | 0.837 |
| Crédito 300k × 300 (20) | Bankai exact | 20.8 | 1,474 | 1.00 | 0.85 | 0.852 |
| | Bankai binned | 16.1 | 819 | 1.00 | 0.85 | 0.852 |
| | BP/E | 45.7 | 1,806 | 1.00 | 0.85 | 0.852 |
| | BP/L | 52.3 | 3,428 | 1.00 | 0.85 | 0.852 |
| Cibersegurança 400k × 150 (60) | Bankai exact | 54.8 | 1,395 | 1.00 | 0.67 | 0.837 |
| | Bankai binned | 42.7 | 908 | 1.00 | 0.62 | 0.838 |
| | BP/E | 107.5 | 1,472 | 1.00 | 0.65 | 0.836 |
| | BP/L | 77.5 | 2,073 | 1.00 | 0.55 | 0.837 |
| Bioinformática 50k × 2000 (30) | Bankai exact | 135.6 | 982 | 1.00 | 1.00 | 0.750 |
| | Bankai binned | 64.0 | 450 | 1.00 | 1.00 | 0.750 |
| | BP/E | 145.1 | 1,608 | 1.00 | 1.00 | 0.750 |
| | BP/L | 129.1 | 5,823 | 1.00 | 0.80 | 0.734 |

Reference AUC (median) with all features / with the known relevant features:

| Profile | All features | Known relevant |
|---|---:|---:|
| Industrial | 0.825 | 0.838 |
| Crédito | 0.825 | 0.853 |
| Cibersegurança | 0.815 | 0.833 |
| Bioinformática | 0.693 | 0.750 |

## Per-seed comparison (all 20 profile × seed pairs)

| Bankai backend | vs | Faster | Less memory | Time ratio | Memory ratio |
|---|---|---:|---:|---|---|
| exact | BP/E | 20/20 | 20/20 | 0.27–0.96 | 0.61–0.97 |
| binned | BP/E | 20/20 | 20/20 | 0.18–0.63 | 0.28–0.63 |
| exact | BP/L | 15/20 | 20/20 | 0.18–1.26 | 0.17–0.74 |
| binned | BP/L | 20/20 | 20/20 | 0.12–0.59 | 0.08–0.48 |

- **Where Bankai lost:** Bankai exact was slower than BP/L only in Bioinformática, by 1.01–1.26×.
  - In that profile, BP/L used about 6× more memory.
  - It also missed 1, 6, 10 and 12 of the 30 relevant features in four of the five seeds.
- **Selection:**
  - **No method confirmed an irrelevant feature.**
  - In Industrial and Crédito, all four methods confirmed identical sets in every seed. The unconfirmed relevant features are the generator's weak-effect group.
  - In Bioinformática, both Bankai backends and BP/E recovered all 30 relevant features, including the 20 interaction sources.
  - In Cibersegurança, every method reached the 40-round cap and the sets differed in a few borderline relevant features. Median recall was 0.67 for Bankai exact, 0.65 for BP/E, 0.62 for Bankai binned and 0.55 for BP/L. The confirmed sets nevertheless had a higher AUC than the 60 known relevant features.
- **Rounds:** round counts vary across seeds and methods with no systematic advantage. The shared decision rule and MDI importance make them depend on forest noise, not on the implementation.
