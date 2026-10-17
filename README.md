# Bankai Boruta reproducible benchmark suite

Seven concrete feature-selection configurations, four deterministic synthetic
datasets, one fresh OS process per trial, and manifest-validated paper reports.
New benchmark code is MIT-licensed. Bankai artifacts and the upstream patch retain
their GPL license; see [DEPENDENCIES.md](DEPENDENCIES.md).

```sh
uv sync --locked
make test
make smoke
make aggregate
make smoke                    # successful matching trials are skipped
```

The quick smoke uses Industrial, 400 training rows, 100 test rows, 40 columns,
seed 42, one thread, eight trees, depth three, and Classic `max_iter=4`.
Greedy retains `ceil(log2(P / .05))` rounds. Measured validation, machine details,
and limitations are in [VERIFICATION.md](VERIFICATION.md).

## Release gate

Public `bankai-boruta==0.1.0a3` cannot honor positive `n_jobs` and fractional
`max_features` on its native path. This repository preserves the requested forest
profiles with an isolated development correction rather than silently changing
paths. [upstream/native-controls.patch](upstream/native-controls.patch) extends
native eligibility and threads the forest's resolved feature count and thread
count through the Rust boundary, preparation, and training. Per-round sampling
resolves against the current real-plus-shadow width using a15's validation.

The source baseline is recorded in [upstream/base-revision.txt](upstream/base-revision.txt).
Immutable local wheel/source archives and SHA-256 checksums are committed under
`artifacts/`; the archive includes `Cargo.lock` and the upstream GPL text. The
Rust forest dependency is pinned to source revision
`caa46c22ef93434cd87319490513e877d4378564`. These are development artifacts,
not a claimed public release. Rebuild instructions are in [upstream/README.md](upstream/README.md).

**`full` runs are intentionally gated.** Before paper execution, publish the
upstream correction, replace the development dependency/source override with its
verified public release, regenerate `uv.lock` with wheel hashes, run the native
parity tests and Linux smoke, and update
`src/bankai_benchmark/release-verification.json` with that verified version and
wheel hashes. No future version is assumed or manufactured by this repository.

## Experiment profiles

| Dataset ID | Train N | P | Trees | Depth | Bins | Feature sampling | Classic max_iter |
|---|---:|---:|---:|---:|---:|---|---:|
| industrial | 100,000 | 500 | 100 | 6 | 63 | sqrt | 50 |
| credito | 150,000 | 300 | 100 | 6 | 63 | sqrt | 50 |
| bioinformatica | 25,000 | 2,000 | 150 | 8 | 63 | 0.15 | 60 |
| ciberseguranca | 200,000 | 150 | 100 | 6 | 63 | sqrt | 40 |

Every selector uses `alpha=.05` and explicit tree counts. Classic uses `perc=100`,
`two_step=True`, and disabled early stopping. Bankai and BorutaPy Classic allow
at most `max_iter-1` fits. Greedy runs exactly `ceil(log2(P/alpha))` fits.
Only confirmed features enter primary metrics; tentative features are recorded.

```sh
make smoke-matrix
uv run bankai-benchmark full --suite quality --experiment paper-v1
uv run bankai-benchmark full --suite scaling --experiment paper-v1
```

`smoke-matrix` uses 5% of N, 30% of P, seeds 42/43, threads 1/4, one discarded
warmup per dataset/method/thread, original tree geometry, and Classic
`max_iter=10`. Width never falls below the relevant feature count; consequently
Cibersegurança has 60 columns in this mode. It is a substantial experiment,
not the two-minute smoke target. Full quality uses all four datasets, seeds
42–46, and 16 threads. Full scaling uses Industrial and threads 1/2/4/8/16.
Full campaigns discard two warmups with seeds 900001/900002. Warmups run in fresh
processes and warm system caches; measured workers are still fresh processes.
Quality and scaling receive separate experiment IDs (`NAME-quality`/`NAME-scaling`).

## Data generation and frozen implementation choices

