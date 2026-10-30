# CIC-IDS2017 with bankai-boruta 0.1.0a12, 2026-10-23

Protocol `native-shadow-max40-v1` on the real CIC-IDS2017 training split
(1,748,586 × 78, float32; `scripts/prepare_cicids2017.py`), with the
Cybersecurity profile's configuration, 16 threads on one c7a.4xlarge and seeds
42–46, one repeat each. Candidate: the public **bankai-boruta 0.1.0a12** and
**bankai-random-forest 0.1.0a20**, unpacked by `scripts/run_candidate_probe_aws.py`
over image `sha256:b9209d5a…0d74`. State: `../native-shadow-cicids2017-a12-amd-20261023.json`
(run `20261023T131809Z`, about 1 h of host time, USD 4.50 reserved).

The 0.1.0a8 baseline is `../native-shadow-cicids2017-amd-20261023/` (same data SHA256).
AUC is the held-out ROC AUC of the suite's downstream ExtraTrees on each confirmed set
(0.99871 with all 78 features).

| Method | Time (s) | RSS (MiB) | s/round | Rounds | Confirmed | AUC | 0.1.0a8 time (s) | 0.1.0a8 RSS (MiB) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Bankai exact | 39.8 | 2,140 | 3.29 | 12 | 68 | 0.99872 | 98.7 | 5,091 |
| Bankai binned | 129.2 | 1,517 | 3.23 | 40 | 66 | 0.99874 | 304.5 | 3,372 |
| BorutaPy + ExtraTrees | 130.8 | 4,146 | 11.0 | 12 | 68 | 0.99872 | 128.8 | 4,131 |
| BorutaPy + LightGBM | 280.3 | 2,736 | 7.02 | 40 | 66 | 0.99874 | 278.1 | 2,739 |

- **Same decisions:** Bankai exact confirmed the same 68 features as BorutaPy + ExtraTrees and as 0.1.0a8 in every seed.
- **Against BorutaPy + ExtraTrees:** Bankai exact is 3.3× faster and uses about half the memory. With 0.1.0a8 it used 1 GiB more than BorutaPy + ExtraTrees.

## How the memory gap was closed

The development probes that led to 0.1.0a20 of bankai-random-forest are kept for reference:

- `../allocator-probe-amd-20261023.json` (`scripts/run_allocator_probe_aws.py`): glibc tuning (`MALLOC_ARENA_MAX=2`, a 64 KiB mmap threshold) and 8 threads against the 0.1.0a8 baseline.
- `../candidate-probe-o7-amd-20261023/` and `../candidate-probe-o10-amd-20261023/`: local candidate wheels against the published 0.1.0a11. Every candidate gave the same confirmed set as 0.1.0a11 in every seed.

The changes kept one row buffer per tree partitioned in place, integer class
counts packed with the label bit, bootstrap weights stored as `u32` counts, and
float32 thresholds compared without widening.
