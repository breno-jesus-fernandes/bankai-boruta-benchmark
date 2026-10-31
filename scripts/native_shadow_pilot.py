"""Process-isolated comparison of Bankai (exact, binned) and BorutaPy (ExtraTrees, LightGBM RF).

Every fit runs in a fresh worker process that generates the dataset, signals
readiness and waits; the parent then samples external RSS until the fit ends.
All methods share the profile's nominal configuration (trees, depth, feature
fraction; 63 bins for the binned backend) plus bootstrap, perc=100, alpha=0.05,
two_step and at most 40 rounds with the natural stop.
Methods are interleaved within each repeat, and one JSON per seed is uploaded.
The real dataset ``cicids2017`` (scripts/prepare_cicids2017.py) uses the
Cybersecurity profile's configuration; it has no known relevant features, so
each seed also records the downstream ROC AUC on its held-out split.
``--scale 2`` doubles the synthetic profiles' rows and columns (extra columns
are noise); each seed's data is generated once and loaded whole by every worker.
"""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

import psutil

METHODS = ("bankai_exact", "bankai_binned", "borutapy", "borutapy_lgbm")
# Absolute, because workers run from their own temporary directory.
BENCHMARK_SRC = os.path.abspath(os.environ.get("BANKAI_BENCHMARK_SRC", "/opt/bankai-benchmark/src"))
REAL_DATA = os.environ.get("BANKAI_CICIDS2017_DIR", "/opt/data/cicids2017")
DATASETS = ("industrial", "credito", "bioinformatica", "ciberseguranca", "cicids2017")


def mode(name, scale):
    return "full2x" if scale == 2 and name != "cicids2017" else "full"


def config(name, scale=1):
    sys.path.insert(0, BENCHMARK_SRC)
    from bankai_benchmark.config import profile
    return profile("ciberseguranca" if name == "cicids2017" else name, mode(name, scale))


def real_split(split):
    import numpy as np
    rows, cols = json.loads((Path(REAL_DATA) / "manifest.json").read_text())[split]["shape"]
    X = np.fromfile(Path(REAL_DATA) / f"{split}-X.f32", dtype="<f4").reshape(rows, cols)
    return X, np.fromfile(Path(REAL_DATA) / f"{split}-y.i32", dtype="<i4")


def dataset(name, seed, rows=None, scale=1, cache=None):
    if name == "cicids2017":
        X, y = real_split("train")
        return (X[:rows], y[:rows], []) if rows else (X, y, [])
    if cache:
        import numpy as np
        # Read whole arrays, not memory maps, so the data is resident before the RSS baseline.
        X, y, relevant = (np.load(Path(cache) / f"{part}.npy") for part in ("X_train", "y_train", "relevant_features"))
        return (X[:rows], y[:rows], [int(i) for i in relevant]) if rows else (X, y, [int(i) for i in relevant])
    sys.path.insert(0, BENCHMARK_SRC)
    from bankai_benchmark.datasets import generate_dataset
    bundle = generate_dataset(name, seed, mode(name, scale))
    X, y = bundle.X_train, bundle.y_train
    if rows:
        X, y = X[:rows], y[:rows]
    return X, y, [int(i) for i in bundle.relevant_features]


def selector(method, seed, threads, cfg, max_iter):
    # BorutaPy's loop starts at 1 with ``_iter < max_iter``; max_iter + 1 gives
    # at most ``max_iter`` rounds. BankaiBoruta mirrors that contract.
    trees = cfg.trees
    common = dict(n_estimators=trees, perc=100, alpha=.05, two_step=True,
        max_iter=max_iter + 1, random_state=seed)
    if method == "borutapy_lgbm":
        # The suite's LightGBM random-forest backend, unchanged: 63 bins,
        # row subsample 0.8 and per-tree columns at sqrt of the augmented width.
        from types import SimpleNamespace
        from boruta import BorutaPy
        from bankai_benchmark.competitors import estimator
        trial = SimpleNamespace(dataset=cfg.dataset, mode="full", threads=threads, seed=seed)
        return BorutaPy(estimator(trial, "lightgbm"), early_stopping=False, **common)
    if method == "borutapy":
        from boruta import BorutaPy
        from sklearn.ensemble import ExtraTreesClassifier
        model = ExtraTreesClassifier(n_estimators=trees, max_depth=cfg.depth, max_features=cfg.max_features,
            bootstrap=True, n_jobs=threads, random_state=seed)
        return BorutaPy(model, early_stopping=False, **common)
    from bankai_boruta import BankaiBoruta
    from bankai_random_forest import BankaiRandomForestClassifier
    binned = method == "bankai_binned"
    model = BankaiRandomForestClassifier(n_estimators=trees, max_depth=cfg.depth, max_features=cfg.max_features,
        bootstrap=True, n_jobs=threads, random_state=seed, extra_trees=True,
        extra_trees_backend="binned" if binned else "exact", max_bins=cfg.bins if binned else None)
    return BankaiBoruta(estimator=model, **common)