`generate_dataset(dataset_id, seed, mode)` returns C-contiguous float32 matrices,
int32 binary targets, sorted relevant indices, shuffled subtype indices, and
calibration metadata. NumPy's independent `SeedSequence` streams control feature
sampling, categorical weights, logistic noise, column permutation, and row
splitting. NumPy and `scipy.special` generate the data; sklearn does not.

All 1.25N rows are generated jointly. Each causal contribution is standardized,
then their weighted sum is standardized. The logit is
`sqrt(SNR) * standardized_signal + standardized_logistic_noise`.
Quantile labeling gives the closest feasible integer class counts. Stratified
NumPy splitting produces N training and 0.25N test rows. Joint synthetic
calibration is explicitly recorded; no selector or downstream model fits on
test rows. The resulting benchmark is not a test of distribution shift.
Categorical columns retain integer encodings in X; their effect vectors alone
are standardized. The inverse column permutation remaps every subtype.

The handoff did not supply numerical prevalence/SNR settings, categorical
cardinalities, several subtype totals, or all downstream hyperparameters.
The following are transparent, versioned implementation defaults, **not recovered
claims about an earlier protocol**. Review them against the intended paper
protocol before running full campaigns.

| Dataset | Relevant composition | Prevalence | SNR | Noise allocation |
|---|---|---:|---:|---|
| Industrial | 6 Gaussian roots + 6 redundant correlates (rho=.95) | .5 | 2 | thirds: correlated, uniform trap, Gaussian |
| Crédito | 6 lognormal roots + 8 categorical signals + 6 redundant roots | .2 | 2 | 40 categorical trap + 240 Gaussian |
| Bioinformática | 10 Toeplitz marginals + 20 interaction sources | .5 | 1 | equal uniform trap/Gaussian |
| Cibersegurança | 20 step + 20 periodic + 20 sparse sources | .1 | 2 | 45 uniform trap + 45 Gaussian |

Industrial effects are three linear terms from roots 0–2, two squared terms
from roots 3–4, and root5×root0, equally weighted after standardization.
Correlated noise uses independent ten-column block latents (rho=.64 between
columns). Crédito uses six standardized log1p effects and eight random
categorical effects with cardinalities `[2,3,4,5,8,10,20,50]`. Its 40 categorical
noise columns repeat these cardinalities five times. Redundant columns add no
separate causal terms; relevance includes their signal information.
Bioinformatica uses Cholesky Toeplitz correlation `.8**abs(i-j)`, weights .35 on
ten marginal terms, and weights 1 on ten `tanh(2*u*v)` terms.
Cibersegurança uses Gaussian threshold-at-zero steps, uniform `[-pi,pi]` periodic
sources with sine effects, and Bernoulli(.05)×Exponential(1) sparse sources,
with equal standardized effect weights. Width scaling preserves every relevant
column and allocates noise by deterministic largest-remainder rounding.
One-row rounding tolerance applies when a target class rate is nonintegral.

Array caches live outside workers under `.cache/datasets`; keys include the
profile and generator hashes. Generator intermediates cannot inflate selector
memory. Generator contracts are tested on all four datasets without allocating
full-size profiles in routine CI.

## Methods and fairness

| Registry ID | Selector and backend | Path | Row sampling |
|---|---|---|---|
| bankai_classic_native | Bankai Classic / BankaiRF binned Extra Trees | asserted rust | bootstrap |
| bankai_classic_adapter | Bankai Classic / same BankaiRF | asserted python | bootstrap |
| bankai_greedy_native | Bankai Greedy / BankaiRF | asserted rust | bootstrap |
| borutapy_lightgbm_rf | BorutaPy / LightGBM RF | Python shadows | .8 subsample each round |
| borutapy_sklearn_et | BorutaPy / sklearn ExtraTrees | Python shadows | all rows, no bootstrap |
| greedy_borutapy_bankai | suite Python Greedy / BankaiRF | Python shadows | bootstrap |
| greedy_borutapy_lightgbm | suite Python Greedy / LightGBM RF | Python shadows | .8 subsample each round |

