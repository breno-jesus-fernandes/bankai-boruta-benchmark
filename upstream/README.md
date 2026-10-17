# Historical native-control development artifact

The correction is now published in `bankai-boruta==0.1.0a4`. Normal installs
use PyPI; the following records the original development workflow.

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
The original artifact hashes remain in `artifacts/build-provenance.json` and
Git history; development binaries were removed after migrating to PyPI.
`test_native_controls.py` records the original upstream parity tests. The suite
also checks native/adapter parity and path diagnostics in `tests/test_native.py`.
