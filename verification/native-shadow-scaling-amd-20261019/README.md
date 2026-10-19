# Native shadows on AMD: thread scaling on Industrial, 2026-10-19

Same protocol, image (`sha256:a8909f1f…823e`), host type and settings as
`../native-shadow-amd-20261019/`, restricted to Industrial (200k × 500) with
4 and 8 threads. The 16-thread column comes from that report. Seeds 42–46,
one fit per method and seed (the 16-thread values are medians of three).

| Run | Threads | State |
|---|---:|---|
| `20261019T092745Z` | 4 | `../native-shadow-scaling-t4-amd-20261019.json` |
| `20261019T100132Z` | 8 | `../native-shadow-scaling-t8-amd-20261019.json` |

- **Integrity:** every artifact matched its S3 SHA256 metadata.
- **Same data:** each seed has the same data SHA256 at 4, 8 and 16 threads.
- **Cost:** each run armed its shutdown before any capacity and reserved 2 h and 1 h in the supplemental USD 150 ledger (USD 3 + 1.50). Both fleets returned to zero and both stacks were deleted.

## Median time and fit RSS over five seeds

| Method | 4 threads | 8 threads | 16 threads | Speedup 4→16 |
|---|---:|---:|---:|---:|
| Bankai exact | 70.1 s / 942 MiB | 37.3 s / 1,064 MiB | 22.5 s / 1,283 MiB | 3.1× |
| Bankai binned | 45.6 s / 419 MiB | 24.7 s / 496 MiB | 15.6 s / 667 MiB | 2.9× |
| BP/E | 71.2 s / 1,639 MiB | 47.9 s / 1,698 MiB | 37.5 s / 1,817 MiB | 1.9× |
| BP/L | 132.2 s / 4,818 MiB | 95.4 s / 4,848 MiB | 75.1 s / 4,865 MiB | 1.8× |

## Per-seed comparison

| Bankai backend | vs | 4 threads: faster / less memory | 8 threads: faster / less memory |
|---|---|---|---|
| exact | BP/E | 4/5 (0.62–1.03×) / 5/5 (0.57–0.58×) | 5/5 (0.48–0.82×) / 5/5 (0.62–0.63×) |
| binned | BP/E | 5/5 (0.39–0.64×) / 5/5 (0.26×) | 5/5 (0.33–0.51×) / 5/5 (0.29×) |
| exact | BP/L | 5/5 (0.33–0.62×) / 5/5 (0.19–0.20×) | 5/5 (0.24–0.46×) / 5/5 (0.22–0.24×) |
| binned | BP/L | 5/5 (0.19–0.37×) / 5/5 (0.09×) | 5/5 (0.15–0.27×) / 5/5 (0.10–0.11×) |

- **Selection and rounds are thread-independent.** For every method and seed, the confirmed set and the round count were identical at 4, 8 and 16 threads, and so were precision (1.00) and recall (0.67).
- **Bankai scales better.** From 4 to 16 threads, Bankai's time falls about 3×. BorutaPy's falls about 1.8–1.9×, because its Python loop and per-round shadow copy stay serial. So the gap widens with cores.
- **Where Bankai lost:** at 4 threads, Bankai exact was 1.03× slower than BP/E on seed 42. It was faster on the other four seeds.
- **Memory grows with threads for Bankai.** Each worker has its own buffers, so fit RSS rises from 942 to 1,283 MiB (exact) and from 419 to 667 MiB (binned). It is still below BP/E and BP/L at every thread count.
