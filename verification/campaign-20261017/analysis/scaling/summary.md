# COMPLETE

Industrial; five seeds per method/thread. Original quality measurements at 16 threads are reused.
Speedup = paired T4/Tt. Relative efficiency = speedup/(t/4); no one-thread efficiency is claimed.

| Method | Threads | Seeds | Fit seconds, median | Peak GiB, median | Paired speedup vs 4 |
|---|---:|---:|---:|---:|---:|
| bankai_classic_native | 4 | 5/5 | 36.839 | 1.285 | 1.000 |
| bankai_classic_native | 8 | 5/5 | 22.319 | 1.302 | 1.651 |
| bankai_classic_native | 16 | 5/5 | 23.597 | 1.363 | 1.524 |
| bankai_classic_adapter | 4 | 5/5 | 36.252 | 2.162 | 1.000 |
| bankai_classic_adapter | 8 | 5/5 | 26.828 | 2.192 | 1.351 |
| bankai_classic_adapter | 16 | 5/5 | 28.862 | 2.243 | 1.242 |
| bankai_greedy_native | 4 | 5/5 | 56.289 | 1.291 | 1.000 |
| bankai_greedy_native | 8 | 5/5 | 33.282 | 1.305 | 1.703 |
| bankai_greedy_native | 16 | 5/5 | 36.710 | 1.364 | 1.533 |
| borutapy_lightgbm_rf | 4 | 5/5 | 70.024 | 2.731 | 1.000 |
| borutapy_lightgbm_rf | 8 | 5/5 | 52.078 | 2.760 | 1.345 |
| borutapy_lightgbm_rf | 16 | 5/5 | 51.250 | 2.772 | 1.358 |
| borutapy_sklearn_et | 4 | 5/5 | 57.444 | 1.128 | 1.000 |
| borutapy_sklearn_et | 8 | 5/5 | 37.499 | 1.146 | 1.531 |
| borutapy_sklearn_et | 16 | 5/5 | 37.719 | 1.179 | 1.521 |
| greedy_borutapy_bankai | 4 | 5/5 | 50.291 | 1.447 | 1.000 |
| greedy_borutapy_bankai | 8 | 5/5 | 36.453 | 1.480 | 1.378 |
| greedy_borutapy_bankai | 16 | 5/5 | 39.991 | 1.524 | 1.253 |
| greedy_borutapy_lightgbm | 4 | 5/5 | 94.806 | 2.545 | 1.000 |
| greedy_borutapy_lightgbm | 8 | 5/5 | 69.056 | 2.932 | 1.374 |
| greedy_borutapy_lightgbm | 16 | 5/5 | 64.523 | 2.931 | 1.465 |
