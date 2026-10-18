"""Run a paired, process-isolated BorutaPy ExtraTrees baseline at a 40-round cap."""
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

import boto3
import psutil


def dataset(args):
    sys.path.insert(0, "/opt/bankai-benchmark/src")
    from bankai_benchmark.datasets import generate_dataset
    bundle = generate_dataset("industrial", args.seed, "full")
    return bundle.X_train, bundle.y_train, bundle.metadata


def worker(args):
    import numpy as np
    from boruta import BorutaPy
    from sklearn.ensemble import ExtraTreesClassifier

    X, y, metadata = dataset(args)
    data_hash = hashlib.sha256(X.tobytes() + y.tobytes()).hexdigest()
    model = ExtraTreesClassifier(n_estimators=args.trees, max_depth=6,
        max_features="sqrt", bootstrap=True, n_jobs=args.threads, random_state=args.seed)
    # BorutaPy's loop condition is ``_iter < max_iter`` and starts at 1,
    # so max_iter=41 is required to perform exactly 40 rounds.
    selector = BorutaPy(model, n_estimators=args.trees, perc=100, alpha=.05,
        two_step=True, max_iter=args.max_iter + 1, random_state=args.seed,
        early_stopping=args.early_stopping, n_iter_no_change=100)
    target = Path(args.worker_output)
    target.with_suffix(".ready").touch()
    while not target.with_suffix(".go").exists():
        time.sleep(.001)
    hwm_reset = False
    if sys.platform.startswith("linux"):
        try:
            Path("/proc/self/clear_refs").write_text("5")
            hwm_reset = True
        except OSError:
            pass
    start = time.perf_counter()
    selector.fit(X, y)
    elapsed = time.perf_counter() - start
    hwm = None
    if sys.platform.startswith("linux"):
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmHWM:"):
                hwm = int(line.split()[1]) * 1024
    result = dict(variant="borutapy_sklearn_et", protocol=args.experiment,
        mode="fixed-40" if not args.early_stopping else "capped-40",
        elapsed_seconds=elapsed, n_iter=len(selector.importance_history_) - 1,
        max_iter=args.max_iter, early_stopping=args.early_stopping,
        stop_reason="max_iter" if len(selector.importance_history_) - 1 >= args.max_iter else "BorutaPy_stop",
        dataset=metadata, data_sha256=data_hash, vmhwm_bytes=hwm,
        vmhwm_reset=hwm_reset, packages={name: importlib.metadata.version(name)
            for name in ("Boruta", "scikit-learn", "numpy", "scipy")},
        python_version=sys.version, support=selector.support_.tolist(),
        weak=selector.support_weak_.tolist(),
        ranking=selector.ranking_.tolist(),
        importances=np.where(np.isnan(selector.importance_history_), None,
            selector.importance_history_).tolist())
    target.write_text(json.dumps(result, allow_nan=False))
    target.with_suffix(".done").touch()


def run_one(python, args, repeat, mode):
    with tempfile.TemporaryDirectory(prefix="borutapy-max40-") as temporary:
        target = Path(temporary) / "result.json"
        command = [python, str(Path(__file__).resolve()), "--worker-output", str(target),
            "--seed", str(args.seed), "--threads", str(args.threads),
            "--trees", str(args.trees), "--repeats", "1", "--max-iter", str(args.max_iter)]
        if mode == "capped-40":
            command.append("--early-stopping")
        environment = os.environ.copy()
        for name in ("OMP_NUM_THREADS", "RAYON_NUM_THREADS"):
            environment[name] = str(args.threads)
        for name in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
            environment[name] = "1"
        with (Path(temporary) / "stderr.log").open("w+") as errors:
            process = subprocess.Popen(command, cwd=temporary, env=environment,
                stdout=errors, stderr=errors)
            monitored = psutil.Process(process.pid)
            peak = baseline = None
            deadline = time.monotonic() + args.timeout_seconds
            while process.poll() is None:
                if time.monotonic() > deadline:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                    raise TimeoutError("BorutaPy ExtraTrees pilot exceeded its process deadline")
                if target.with_suffix(".ready").exists() and baseline is None:
                    baseline = monitored.memory_info().rss
                    peak = baseline
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
        result.update(repeat=repeat, external_peak_rss_bytes=peak,
            baseline_rss_bytes=baseline, peak_rss_delta_bytes=peak - baseline,
            rss_scope="fit")
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bucket")
    parser.add_argument("--experiment", default="exact-session-a7-max40-v1")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--threads", type=int, default=16)
    parser.add_argument("--trees", type=int, default=100)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--max-iter", type=int, default=40)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--early-stopping", action="store_true")
    parser.add_argument("--worker-output")
    parser.add_argument("--smoke", action="store_true",
        help="Run a small local BorutaPy/ExtraTrees fit and exit")
    args = parser.parse_args()
    if args.worker_output:
        worker(args)
        return
    if args.smoke:
        import numpy as np
        from boruta import BorutaPy
        from sklearn.ensemble import ExtraTreesClassifier
        rng = np.random.RandomState(args.seed)
        X = rng.normal(size=(300, 24)).astype(np.float32)
        y = (X[:, 0] + X[:, 1] > 0).astype(np.uint8)
        model = ExtraTreesClassifier(n_estimators=8, max_depth=4,
            max_features="sqrt", bootstrap=True, n_jobs=1, random_state=args.seed)
        selector = BorutaPy(model, n_estimators=8, max_iter=3,
            random_state=args.seed, early_stopping=False)
        selector.fit(X, y)
        assert selector.ranking_.shape == (X.shape[1],)
        assert len(selector.importance_history_) - 1 <= 2
        print("BorutaPy ExtraTrees smoke fit passed")
        return
    if not args.bucket:
        parser.error("--bucket is required unless --smoke is selected")
    if args.max_iter > 40:
        parser.error("max-iter must not exceed the approved 40-round cap")
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    python = "/opt/candidate/bin/python"
    for mode in ("fixed-40", "capped-40"):
        results = [run_one(python, args, repeat, mode) for repeat in range(args.repeats)]
        payload = dict(protocol=args.experiment, experiment_kind=mode,
            host=dict(platform=platform.platform(), machine=platform.machine(), logical_cpus=os.cpu_count()),
            configuration=dict(seed=args.seed, threads=args.threads, trees=args.trees,
                max_iter=args.max_iter, repeats=args.repeats, dtype="float32"),
            dataset_hash_consistency=("passed" if len({r["data_sha256"] for r in results}) == 1 else "failed"),
            summary={"elapsed_seconds": statistics.median(r["elapsed_seconds"] for r in results),
                "external_peak_rss_bytes": statistics.median(r["external_peak_rss_bytes"] for r in results)},
            results=results)
        key = f"{args.experiment}/pilot/{run_id}/industrial-seed{args.seed}-t{args.threads}-borutapy-{mode}.json"
        data = json.dumps(payload, allow_nan=False).encode()
        digest = hashlib.sha256(data).hexdigest()
        boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-east-1")).put_object(
            Bucket=args.bucket, Key=key, Body=data, ContentType="application/json",
            Metadata={"sha256": digest})
        print(json.dumps({"s3_uri": f"s3://{args.bucket}/{key}", "sha256": digest,
            "bytes": len(data), "median_seconds": payload["summary"]["elapsed_seconds"],
            "median_peak_rss_bytes": payload["summary"]["external_peak_rss_bytes"]}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
