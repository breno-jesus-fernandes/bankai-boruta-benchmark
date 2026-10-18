# Exact-session AMD pilot — 2026-10-18

This is a bounded pilot for the distinct `exact-session-a7-v1` benchmark identity. It does not modify or replace the frozen a6 observations.

## Setup

- Host: AWS `c7a.4xlarge`, 16 physical cores, 1 thread per core; Linux x86_64, Python 3.11.17.
- Dataset: Industrial, seed 42, 200,000 × 500, float32; training configuration 100 trees and 16 workers.
- Reference: `bankai-boruta==0.1.0a6` with `bankai-random-forest==0.1.0a15`.
- Candidate: `bankai-boruta==0.1.0a7` with `bankai-random-forest==0.1.0a16`, `BANKAI_BORUTA_EXACT_SESSION=1`.
- Candidate image: `642504869083.dkr.ecr.us-east-1.amazonaws.com/bankai-image-publisher-images@sha256:4a4663a4320f0e101567a6af86b5910d31fac39175165da0b8cc0aa784309de6`.
- Both configurations ran three paired repetitions on the same host. RSS is the external process peak measured for the fit. The full-fit run used `max_iter=120` and both paths reached 119 rounds with `stop_reason=max_iter`.

## Results

| Industrial run | Reference median | Session median | Time change | Reference peak RSS | Session peak RSS | RSS change | Parity |
|---|---:|---:|---:|---:|---:|---:|---|
| Fixed 5 rounds | 18.512 s | 19.272 s | +4.11% | 2,176.6 MiB | 1,796.3 MiB | −17.47% | passed |
| Complete fit (119 rounds) | 79.036 s | 76.968 s | −2.62% | 2,180.0 MiB | 1,843.2 MiB | −15.45% | passed |

All paired repetitions had the same generated-data SHA-256 (`ecbd7f59d56aa8e8c14b1567343d1b0916bc15d4e1ee02b0cb7b0dcceaff9988`). The comparison artifact reports parity passed for both hit/decision results and the paired run outputs.

The fixed-round result isolates backend overhead: the candidate used less memory but was 4.11% slower at five rounds. In the complete-fit pilot, the candidate was 2.62% faster and used 15.45% less peak RSS. These are preliminary medians from one seed and one worker count, not evidence for the full 90-pair acceptance grid.

For context, the existing `quality/full` Industrial benchmark measured BorutaPy + scikit-learn ExtraTrees at **37.719 s** median across five seeds, 16 workers, and 49 median rounds (`verification/pilot-20261017/report/summary_by_dataset.csv`). That is not a same-round comparison: this exact-session pilot ran 119 rounds in the complete-fit configuration.

## Artifacts and cost

- [Fixed 5-round JSON](s3://bankai-benchmark-bootstrap-results-ku2wdx1kzzqb/exact-session-a7-v1/pilot/20261018T213834Z/industrial-seed42-t16-fixed-5.json) (777,050 bytes; SHA-256 `83677d9764cd4f3a3e141022627903b5862c075de5f6f7f6693f7ff9ed0008fa`).
- [Complete-fit JSON](s3://bankai-benchmark-bootstrap-results-ku2wdx1kzzqb/exact-session-a7-v1/pilot/20261018T213834Z/industrial-seed42-t16-complete.json) (6,537,196 bytes; SHA-256 `1462c9dca687598abe9cf14c911df85a2ccf93bb53da66796d1d6d3c40de371d`).
- The pilot reserved R$20 from the existing ledger. No additional reservation was made; the protected R$80 reserve was preserved.
- AWS shutdown was set for 2026-10-18 22:36 UTC. The task completed with exit code 0 at 21:49 UTC. The fleet returned to zero with no remaining Auto Scaling instances, and the temporary CloudFormation stack was deleted.

## Limitations

Only seed 42, 16 workers, 100 trees, one five-round fit, and one complete-fit configuration were run. The pilot does not cover 1/4 workers or seeds 43–46, and it is insufficient to enable the session path by default. The remaining acceptance campaign requires additional budget authorization.
