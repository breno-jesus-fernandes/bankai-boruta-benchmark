# Native shadows with 2× data on 32 cores, bankai-boruta 0.1.0a12, 2026-10-31

Protocol `native-shadow-max40-v1` (`scripts/native_shadow_pilot.py`) with
`--scale 2`: the four synthetic profiles with twice the rows and twice the
columns (`profile(name, "full2x")`), the same relevant features (12/20/30/60), so
only the noise grows. Methods, settings and package versions are those of
`../native-shadow-synthetic-a12-r5-amd-20261023/` (the 1× run on 16 cores):
image `sha256:b4a44fc7…24cd6e` pins **bankai-boruta 0.1.0a12** and
**bankai-random-forest 0.1.0a20** over Boruta 0.4.3, scikit-learn 1.9.1,
LightGBM, NumPy 2.4.6 and Python 3.11.17. Artifacts carry the `-x2` suffix and
record `scale`, `profile_mode`, `n_rows` and `n_features`.

## Setup

- **Host:** one EC2 c7a.8xlarge (32 physical AMD cores, SMT off, 64 GiB) on ECS, 32 threads.
- **Data:** float32, seeds 42–46, generated once per seed in the parent process and loaded whole (no mmap) by each fit's worker before its RSS baseline. Every artifact passed the data hash check across methods.
- **Repeats:** 5 per seed, methods interleaved within each repeat: 400 fits.
- **AUC:** `scripts/native_shadow_auc.py` on each artifact's 2× profile. Industrial, Crédito and Bioinformática ran locally; Cibersegurança (800k training rows) did not fit a laptop's memory and ran on a c7a.8xlarge with `scripts/run_native_shadow_auc_aws.py`. The AUC is deterministic given the seed, the set and the platform; the thread count does not change it, but arm64 and x86 differ by up to 0.0016 (see `../native-shadow-scaling64-a12-amd64-20261031/README.md`).

| Launch | Seeds | Run | State | Reserved (USD) |
|---|---|---|---|---:|
| Calibration (1 repeat, all profiles) | 42 | `20261030T192313Z` | `../native-shadow-x2-calibration-amd32-20261030.json` | 6 |
| Industrial | 42–46 | `20261030T200922Z` | `../native-shadow-x2-industrial-amd32-20261030.json` | 12 |
| Crédito | 42–46 | `20261030T224849Z` | `../native-shadow-x2-credito-amd32-20261030.json` | 12 |
| Bioinformática A | 42–43 | `20261031T011511Z` | `../native-shadow-x2-bio-a-amd32-20261030.json` | 12 |
| Bioinformática B | 44–46 | `20261031T041423Z` | `../native-shadow-x2-bio-b-amd32-20261030.json` | 18 |
| Cibersegurança | 42–46 | `20261031T111424Z` | `../native-shadow-x2-ciber-amd32-20261030.json` | 15 |
| AUC (Cibersegurança) | 42–46 | `auc/…` | `../native-shadow-x2-auc-amd32-20261031.json` | 6 |

Every launch armed the shutdown before any capacity, reserved its hours in the
supplemental USD 150 ledger (USD 3 per hour for the c7a.8xlarge), drained the
fleet and deleted the stack. The calibration artifacts are in
`../native-shadow-x2-calibration-amd32-20261030/`. In Bioinformática B the local
AWS session expired while polling: the task uploaded all three artifacts by
08:34Z (CloudWatch logs), the armed shutdown terminated the idle host at 10:13Z,
and the state was finalized by hand.

## Results (medians over five seeds of per-seed medians)