def worker(args):
    import numpy as np
    X, y, relevant = dataset(args.dataset, args.seed, args.rows, args.scale, args.cache)
    data_hash = hashlib.sha256(np.ascontiguousarray(X).tobytes() + y.tobytes()).hexdigest()
    model = selector(args.method, args.seed, args.threads, config(args.dataset, args.scale), args.max_iter)
    target = Path(args.worker_output)
    target.with_suffix(".ready").touch()
    while not target.with_suffix(".go").exists():
        time.sleep(.001)
    start = time.perf_counter()
    model.fit(X, y)
    elapsed = time.perf_counter() - start
    target.with_suffix(".done").touch()
    if args.method.startswith("borutapy"):
        rounds = len(model.importance_history_) - 1
        storage = "python"
    else:
        rounds = int(model.n_iter_)
        storage = model.diagnostics_.get("storage_mode")
    relevant = set(relevant)
    support = np.flatnonzero(model.support_).tolist()
    result = dict(dataset=args.dataset, method=args.method, storage_mode=storage, seed=args.seed, scale=args.scale,
        elapsed_seconds=elapsed, rounds=rounds, max_iter=args.max_iter,
        support=support, tentative=np.flatnonzero(model.support_weak_).tolist(),
        data_sha256=data_hash, n_rows=int(X.shape[0]), n_features=int(X.shape[1]),
        packages={name: importlib.metadata.version(name) for name in (
            "bankai-boruta", "bankai-random-forest", "Boruta", "scikit-learn", "numpy")},
        python_version=sys.version)
    if relevant:
        hits = len(relevant.intersection(support))
        result.update(precision=hits / len(support) if support else None,
            recall=hits / len(relevant), relevant=sorted(relevant))
    target.write_text(json.dumps(result, allow_nan=False))


def run_one(args, name, method, seed, repeat, cache=None):
    with tempfile.TemporaryDirectory(prefix="native-shadow-") as temporary:
        target = Path(temporary) / "result.json"
        command = [sys.executable, str(Path(__file__).resolve()), "--worker-output", str(target),
            "--dataset", name, "--method", method, "--seed", str(seed),
            "--threads", str(args.threads), "--max-iter", str(args.max_iter), "--scale", str(args.scale)]
        if cache:
            command += ["--cache", str(cache)]
        if args.rows:
            command += ["--rows", str(args.rows)]
        environment = os.environ.copy()
        environment["BANKAI_BENCHMARK_SRC"] = BENCHMARK_SRC
        for name in ("OMP_NUM_THREADS", "RAYON_NUM_THREADS"):
            environment[name] = str(args.threads)
        for name in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
            environment[name] = "1"
        with (Path(temporary) / "stderr.log").open("w+") as errors:
            process = subprocess.Popen(command, cwd=temporary, env=environment, stdout=errors, stderr=errors)
            monitored = psutil.Process(process.pid)
            peak = baseline = None
            deadline = time.monotonic() + args.timeout_seconds
            while process.poll() is None:
                if time.monotonic() > deadline:
                    process.kill()
                    process.wait()
                    raise TimeoutError(f"{name} {method} seed {seed} exceeded its process deadline")
                if baseline is None and target.with_suffix(".ready").exists():
                    baseline = peak = monitored.memory_info().rss
                    target.with_suffix(".go").touch()
                if baseline is not None and not target.with_suffix(".done").exists():
                    try:
                        peak = max(peak, monitored.memory_info().rss)
                    except psutil.NoSuchProcess:
                        pass
                time.sleep(.005)
            if process.returncode:
                errors.seek(0)
                raise RuntimeError(errors.read())
        result = json.loads(target.read_text())
        result.update(repeat=repeat, baseline_rss_bytes=baseline, external_peak_rss_bytes=peak,
            peak_rss_delta_bytes=peak - baseline, rss_scope="fit")
        return result


def held_out_auc(results, seed, threads, rows, cache=None):
    # The suite's downstream ExtraTrees on each distinct confirmed set, on all
    # features and (synthetic data) on the relevant ones, after every timed fit of the seed.
    from types import SimpleNamespace
    import numpy as np
    sys.path.insert(0, BENCHMARK_SRC)
    from bankai_benchmark.metrics import downstream
    if cache is None:
        X_train, y_train = real_split("train")
        X_test, y_test = real_split("test")
        relevant = None
    else:
        X_train, y_train, X_test, y_test, relevant = (np.load(Path(cache) / f"{name}.npy", allow_pickle=False)
            for name in ("X_train", "y_train", "X_test", "y_test", "relevant_features"))
    if rows:
        X_train, y_train, X_test, y_test = X_train[:rows], y_train[:rows], X_test[:rows], y_test[:rows]
    bundle = SimpleNamespace(X_train=X_train, y_train=y_train, X_test=X_test, y_test=y_test)
    sets = {"all": list(range(X_train.shape[1]))}
    if relevant is not None:
        sets["relevant"] = sorted(int(i) for i in relevant)
    for result in results:
        sets.setdefault(",".join(map(str, result["support"])), result["support"])
    scores = {label: downstream(bundle, np.asarray(indices, dtype=int), seed, threads)["roc_auc"]
              for label, indices in sets.items()}
    auc = dict(all=scores["all"], by_method={r["method"]: scores[",".join(map(str, r["support"]))] for r in results})
    if relevant is not None:
        auc["relevant"] = scores["relevant"]
    return auc


