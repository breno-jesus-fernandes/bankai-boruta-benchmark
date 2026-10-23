# Native shadows on AMD with bankai-boruta 0.1.0a12: four profiles, 2026-10-23

Protocol `native-shadow-max40-v1` (`scripts/native_shadow_pilot.py`), the same
as `../native-shadow-amd-20261019/`. Candidate: the public
**bankai-boruta 0.1.0a12** and **bankai-random-forest 0.1.0a20** (PyPI
manylinux_2_28 wheels), unpacked over the locked comparator stack of image
`sha256:b9209d5a…0d74` by `scripts/run_candidate_probe_aws.py`: Boruta 0.4.3,
scikit-learn 1.9.1, LightGBM, NumPy 2.4.6 and Python 3.11.17.

## Setup

- **Host:** one EC2 c7a.4xlarge (16 physical AMD cores, SMT off, 32 GiB) on ECS, 16 threads.
- **Methods and shared settings:** as in the 0.1.0a8 run (Bankai exact, Bankai binned with 63 bins, BP/E, BP/L; bootstrap, `perc=100`, `alpha=0.05`, `two_step=True`, at most 40 rounds).
- **Data:** float32, seeds 42–46. Every artifact has the same data SHA256 as the 0.1.0a8 run.
- **Repeats:** 5 per seed, methods interleaved within each repeat.
- **AUC:** every method confirmed the same feature set as in the 0.1.0a8 run, seed by seed, so `summary.json` reuses `../native-shadow-amd-20261019/auc.json` (deterministic given the seed and the set).

| Run | Repeats | State | Host time |
|---|---:|---|---|
| `20261023T160300Z` (this directory) | 5 | `../native-shadow-synthetic-a12-r5-amd-20261023.json` | about 6 h 55 min |
| `20261023T142330Z` (`../native-shadow-synthetic-a12-amd-20261023/`) | 1 | `../native-shadow-synthetic-a12-amd-20261023.json` | about 1 h 20 min |

Both runs armed the shutdown before any capacity, reserved their hours in the
supplemental USD 150 ledger (USD 13.50 and 6), drained the fleet and deleted the stack.

## Results (medians over five seeds of per-seed medians)

| Profile (train n × p, relevant) | Method | Time (s) | RSS (MiB) | Rounds | Precision | Recall | AUC | 0.1.0a8 time (s) | 0.1.0a8 RSS (MiB) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Industrial 200k × 500 (12) | Bankai exact | 9.2 | 931 | 34 | 1.00 | 0.67 | 0.837 | 22.5 | 1,283 |
| | Bankai binned | 10.8 | 456 | 40 | 1.00 | 0.67 | 0.837 | 15.6 | 667 |
| | BP/E | 37.1 | 1,816 | 19 | 1.00 | 0.67 | 0.837 | 37.5 | 1,817 |
| | BP/L | 75.1 | 4,865 | 22 | 1.00 | 0.67 | 0.837 | 75.1 | 4,865 |
| Crédito 300k × 300 (20) | Bankai exact | 9.5 | 929 | 19 | 1.00 | 0.85 | 0.852 | 20.8 | 1,474 |
| | Bankai binned | 10.9 | 506 | 19 | 1.00 | 0.85 | 0.852 | 16.1 | 819 |
| | BP/E | 46.2 | 1,805 | 16 | 1.00 | 0.85 | 0.852 | 45.7 | 1,806 |
| | BP/L | 52.7 | 3,429 | 16 | 1.00 | 0.85 | 0.852 | 52.3 | 3,428 |
| Cibersegurança 400k × 150 (60) | Bankai exact | 24.5 | 760 | 40 | 1.00 | 0.67 | 0.837 | 54.8 | 1,395 |
| | Bankai binned | 23.5 | 476 | 40 | 1.00 | 0.62 | 0.838 | 42.7 | 908 |
| | BP/E | 110.4 | 1,455 | 40 | 1.00 | 0.65 | 0.836 | 107.5 | 1,472 |
| | BP/L | 79.9 | 1,877 | 40 | 1.00 | 0.55 | 0.837 | 77.5 | 2,073 |
| Bioinformática 50k × 2000 (30) | Bankai exact | 85.7 | 853 | 40 | 1.00 | 1.00 | 0.750 | 135.6 | 982 |
| | Bankai binned | 71.1 | 388 | 16 | 1.00 | 1.00 | 0.750 | 64.0 | 450 |
| | BP/E | 145.1 | 1,608 | 29 | 1.00 | 1.00 | 0.750 | 145.1 | 1,608 |
| | BP/L | 130.0 | 5,823 | 40 | 1.00 | 0.80 | 0.734 | 129.1 | 5,823 |

The 0.1.0a8 columns come from `../native-shadow-amd-20261019/summary.json`
(three repeats for Industrial, one for the other profiles).

## Per-seed comparison (all 20 profile × seed pairs)

| Bankai backend | vs | Faster | Less memory | Time ratio | Memory ratio |
|---|---|---:|---:|---|---|
| exact | BP/E | 20/20 | 20/20 | 0.13–0.59 | 0.51–0.53 |
| binned | BP/E | 20/20 | 20/20 | 0.13–0.50 | 0.24–0.33 |
| exact | BP/L | 20/20 | 20/20 | 0.09–0.79 | 0.14–0.41 |
| binned | BP/L | 20/20 | 20/20 | 0.09–0.66 | 0.07–0.26 |

- **Against 0.1.0a8:** Bankai exact is 1.6–2.5× faster and uses 13–46% less memory. Bankai exact now beats BP/L in Bioinformática too (0.64–0.79 of its time), where 0.1.0a8 was 1.01–1.26× slower.
- **Same decisions:** every method confirmed and left tentative exactly the same features as in the 0.1.0a8 run, in every profile and seed, and in every repeat.
- **Selection:**
  - No method confirmed an irrelevant feature.
  - Industrial, Crédito and Bioinformática: Bankai exact, Bankai binned and BP/E confirmed identical sets in every seed. BP/L missed up to 12 of the 30 relevant features in Bioinformática.
  - Cibersegurança: every method reached the 40-round cap, and Bankai exact and BP/E differed in one to four borderline relevant features per seed, as in 0.1.0a8.
- **Binned in Bioinformática:** it costs 2× more per round than exact (4.38 against 2.16 s) but stops after 12–20 rounds, so it finishes first.
- **Noise:** the largest per-seed coefficient of variation over the five repeats was 4.2% for Bankai exact, 4.0% for BP/E, 2.7% for BP/L and 11.5% for Bankai binned (one Bioinformática seed).
