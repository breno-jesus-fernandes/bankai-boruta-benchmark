"""Process-isolated Industrial comparison: Bankai exact, Bankai binned and BorutaPy.

Every fit runs in a fresh worker process that generates the dataset, signals
readiness and waits; the parent then samples external RSS until the fit ends.
All methods share the nominal configuration (100 trees, depth 6, sqrt features,
bootstrap, perc=100, alpha=0.05, two_step, at most 40 rounds, natural stop).
Methods are interleaved within each repeat, and one JSON per seed is uploaded.
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

METHODS = ("bankai_exact", "bankai_binned", "borutapy")
BENCHMARK_SRC = os.environ.get("BANKAI_BENCHMARK_SRC", "/opt/bankai-benchmark/src")


def dataset(seed, rows=None):
    sys.path.insert(0, BENCHMARK_SRC)
    from bankai_benchmark.datasets import generate_dataset
    bundle = generate_dataset("industrial", seed, "full")
    X, y = bundle.X_train, bundle.y_train
    if rows:
        X, y = X[:rows], y[:rows]
    return X, y, [int(i) for i in bundle.relevant_features]


def selector(method, seed, threads, trees, max_iter):
    # BorutaPy's loop starts at 1 with ``_iter < max_iter``; max_iter + 1 gives
    # at most ``max_iter`` rounds. BankaiBoruta mirrors that contract.
    common = dict(n_estimators=trees, perc=100, alpha=.05, two_step=True,
        max_iter=max_iter + 1, random_state=seed)
    if method == "borutapy":
        from boruta import BorutaPy
        from sklearn.ensemble import ExtraTreesClassifier
        model = ExtraTreesClassifier(n_estimators=trees, max_depth=6, max_features="sqrt",
            bootstrap=True, n_jobs=threads, random_state=seed)
        return BorutaPy(model, early_stopping=False, **common)
    from bankai_boruta import BankaiBoruta
    from bankai_random_forest import BankaiRandomForestClassifier
    binned = method == "bankai_binned"
    model = BankaiRandomForestClassifier(n_estimators=trees, max_depth=6, max_features="sqrt",
        bootstrap=True, n_jobs=threads, random_state=seed, extra_trees=True,
        extra_trees_backend="binned" if binned else "exact", max_bins=63 if binned else None)
    return BankaiBoruta(estimator=model, **common)


def worker(args):
    import numpy as np
    X, y, relevant = dataset(args.seed, args.rows)
    data_hash = hashlib.sha256(np.ascontiguousarray(X).tobytes() + y.tobytes()).hexdigest()
    model = selector(args.method, args.seed, args.threads, args.trees, args.max_iter)
    target = Path(args.worker_output)
    target.with_suffix(".ready").touch()
    while not target.with_suffix(".go").exists():
        time.sleep(.001)
    start = time.perf_counter()
    model.fit(X, y)
    elapsed = time.perf_counter() - start
    target.with_suffix(".done").touch()
    if args.method == "borutapy":
        rounds = len(model.importance_history_) - 1
        mode = "python"
    else:
        rounds = int(model.n_iter_)
        mode = model.diagnostics_.get("storage_mode")
    relevant = set(relevant)
    support = np.flatnonzero(model.support_).tolist()
    result = dict(method=args.method, storage_mode=mode, seed=args.seed,
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


def run_one(args, method, seed, repeat):
    with tempfile.TemporaryDirectory(prefix="native-shadow-") as temporary:
        target = Path(temporary) / "result.json"
        command = [sys.executable, str(Path(__file__).resolve()), "--worker-output", str(target),
            "--method", method, "--seed", str(seed), "--threads", str(args.threads),
            "--trees", str(args.trees), "--max-iter", str(args.max_iter)]
        if args.rows:
            command += ["--rows", str(args.rows)]
        environment = os.environ.copy()
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
                    raise TimeoutError(f"{method} seed {seed} exceeded its process deadline")
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
    parser.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44, 45, 46])
    parser.add_argument("--methods", nargs="+", default=list(METHODS), choices=METHODS)
    parser.add_argument("--threads", type=int, default=16)
    parser.add_argument("--trees", type=int, default=100)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--max-iter", type=int, default=40)
    parser.add_argument("--rows", type=int, help="Truncate the training split (smoke only)")
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
    for seed in args.seeds:
        results = []
        for repeat in range(args.repeats):
            # Rotate the method order so no method always runs first or last.
            order = args.methods[repeat % len(args.methods):] + args.methods[:repeat % len(args.methods)]
            for method in order:
                result = run_one(args, method, seed, repeat)
                results.append(result)
                print(json.dumps({k: result[k] for k in ("method", "seed", "repeat", "rounds",
                    "elapsed_seconds", "peak_rss_delta_bytes", "support")}), flush=True)
        payload = dict(protocol=args.experiment, run_id=run_id, host=host,
            configuration=dict(seed=seed, threads=args.threads, trees=args.trees, max_iter=args.max_iter,
                repeats=args.repeats, rows=args.rows, dtype="float32", depth=6, max_features="sqrt",
                bootstrap=True, perc=100, alpha=.05, two_step=True),
            dataset_hash_consistency="passed" if len({r["data_sha256"] for r in results}) == 1 else "failed",
            summary=summarize(results), results=results)
        data = json.dumps(payload, allow_nan=False, indent=1).encode()
        name = f"industrial-seed{seed}-t{args.threads}.json"
        if args.output_dir:
            Path(args.output_dir).mkdir(parents=True, exist_ok=True)
            (Path(args.output_dir) / name).write_bytes(data)
        if s3:
            key = f"{args.experiment}/pilot/{run_id}/{name}"
            digest = hashlib.sha256(data).hexdigest()
            s3.put_object(Bucket=args.bucket, Key=key, Body=data, ContentType="application/json",
                Metadata={"sha256": digest})
            print(json.dumps({"s3_uri": f"s3://{args.bucket}/{key}", "sha256": digest, "bytes": len(data)}), flush=True)
    print(json.dumps({"status": "success", "run_id": run_id, "seeds": args.seeds}), flush=True)


if __name__ == "__main__":
    main()
