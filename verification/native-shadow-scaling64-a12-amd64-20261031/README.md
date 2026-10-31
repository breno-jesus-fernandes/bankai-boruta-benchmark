# Thread scaling 8/16/32/64 on Industrial 2×, bankai-boruta 0.1.0a12, 2026-10-31

Protocol `native-shadow-max40-v1` on the Industrial 2× profile (400k × 1,000
training rows, 12 relevant features, `--scale 2`), the four methods of
`../native-shadow-x2-a12-amd32-20261031/`, seeds 42–46, one repeat, run with 8,
16, 32 and 64 threads in sequence by one task on one host. Image
`sha256:610ec1cb…1f61480` (built from `dd68012`) pins **bankai-boruta 0.1.0a12**
and **bankai-random-forest 0.1.0a20** over the same comparator stack as the 2×
campaign; the downstream AUC ran inside the container after the 64-thread pass
(`--auc`).

- **Host:** one EC2 c7a.16xlarge (64 physical AMD cores, SMT off, 128 GiB) on ECS.
- **State:** `../native-shadow-scaling64-amd64-20261031.json`. Task from 18:07Z to 20:33Z; runs `20261031T180749Z` (8), `20261031T185414Z` (16), `20261031T192947Z` (32) and `20261031T200055Z` (64).
- **Budget:** USD 24 reserved (4 armed hours at USD 6) after raising the supplemental ledger from USD 150 to 165 (`../native-shadow-scaling64-cost-policy-20261031.md`); about 2.5 host hours, roughly USD 8–9 on demand. Fleet drained by the runner, stack deleted.

## Results (median over five seeds)

| Method | 8 thr (s) | 16 thr (s) | 32 thr (s) | 64 thr (s) | Speedup 8→64 | RSS 8 thr (MiB) | RSS 64 thr (MiB) |
|---|---:|---:|---:|---:|---:|---:|---:|
| Bankai exact | 39.1 | 21.6 | 13.6 | **10.2** | 3.7× | 3,211 | 3,780 |
| Bankai binned | 46.2 | 27.3 | 18.5 | 14.8 | 3.1× | **1,301** | **1,963** |
| BorutaPy + ExtraTrees | 171.5 | 135.3 | 120.5 | 116.2 | 1.5× | 6,387 | 7,509 |
| BorutaPy + LightGBM | 267.9 | 211.5 | 191.8 | 181.5 | 1.5× | 13,183 | 13,300 |

Speedups are medians of per-seed ratios against the same seed at 8 threads.

| Threads | Bankai exact vs BorutaPy + ExtraTrees (time) | Bankai binned vs BorutaPy + ExtraTrees (time) | Bankai exact vs BorutaPy + LightGBM (time) | Bankai exact / BorutaPy + ExtraTrees (memory) |
|---:|---:|---:|---:|---:|
| 8 | 4.3× faster (4.1–5.8) | 3.7× (3.5–5.3) | 6.9× | 0.50 |
| 16 | 6.1× (5.7–7.8) | 5.0× (4.7–6.7) | 9.7× | 0.50–0.51 |
| 32 | 8.9× (8.2–10.6) | 6.5× (6.1–8.1) | 13.7× | 0.50 |
| 64 | **11.2×** (10.0–12.9) | 7.8× (7.4–9.4) | 18.2× | 0.50 |

- **Scaling:** from 8 to 64 threads Bankai exact went 3.7× faster (1.8× at 16, 2.9× at 32) and Bankai binned 3.1×; both BorutaPy variants gained about 1.5×, almost all of it by 32 threads. Bankai still gains from 32 to 64 threads (1.3×), so it has not saturated, though the parallel efficiency against 8 threads falls to 46% (exact) and 39% (binned).
- **Advantage grows with cores:** Bankai exact goes from 4.3× faster than BorutaPy + ExtraTrees at 8 threads to 11.2× at 64, and from 6.9× to 18.2× against BorutaPy + LightGBM.
- **Memory:** per-thread buffers add about 0.6 GiB to each Bankai mode and 1.1 GiB to BorutaPy + ExtraTrees from 8 to 64 threads; BorutaPy + LightGBM is flat. Bankai exact stays at half the memory of BorutaPy + ExtraTrees at every thread count.
- **Selection:** every method confirmed the same 8 features in every seed and every thread count (precision 1.00, recall 0.67), with the same rounds per seed, and the same sets as the 2× campaign on the c7a.8xlarge; AUC 0.840 for every method (0.817 with all features, 0.841 with only the relevant ones).
- **AUC depends on the platform, not the threads:** the 2× campaign computed the Industrial AUC on an Apple Silicon laptop; this run computed it on x86 with the same data (equal `data_sha256`, regenerated on the laptop too), the same sets and the same package versions, and differs by up to 0.0016 per seed (median 0.840 in both). On the laptop the downstream AUC is identical with 1, 4 or 8 threads and with float32 or float64 input, so the gap comes from the ExtraTrees fit on arm64 against x86.
- **Against the 32-core host:** at 32 threads the c7a.16xlarge measured 13.6 s for Bankai exact and 120.5 s for BorutaPy + ExtraTrees, against 15.5 s and 123.9 s on the c7a.8xlarge (five repeats there, one here).

`summary.json` is `scripts/native_shadow_summary.py` on this folder, one row per thread count and method.
