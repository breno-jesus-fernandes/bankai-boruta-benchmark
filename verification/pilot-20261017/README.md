# Industrial quality pilot — 2026-10-17

35 intended Industrial trials completed successfully: seven methods, seeds
42–46, 16 threads, full-size dataset. ECS task exited with code 0. The shared
quality manifest covers all four datasets (140 trials), so this snapshot is
provisional and lists 105 missing trials from the three other datasets.

The `input/` directory preserves the original S3 manifest, raw measurements,
and five oracle/all-feature reference records. The `report/` directory contains
the manifest-validated aggregation, median/IQR CSV, TeX, and completeness report.
These data describe synthetic Industrial performance; they are not evidence
about the other datasets or thread scaling.

- Bucket: `bankai-benchmark-bootstrap-results-ku2wdx1kzzqb`
- Prefix: `pilot-20261017-quality/`
- Cluster: `pilot-20261017`, region `us-east-1`
- Task: `8248a1e6e7a54501ac2d6294d3bf8e74`
- Image: `sha256:e1153cdb5d95fe72b42ae23c491bf30217055593d2de84a5ba6f65e23b19c4e4`

Reproduce the report with:

```sh
uv run bankai-aggregate --results verification/pilot-20261017/input \
  --output reports/pilot-reproduced --provisional
```
