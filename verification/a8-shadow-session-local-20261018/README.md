# Bankai Boruta a8 shadow session: local Industrial comparison — 2026-10-18

Candidate: Bankai Boruta **0.1.0a8** (breno-jesus-fernandes/bankai-boruta#21,
commit `d2ae35c`) with BankaiRF **0.1.0a17** (breno-jesus-fernandes/bankai-random-forest#22,
commit `9a9a55a`), both published on PyPI on 2026-10-19. Comparator:
BorutaPy 0.4.3 with scikit-learn 1.9.1 `ExtraTreesClassifier`.

These are **local** measurements, not the AMD protocol: Apple M1 (4 performance
+ 4 efficiency cores), 8 GiB, macOS 26.6.2, Python 3.13.1, NumPy 2.5.4, 4 threads.
The AMD c7a.4xlarge validation uses `scripts/native_shadow_pilot.py` (protocol `native-shadow-max40-v1`).

## Fairness settings

Every method used Industrial `full` (200,000 × 500 float32 training split), 100
trees, depth 6, `max_features="sqrt"`, bootstrap, gini, `perc=100`,
`alpha=0.05`, `two_step=True`, `max_iter=41` (at most 40 rounds), no early
stopping, `random_state=seed`, 4 threads. Each fit ran in a fresh process that
only loads the cached arrays (`scripts/a8_local/cache_industrial.py`), so the
reported memory is the fit's own peak RSS growth over that baseline
(`ru_maxrss` after fit minus after loading). Methods ran sequentially.

## Results (`full_iso.jsonl`; seed 42 exact from `seed42_exact_rerun.json`)

| Method | Fit time, median [min, max] | Fit RSS growth, median | Rounds (seeds 42–46) |
|---|---:|---:|---|
| Bankai a8, exact Extra Trees | **44.8 s** [24.0, 48.8] | **1,093 MiB** | 34, 9, 37, 40, 12 |
| Bankai a8, binned Extra Trees (63 bins) | **48.1 s** [26.1, 48.8] | **670 MiB** | 16, 40, 40, 40, 12 |
| BorutaPy + scikit-learn ExtraTrees | 80.6 s [66.6, 97.5] | 2,184 MiB | 16, 19, 34, 40, 12 |

- Both Bankai backends were faster than BorutaPy and used less memory **in every
  seed** (exact: 1.6–3.1× faster; binned: 1.6–2.5× faster).
- All three methods confirmed the same eight features within each seed
  (the generator permutes feature positions per seed): precision 1.0 and
  recall 0.667 against the 12 relevant features.
- The first seed-42 exact run (45.4 s) overlapped with a LaTeX compilation and
  was repeated; the table uses the repeat (44.8 s, same rounds and selection).

Five-round fits isolate the 500-feature rounds (`memfit.py … 5 4 42`):

| Method | Time | Fit RSS growth |
|---|---:|---:|
| Bankai a8 exact | 13.3 s | 1,068 MiB |
| Bankai a8 binned | 13.1 s | 662 MiB |
| Bankai a7 exact (materialized reference) | 30.2 s | 1,460 MiB |
| Bankai a7 binned (materialized reference) | 41.9 s | 1,042 MiB |
| BorutaPy + scikit-learn ExtraTrees | 39.4 s | 2,037 MiB |

## Round counts

Round counts are a property of the shared statistical rule plus forest noise,
not of the implementation. On a 20,000-row Industrial subset (`mini.py`):

| Run | Seeds | Mean rounds ± s.e. | Capped at 40 |
|---|---:|---:|---:|
| a8 native exact (`mini60_v2.jsonl`) | 60 | 32.1 ± 1.4 | 38 |
| a7 native exact (`mini60.jsonl`) | 60 | 35.6 ± 1.2 | 47 |
| BorutaPy + BankaiRF a16 (`mini60.jsonl`) | 60 | 35.1 ± 1.2 | 46 |
| BorutaPy + scikit-learn ExtraTrees (`mini60.jsonl`) | 60 | 35.1 ± 1.2 | 45 |

On 5,000 rows, the a7 controller and BorutaPy with the same BankaiRF forest gave
38.8 ± 0.4 and 39.3 ± 0.2 rounds over 150 seeds (`ctrl150.jsonl`). Bankai's
exact gain importance equals scikit-learn's mean decrease in impurity (tested in
BankaiRF a17). Rounds are therefore statistically tied; the a8 gains are per-round
time and memory. Uniform `trap_noise` columns gain more from random Extra Trees
thresholds than Gaussian shadows, sit near 50% hits and keep many fits at the
40-round cap for every implementation.

## Reproduction

```bash
cd verification/a8-shadow-session-local-20261018   # or any scratch directory
python ../../scripts/a8_local/cache_industrial.py 42 43 44 45 46
for s in 42 43 44 45 46; do for m in bankai_exact bankai_binned borutapy; do
  python ../../scripts/a8_local/memfit.py $m 40 4 $s; done; done
```

`BANKAI_BORUTA_EXACT_REFERENCE=1` selects Bankai's a7 materialized path.
