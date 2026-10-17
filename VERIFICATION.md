# Verification record

The implementation and verification artifacts are committed to the private
[GitHub repository](https://github.com/breno-jesus-fernandes/bankai-boruta-benchmark).

- `uv run pytest -q`: **49 passed**, including all four generators, seven
  configurations, 20 native/adapter parity cases, hand-computed metrics,
  fresh-process measurement, process-group timeout cleanup, resume/configuration
  checks, mocked S3 retries/recovery, every paper placeholder, paired scaling,
  and mocked five-host AWS placement.
- Final fresh local quick smoke: **7/7 successes in 11.606 seconds**, measured
  end-to-end including process startup and downstream evaluation. Reference
  machine: Apple M1, eight logical CPUs, 8 GiB RAM, macOS, Python 3.11; one
  selector thread. Timing is a single reference observation, not a runtime
  guarantee or a full benchmark claim. See `verification/smoke-timing.json`.
- Repeat smoke: all seven successes skipped; file hashes **and modification
  times** unchanged, verified by `scripts/verify_smoke.py`.
- Aggregation: inspected the CSV, Markdown and TeX outputs. The main table has
  six configurations including Python Greedy–BankaiRF; the additional table
  contains Python Greedy–LightGBM. All five-seed, 16-thread paper placeholders
  remain unavailable for smoke. A snapshot is in `verification/smoke-report`.
- Both development artifact SHA-256 checksums verified. The macOS wheel's Python
  selector source was compared byte-for-byte with the isolated patched source.
- AWS planning executed offline and saved to `verification/aws-plan.json`.
  No AWS resources or full benchmark campaign were created.

Native Linux amd64 acceptance passed in
[GitHub Actions run 39052587675](https://github.com/breno-jesus-fernandes/bankai-boruta-benchmark/actions/runs/39052587675):
unit/integration tests, quick smoke, aggregation, skip-on-resume, container
build, and container assertions for all seven trials, Linux VmHWM, one-CPU
affinity and required native paths. The latest commit is checked again by CI;
its acceptance summary is stored alongside this record when complete.

An additional local Linux amd64 attempt through Podman/QEMU on Apple Silicon
crashed in the emulator while executing `uv`. It does not count as acceptance;
the successful native x86_64 CI jobs provide that evidence. The temporary VM
was used only for verification, not measurements for the paper.

## Remaining external acceptance conditions

The public Bankai release containing the native-control correction does not
exist in the benchmark pin. The current `0.1.0a3+benchmark.1` artifacts are
explicitly development-only. The isolated patch, source revision, tests,
archive, wheel and checksums are preserved; no upstream public release is
claimed. Full paper commands are gated pending release verification and a
new public-version lockfile.

Review the documented frozen generator/default choices against the intended
paper protocol before paper execution: the handoff omitted some numerical
signal/noise/prevalence and downstream parameters. The README identifies every
such choice. Full AWS results must come from a real provisioned workload;
smoke outputs do not populate final paper values.
