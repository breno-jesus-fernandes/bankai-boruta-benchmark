# Completed benchmark campaign — 2026-10-17/18 UTC

[Read the complete analysis in Portuguese](analysis/ANALISE.md).

The archive contains **210 unique successful measurements**: 140 quality trials
(four datasets × seven configurations × five seeds, at 16 threads) and 70 new
Industrial scaling trials (seven configurations × five seeds × 4/8 threads).
Scaling comparisons reuse 35 original quality observations at 16 threads, without
relabeling or counting them again as new executions. Warmups are excluded.

## Reports and paper artifacts

- [Quality metrics, median/Q1/Q3/IQR](analysis/quality/summary_by_dataset.csv)
- [Scaling at 4, 8 and reused 16 threads](analysis/scaling/thread_scaling.csv)
- [Paired quality comparisons and selection parity](analysis/paired_quality_comparisons.csv)
- [Paired differences between 8 and 16 threads](analysis/paired_8_vs_16.csv)
- [Main quality table, LaTeX](analysis/quality/wmecai_table1.tex)
- [Additional Python Greedy–LightGBM table](analysis/quality/wmecai_lightgbm_greedy.tex)
- [Industrial/16-thread paper commands](analysis/quality/wmecai_placeholders.tex)
- [Literal paper placeholder replacements](analysis/quality/placeholder_replacements.json)
- [Validation counts](analysis/validation.json) and [reused observation origins](analysis/scaling/origins.json)

The automatic report's completion flag means the specified cells are complete;
it is not an endorsement of statistical significance or publication readiness.
Five seeds, fixed synthetic profiles, backend differences, sequential host/order
effects, and the absence of one-thread scaling data limit interpretation.

## Figures

Every figure is provided as editable SVG, vector PDF and PNG. Whiskers represent
Q1–Q3, not confidence intervals. The 16-thread points are hollow to identify
reused quality measurements. Method codes are defined in the analysis script.

- [Quality fit time](analysis/figures/quality_fit_time.svg)
- [Quality peak memory](analysis/figures/quality_peak_memory.svg)
- [Selection metrics and downstream AUC](analysis/figures/quality_selection_and_auc.svg)
- [Scaling fit time](analysis/figures/scaling_fit_time.svg)
- [Paired scaling speedup relative to four threads](analysis/figures/scaling_speedup.svg)

## Reproduction and provenance

From the repository root, without AWS access or any model API:

```sh
uv sync --locked
uv run python scripts/analyze_campaign.py \
  --quality verification/campaign-20261017/quality/input \
  --scaling verification/campaign-20261017/scaling/input \
  --output reports/reproduced-analysis
uv run python scripts/verify_campaign_archive.py verification/campaign-20261017
```

`quality/input/` and `scaling/input/` preserve the original manifests, raw JSON
and downstream references. The 237 source JSON objects were checked byte for
byte against their single-part S3 ETags; local SHA256s are in
[the integrity record](aws/archive-integrity.json). `checksums.json` covers the
complete final archive, including reports and figures.

The measured Python package source reconstructs exactly from revision
`e11befc25ceb16e0367b965df8f17c6f7a6890ed`, published by
[workflow 39059529475](https://github.com/breno-jesus-fernandes/bankai-boruta-benchmark/actions/runs/39059529475).
[The reconstructed package-file hashes](measurement-source.json) match the
source fingerprint in both measured manifests. The immutable image is
`642504869083.dkr.ecr.us-east-1.amazonaws.com/bankai-image-publisher-images@sha256:e1153cdb5d95fe72b42ae23c491bf30217055593d2de84a5ba6f65e23b19c4e4`.
The scaling grid wrapper and its hash are recorded in
[the reduced scaling plan](../../deployment/SCALING48.md).

## AWS status and cost limits

[The read-only audit](aws/audit.json) found no nonterminated EC2 instances,
unattached EBS volumes, Elastic IPs or active NAT gateways in us-east-1 and
sa-east-1. All five benchmark ASGs have desired/max capacity zero. The result
bucket, immutable ECR images and log objects are retained; storage and requests
can continue to be billed. No paid compute was started for this analysis.

Six ASG launch-to-termination intervals total approximately 4.80 instance-hours.
At the verified USD0.714/hour rate, the **compute-only operational estimate** is
USD3.43 (about BRL28.97 using the planning conversion BRL6.50/USD plus 30%). This
is not a billing-meter reading and excludes EBS, IPv4, S3, ECR, CloudWatch,
requests, taxes and final currency conversion. The archived Cost Explorer query
is delayed, account-wide, partial and excludes the current UTC day; its tiny
posted total must not be mistaken for the final campaign bill.

The authorized campaign limit remains BRL400. Ledger reservations are allocations,
not charges. The vCPU quota increase request starts no instances automatically.
To recheck billing after AWS posts the usage (a billable Cost Explorer API query):

```sh
uv run python scripts/audit_campaign_aws.py \
  --archive verification/campaign-20261017 --refresh-billing
```

Refreshing the audit changes its artifacts; regenerate `checksums.json` after
any such refresh. Preserve the original committed snapshot for provenance.
