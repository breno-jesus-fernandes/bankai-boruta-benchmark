# Native-control development artifact

The standalone patch applies to the exact revision in `base-revision.txt`.
It keeps the public constructors unchanged. `n_jobs` resolves with the pinned
forest's own `_resolve_n_jobs`; `max_features` resolves on each augmented width
with its own `_resolve_max_features`. The Rust core receives both explicit
values for preparation and training. No adapter fallback is allowed in native
benchmark configurations.

To rebuild in an isolated checkout:

```sh
git clone https://github.com/breno-jesus-fernandes/bankai-boruta.git /tmp/boruta-controls
cd /tmp/boruta-controls
git checkout "$(cat /path/to/benchmark/upstream/base-revision.txt)"
git apply /path/to/benchmark/upstream/native-controls.patch
uvx --from 'maturin==1.15.0' maturin build --release --out /path/to/benchmark/artifacts
uvx --from 'maturin==1.15.0' maturin sdist --out /path/to/benchmark/artifacts
```

The patch assigns `0.1.0a3+benchmark.1` only to the isolated development artifact.
The wheel/source checksum list is `artifacts/SHA256SUMS`. `test_native_controls.py`
is the portable upstream test contribution: positive 1/4 thread counts,
sqrt/fraction/integer/None/log2 feature sampling, Classic/Greedy paths,
zero native shadow-copy bytes, positive adapter copy bytes, and deterministic
importance-history/selection parity. The benchmark's tests also exercise path
assertions on all configurations. Public upstream publication and release are
still required before full paper campaigns. This patch has not been pushed to
or released from the upstream repository by the benchmark task.
