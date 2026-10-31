# CIC-IDS2017 with bankai-boruta 0.1.0a12 on 32 cores, 2026-10-31

The run of `../native-shadow-cicids2017-a12-amd-20261023/` repeated on a 32-core
host: protocol `native-shadow-max40-v1` on the real CIC-IDS2017 training split
(1,748,586 × 78, float32, unscaled), the Cybersecurity profile's configuration,
seeds 42–46, one repeat each, 32 threads on one c7a.8xlarge (32 physical AMD
cores, SMT off, 64 GiB). Image `sha256:b4a44fc7…24cd6e` pins **bankai-boruta
0.1.0a12** and **bankai-random-forest 0.1.0a20** over the same comparator stack.
State: `../native-shadow-x2-cicids-amd32-20261030.json` (run `20261031T142953Z`,
USD 6 reserved).

| Method | Time (s) | RSS (MiB) | s/round | Rounds | Confirmed | AUC | 16 threads time (s) | 16 threads RSS (MiB) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Bankai exact | 22.3 | 3,033 | 1.84 | 12 | 68 | 0.99872 | 39.8 | 2,140 |
| Bankai binned | 75.3 | 2,428 | 1.88 | 40 | 66 | 0.99874 | 129.2 | 1,517 |
| BorutaPy + ExtraTrees | 92.1 | 5,888 | 7.72 | 12 | 68 | 0.99872 | 130.8 | 4,146 |
| BorutaPy + LightGBM | 250.6 | 2,759 | 6.27 | 40 | 66 | 0.99874 | 280.3 | 2,736 |

- **Same decisions as on 16 threads:** every method confirmed the same features in the same number of rounds, seed by seed (20 of 20 method × seed pairs), so the AUC is unchanged.
- **Doubling the cores:** Bankai exact went 1.8× faster and Bankai binned 1.7×, against 1.4× for BorutaPy + ExtraTrees and 1.1× for BorutaPy + LightGBM. Bankai exact is now 4.1× faster than BorutaPy + ExtraTrees (3.3× on 16 threads).
- **Memory grows with the threads:** per-thread buffers add about 0.9 GiB to both Bankai modes and 1.7 GiB to BorutaPy + ExtraTrees; BorutaPy + LightGBM is flat. Bankai exact still uses about half the memory of BorutaPy + ExtraTrees.