| Profile (train n × p, relevant) | Method | Time (s) | RSS (MiB) | Rounds | Precision | Recall | AUC | 1× time (s) | 1× RSS (MiB) | 1× recall |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Industrial 400k × 1000 (12) | Bankai exact | 15.5 | 3,490 | 32 | 1.00 | 0.67 | 0.840 | 9.2 | 931 | 0.67 |
| | Bankai binned | 19.8 | 1,592 | 32 | 1.00 | 0.67 | 0.840 | 10.8 | 456 | 0.67 |
| | BorutaPy + ExtraTrees | 123.9 | 6,945 | 40 | 1.00 | 0.67 | 0.840 | 37.1 | 1,816 | 0.67 |
| | BorutaPy + LightGBM | 186.7 | 13,208 | 22 | 1.00 | 0.67 | 0.840 | 75.1 | 4,865 | 0.67 |
| Crédito 600k × 600 (20) | Bankai exact | 17.3 | 3,406 | 16 | 1.00 | 0.85 | 0.854 | 9.5 | 929 | 0.85 |
| | Bankai binned | 23.3 | 1,698 | 16 | 1.00 | 0.85 | 0.854 | 10.9 | 506 | 0.85 |
| | BorutaPy + ExtraTrees | 125.0 | 6,758 | 16 | 1.00 | 0.85 | 0.854 | 46.2 | 1,805 | 0.85 |
| | BorutaPy + LightGBM | 154.5 | 9,951 | 19 | 1.00 | 0.85 | 0.854 | 52.7 | 3,429 | 0.85 |
| Cibersegurança 800k × 300 (60) | Bankai exact | 37.4 | 2,744 | 40 | 1.00 | 0.70 | 0.838 | 24.5 | 760 | 0.67 |
| | Bankai binned | 38.6 | 1,590 | 40 | 1.00 | 0.77 | 0.838 | 23.5 | 476 | 0.62 |
| | BorutaPy + ExtraTrees | 202.3 | 5,413 | 40 | 1.00 | 0.70 | 0.839 | 110.4 | 1,455 | 0.65 |
| | BorutaPy + LightGBM | 164.3 | 5,934 | 40 | 1.00 | 0.67 | 0.839 | 79.9 | 1,877 | 0.55 |
| Bioinformática 100k × 4000 (30) | Bankai exact | 173.5 | 3,193 | 29 | 1.00 | 1.00 | 0.755 | 85.7 | 853 | 1.00 |
| | Bankai binned | 162.2 | 1,303 | 12 | 1.00 | 1.00 | 0.755 | 71.1 | 388 | 1.00 |
| | BorutaPy + ExtraTrees | 337.2 | 6,378 | 29 | 1.00 | 1.00 | 0.755 | 145.1 | 1,608 | 1.00 |
| | BorutaPy + LightGBM | 338.7 | 22,290 | 22 | 1.00 | 1.00 | 0.755 | 130.0 | 5,823 | 0.80 |

Rounds are the median over seeds of each seed's first repeat. The 1× columns come from
`../native-shadow-synthetic-a12-r5-amd-20261023/summary.json` (c7a.4xlarge, 16 threads).
AUC with all features / with only the relevant features: Industrial 0.815 / 0.841,
Crédito 0.810 / 0.855, Cibersegurança 0.801 / 0.835, Bioinformática 0.684 / 0.755.

## Per-seed comparison (all 20 profile × seed pairs)

| Bankai backend | vs | Faster | Less memory | Time ratio | Memory ratio |
|---|---|---:|---:|---|---|
| exact | BorutaPy + ExtraTrees | 20/20 | 20/20 | 0.10–0.53 | 0.50–0.51 |
| binned | BorutaPy + ExtraTrees | 20/20 | 20/20 | 0.11–0.51 | 0.20–0.30 |
| exact | BorutaPy + LightGBM | 20/20 | 20/20 | 0.07–0.53 | 0.14–0.46 |
| binned | BorutaPy + LightGBM | 20/20 | 20/20 | 0.09–0.51 | 0.06–0.27 |

- **Speed:** with four times the data and twice the cores, Bankai exact took 1.5–2.0× its 1× time, against 1.8–3.3× for BorutaPy + ExtraTrees and 2.1–2.9× for BorutaPy + LightGBM. Against BorutaPy + ExtraTrees, Bankai exact is now 8.0× faster in Industrial (4.0× at 1×), 7.2× in Crédito (4.9×), 5.4× in Cibersegurança (4.5×) and 1.9× in Bioinformática (1.7×).
- **Memory:** Bankai exact keeps about half the memory of BorutaPy + ExtraTrees (50–51%) and Bankai binned 20–30%. BorutaPy + LightGBM peaked at 21.8 GiB in Bioinformática, 17× Bankai binned.
- **Selection:**
  - No method confirmed an irrelevant feature in any of the 400 fits.
  - Every method confirmed the same set in all five repeats of each seed.
  - Industrial, Crédito and Bioinformática: all four methods confirmed identical sets in every seed. With 2× data, BorutaPy + LightGBM now finds all 30 relevant features in Bioinformática (it missed up to 12 at 1×).
  - Cibersegurança: every method reached the 40-round cap. Bankai exact matched BorutaPy + ExtraTrees in three seeds and differed by one or two borderline features in the other two; Bankai binned confirmed 44–48 features (recall 0.77) and BorutaPy + LightGBM 35–43. Recall rose for every method against 1×.
- **Noise:** the largest per-seed coefficient of variation over the five repeats was 2.3% for Bankai exact, 2.4% for BorutaPy + ExtraTrees, 3.2% for BorutaPy + LightGBM and 5.9% for Bankai binned (one Bioinformática seed).
