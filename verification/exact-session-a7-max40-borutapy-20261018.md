# Industrial max-40: BorutaPy ExtraTrees comparison

Run ID: `20261018T220322Z`, protocol `exact-session-a7-max40-v1`. The comparison
used the frozen Industrial `full` dataset (seed 42, data SHA256
`ecbd7f59d56aa8e8c14b1567343d1b0916bc15d4e1ee02b0cb7b0dcceaff9988`), 100
trees, depth 6, `max_features="sqrt"`, bootstrap, float32, and 16 physical AMD
cores on `c7a.4xlarge`. Jobs ran sequentially on isolated processes and hosts.
The three processes reported the same Linux kernel, architecture, and 16 logical
CPUs. Fit time and external process RSS were measured over three repetitions.

| Method | Fixed-40 median time | Fixed-40 median RSS | Capped-40 median time | Capped-40 median RSS | Actual rounds |
|---|---:|---:|---:|---:|---:|
| BorutaPy 0.4.3 + sklearn ExtraTrees 1.9.1 | 35.331 s | 2,377.6 MiB | 35.357 s | 2,378.2 MiB | 16 / 16 |
| Bankai a6 + BankaiRF a15 (materialized reference) | 44.739 s | 2,179.0 MiB | 44.044 s | 2,179.3 MiB | 40 / 39 |
| Bankai a7 + BankaiRF a16 (virtual session) | 45.502 s | 1,831.1 MiB | 44.380 s | 1,830.4 MiB | 40 / 39 |

BorutaPy confirmed the same eight feature indices as both Bankai variants in
all repetitions: `13, 41, 45, 79, 126, 270, 298, 320`. Bankai retained feature
`64` as tentative; BorutaPy retained no tentative features. These are close
selection results, not an assertion of statistical parity between independent
implementations.

Against the generator's 12 relevant features (the union of its strong, medium,
and weak intensity groups), confirmed-only precision was **1.000** and recall
was **0.667** for all three methods: each confirmed 8 true features and no
irrelevant features. If tentative features are counted as selected, precision
is **0.889** for either Bankai variant (the extra tentative feature 64 is
irrelevant) and **1.000** for BorutaPy; recall remains **0.667** for all.

BorutaPy's median run was about 20–21% shorter than the Bankai medians, while
using about 199 MiB more RSS than the materialized reference and about 547 MiB
more than the virtual session. Interpret the time together with actual rounds:
BorutaPy stopped naturally at round 16 after deciding every feature; Bankai ran
39 or 40 rounds. Thus this is a capped full-selector comparison, not a
same-round backend benchmark. `fixed-40` denotes a 40-round ceiling; BorutaPy
can stop when no tentative features remain. Its capped configuration uses
`n_iter_no_change=100`, which exceeds the 40-round budget, so the same natural
decision stop applies in both modes.

| Mode | Artifact | Bytes | SHA256 |
|---|---|---:|---|
| Bankai fixed-40 | `industrial-seed42-t16-fixed-40.json` | 2,654,737 | `ef2901ba8855b759297f3230fcc6b14eb035d1069c0d4fa4ce0ffbe39e3fbeca` |
| Bankai capped-40 | `industrial-seed42-t16-capped-40.json` | 2,605,733 | `77ad8ebf40ec94382d4fb31bc52065207fd99d9ef1058d2811b5f1b8f5aab960` |
| BorutaPy fixed-40 | `industrial-seed42-t16-borutapy-fixed-40.json` | 403,142 | `3dbeb30175ea2bf26a416cc9efcc171108a31615e8b298756a95b0480159e23d` |
| BorutaPy capped-40 | `industrial-seed42-t16-borutapy-capped-40.json` | 403,143 | `ff5d188bb4a340e56da9eae601b272c338578811a183006bb4bacb279bec3a7e` |

All four artifacts are stored under
`s3://bankai-benchmark-bootstrap-results-ku2wdx1kzzqb/exact-session-a7-max40-v1/pilot/20261018T220322Z/`.
The BorutaPy image used immutable digest
`sha256:b6b86a188af16ac4700ec752c3ec3e67c0352da0b801a19b9049b80302ed0452`
(publisher workflow run [39171356672](https://github.com/breno-jesus-fernandes/bankai-boruta-benchmark/actions/runs/39171356672));
the comparator was added in [PR #12](https://github.com/breno-jesus-fernandes/bankai-boruta-benchmark/pull/12).

The BorutaPy task role initially lacked permission for the benchmark result
prefix, so its first fit completed but its artifact write was denied. No
measurements from that attempt were retained. The task role was corrected via
CloudFormation, the reservation was transferred to the supplemental fleet
without adding a budget slot, and all four artifacts were subsequently
written and hash-checked. The original shutdown deadline remained
`2026-10-18T23:02:16Z`; the supplemental fleet returned to zero and its host
terminated at 22:30 UTC.