The Python Greedy implementation uses independent shadows, the fixed full
feature set, strict `importance > max(shadows)`, and hit-once confirmation.
It implements the specified shadow-threshold algorithm; the third-party
`greedyboruta` distribution is **not executed**. Methodological references:
[Boruta](https://www.jstatsoft.org/article/view/v036i11),
[GreedyBoruta methodology](https://pypi.org/project/greedyboruta/), and
[Bankai selector](https://github.com/breno-jesus-fernandes/bankai-boruta/blob/main/python/bankai_boruta/_estimator.py).

Tree counts and depth bounds are matched. Bankai bins and LightGBM `max_bin` are
63; sklearn ET has no histogram-bin parameter. LightGBM uses RF boosting,
`num_leaves=2**depth`, `subsample=.8`, `subsample_freq=1`, gain importances,
`min_child_samples=2`, deterministic column-wise training, no regularization,
and disabled automatic categorical detection. Its clonable wrapper resolves
`floor(sqrt(augmented_width))/augmented_width` at each fit for sqrt profiles,
and .15 for Bioinformática. Feature and split sampling semantics differ between
engines: these are matched budgets, not identical ensembles. Full effective
estimator parameters, including row sampling, are preserved in result JSON.
`BankaiRF` is not an exported a15 alias; the explicit classifier class is used.

## Measurement and result contract

Thread environment variables are set before numerical imports. Linux workers
constrain affinity to the requested number of available logical CPUs and set
estimator `n_jobs`. The prepared selector's `.fit()` alone is timed with
`perf_counter`; dataset loading, construction, and downstream prediction are
outside the fit interval. A 5ms RSS poll measures fit memory. Linux also records
raw `/proc/self/status` VmHWM immediately after fit and attempts the Linux
high-water reset through `/proc/self/clear_refs`. If reset fails, VmHWM is
explicitly labeled process-lifetime. Primary Linux peak is max(polling, VmHWM),
and delta is max(0, peak-baseline). Other systems explicitly report polling.
Bytes convert to GiB using 2**30. CPU model/topology, affinity, package versions,
source/configuration hashes, effective parameters, diagnostic copy counters,
and ECS identity/image/log provenance are recorded. Virtual shadows avoid the
augmented dense matrix; Bankai's float64 input conversion still occurs.

Every result includes schema version, trial/experiment IDs, suite/mode, dataset,
competitor, seed, threads, configuration hash, status, selection/execution/
downstream metrics, selected and tentative indices, diagnostics, provenance,
and error. Success, timeout, execution failure, and resource failure are distinct.
Unavailable values are JSON null; failed trials never become zero-valued
performance observations. The default timeout is 2400 seconds, with process
group cleanup. Local writes are atomic before S3 upload; transient upload
errors retry, failed uploads retain local files and return nonzero.

Primary precision/recall/F1/FDR use confirmed selections. Empty selections get
zero selection metrics and a training-prevalence constant downstream predictor.
Subtype recall is null when there is no relevant feature of that subtype;
`fp_trap_noise` is a count and its separate rate is also reported. Downstream
ExtraTrees uses 200 trees, sqrt sampling, balanced class weights, and the trial
seed; probability-based ROC AUC, accuracy, balanced accuracy, F1, and evaluation
time are recorded. Oracle and all-feature references run once per dataset/seed
in separate evaluation processes, outside selector measurement.

Matching successes are skipped. Use `--retry-failed` to retry recorded failures,
or `--overwrite` to replace matching results. A manifest mismatch requires a
new experiment ID, even with overwrite. Manifests cover the complete expected
grid and pin implementation and dependency versions; ECS shards share one grid.

## Reporting and paper placeholders

```sh
uv run bankai-aggregate --results results --output reports --provisional
uv run bankai-aggregate --bucket BUCKET --experiment NAME-quality \
  --experiment NAME-scaling --results downloaded --output paper-reports
```

Outputs include `summary_by_dataset.csv`, `thread_scaling.csv`, `summary.md`,
`wmecai_table1.tex`, an additional LightGBM Greedy table,
`wmecai_placeholders.tex`, `placeholder_replacements.json`, and
`completeness.json`. Statistics are median and Q1–Q3 (NumPy `linear` quantiles),
with numeric IQR columns and expected/successful/failure/missing counts.
Speedups are paired per seed against one thread before summarization;
efficiency is paired speedup/thread count. Timeout limits are never runtimes.

The versioned mapping is `src/bankai_benchmark/config-paper.json`, targeting
**Industrial at 16 threads in the quality suite**:

| Tokens | Meaning |
|---|---|
| CR, CA, BP, GR, tGB | Median selector-fit seconds |
| mCR, mCA, mBP, mGR, mGB | Median primary peak RSS GiB |
| rCR, rCA, rBP, rGR, rGB | Median selection recall |
| infoC, ruidoC | Median true/false selected counts, Bankai Classic native |
| infoG, ruidoG | Median true/false selected counts, Bankai Greedy native |
| razao | Median paired CA-fit-seconds / CR-fit-seconds |
| delta | Median paired 100×(recall CR − recall CA), percentage points |

BP means BorutaPy–LightGBM RF; GB means suite Python Greedy–BankaiRF.
All five measured seeds are required for final paper placeholders. Incomplete
reports are visibly provisional. Without `--provisional`, unavailable or
incomplete placeholder values stay null/NA. Smoke's one-thread results never
stand in for the specified 16-thread cells. TeX uses prefixed commands, e.g.
`\wmecaiCR`; the separate JSON preserves literal `{{CR}}` token syntax.

## Containers and AWS

```sh
make docker-smoke
# Or: make docker-smoke CONTAINER_ENGINE=podman
```

The amd64 Docker image pins Python 3.11 slim-bookworm by digest, includes
libgomp1, installs locked dependencies, runs as a non-root user, and records a
revision label. Building the development Rust extension needs network access
and a Rust toolchain; the runtime image excludes that toolchain.

AWS commands use the caller's ordinary credential chain. Supply an existing
result bucket, region, subnet IDs, and security group IDs. Instances need
outbound access to ECR, S3, SSM and CloudWatch (NAT or appropriate endpoints).
Subnets must support on-demand c7i.4xlarge capacity; no VPC or bucket is created.
Planning is offline and creates no resources:

```sh
AWS_ARGS='--region us-east-1 --bucket MY_BUCKET --experiment paper-v1 --subnets subnet-abc --security-groups sg-abc'
uv run bankai-aws plan $AWS_ARGS
uv run bankai-aws provision $AWS_ARGS
# Wait for CREATE_COMPLETE; inspect stack outputs for the immutable ECR repository.
# Authenticate Docker to ECR using aws ecr get-login-password, build and push an
# amd64 image with a unique tag, then resolve its sha256 digest from ECR.
uv run bankai-aws register $AWS_ARGS --image ACCOUNT.dkr.ecr.REGION.amazonaws.com/paper-v1@sha256:DIGEST
uv run bankai-aws launch $AWS_ARGS
uv run bankai-aws status $AWS_ARGS
uv run bankai-aws destroy $AWS_ARGS
```

Shell variable expansion in the example assumes a POSIX shell such as bash;
pass flags directly or use an array in zsh. `provision` creates an idle fleet
(minimum/desired zero, maximum one); it does not start EC2 instances. Only
`us-east-1` is permitted for provisioning and launch. The stack contains ECS,
a capacity provider, roles, ECR, and logs. The current ECS-optimized x86_64 AMI
is resolved via the official SSM parameter.

`launch` now runs a single quality pilot on Industrial (use `--dataset` to
choose another dataset). Each task reserves 16,384 CPU units and 28 GiB, and
checks CPU affinity before measurement. The five-host paper launch is disabled
under the R$200 policy. The controller first reserves R$20 in a persistent S3
campaign ledger, then schedules and verifies an AWS-side shutdown one hour
from arming, before starting capacity. At shutdown, minimum, maximum and desired
capacity all become zero, terminating the instance without replacement even
when the controller computer is disconnected. See [BUDGET.md](BUDGET.md) for
limits, permissions, cost assumptions and recovery behavior.

The single-host barrier retains task ARN, EC2 ID, image digest and log location.
Teardown stops standalone tasks and deletes the stack; the result bucket is
retained. No AWS resources are provisioned by local tests or CI.