def summarize(results):
    summary = {}
    for method in METHODS:
        rows = [r for r in results if r["method"] == method]
        if rows:
            summary[method] = dict(
                median_seconds=statistics.median(r["elapsed_seconds"] for r in rows),
                median_peak_rss_delta_bytes=statistics.median(r["peak_rss_delta_bytes"] for r in rows),
                rounds=[r["rounds"] for r in rows], supports=sorted({tuple(r["support"]) for r in rows}))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bucket")
    parser.add_argument("--experiment", default="native-shadow-max40-v1")
    parser.add_argument("--datasets", nargs="+", default=["industrial"], choices=DATASETS)
    parser.add_argument("--dataset", default="industrial")
    parser.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44, 45, 46])
    parser.add_argument("--methods", nargs="+", default=list(METHODS), choices=METHODS)
    parser.add_argument("--threads", type=int, default=16)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--max-iter", type=int, default=40)
    parser.add_argument("--rows", type=int, help="Truncate the training split (smoke only)")
    parser.add_argument("--scale", type=int, choices=(1, 2), default=1, help="2 doubles synthetic rows and columns")
    parser.add_argument("--cache", help=argparse.SUPPRESS)
    parser.add_argument("--auc", action="store_true", help="Also record the downstream AUC of synthetic data (CIC-IDS2017 always does)")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--output-dir", help="Also write each seed JSON locally")
    parser.add_argument("--worker-output")
    parser.add_argument("--method", choices=METHODS)
    parser.add_argument("--seed", type=int)
    args = parser.parse_args()
    if args.worker_output:
        worker(args)
        return
    if args.max_iter > 40:
        parser.error("max-iter must not exceed the approved 40-round cap")
    s3 = None
    if args.bucket:
        import boto3
        s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    host = dict(platform=platform.platform(), machine=platform.machine(), logical_cpus=os.cpu_count())
    for name, seed in [(name, seed) for name in args.datasets for seed in args.seeds]:
        cfg = config(name, args.scale)
        results = []
        cache_root = tempfile.TemporaryDirectory(prefix="native-shadow-data-")
        cache = None
        if name != "cicids2017":
            # Generate once per seed outside every worker; the same bytes reach every fit.
            sys.path.insert(0, BENCHMARK_SRC)
            from bankai_benchmark.datasets import cache_dataset
            cache = cache_dataset(cache_root.name, name, seed, mode(name, args.scale))
        for repeat in range(args.repeats):
            # Rotate the method order so no method always runs first or last.
            order = args.methods[repeat % len(args.methods):] + args.methods[:repeat % len(args.methods)]
            for method in order:
                result = run_one(args, name, method, seed, repeat, cache)
                results.append(result)
                print(json.dumps({k: result[k] for k in ("dataset", "method", "seed", "repeat", "rounds",
                    "elapsed_seconds", "peak_rss_delta_bytes", "support")}), flush=True)
        # Untimed: after every fit of the seed, on the same bytes.
        auc = held_out_auc(results, seed, args.threads, args.rows, cache) if name == "cicids2017" or args.auc else None
        cache_root.cleanup()
        payload = dict(protocol=args.experiment, run_id=run_id, host=host,
            configuration=dict(dataset=name, seed=seed, threads=args.threads, scale=args.scale, profile_mode=mode(name, args.scale),
                n_rows=results[0]["n_rows"], n_features=results[0]["n_features"], trees=cfg.trees, max_iter=args.max_iter,
                repeats=args.repeats, rows=args.rows, dtype="float32", depth=cfg.depth, max_features=cfg.max_features, bins=cfg.bins,
                bootstrap=True, perc=100, alpha=.05, two_step=True),
            dataset_hash_consistency="passed" if len({r["data_sha256"] for r in results}) == 1 else "failed",
            summary=summarize(results), results=results)
        if auc:
            payload["auc"] = auc
        data = json.dumps(payload, allow_nan=False, indent=1).encode()
        artifact = f"{name}-seed{seed}-t{args.threads}{'-x2' if args.scale == 2 else ''}.json"
        if args.output_dir:
            Path(args.output_dir).mkdir(parents=True, exist_ok=True)
            (Path(args.output_dir) / artifact).write_bytes(data)
        if s3:
            key = f"{args.experiment}/pilot/{run_id}/{artifact}"
            digest = hashlib.sha256(data).hexdigest()
            s3.put_object(Bucket=args.bucket, Key=key, Body=data, ContentType="application/json",
                Metadata={"sha256": digest})
            print(json.dumps({"s3_uri": f"s3://{args.bucket}/{key}", "sha256": digest, "bytes": len(data)}), flush=True)
    print(json.dumps({"status": "success", "run_id": run_id, "datasets": args.datasets, "seeds": args.seeds}), flush=True)


if __name__ == "__main__":
    main()
