import argparse
from dataclasses import asdict, replace
import importlib.metadata
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from .config import atomic_json, digest, trial_grid, PROFILES, PROTOCOL, GENERATOR_VERSION, MACHINE, COMPETITORS, source_hash


def execute(command, timeout):
    process = subprocess.Popen(command, start_new_session=True)
    try:
        return process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
        raise


def upload(client, path, bucket, key, attempts=4):
    from botocore.exceptions import ClientError, EndpointConnectionError, ConnectionClosedError
    for attempt in range(attempts):
        try:
            client.upload_file(str(path), bucket, key)
            return
        except (ClientError, EndpointConnectionError, ConnectionClosedError) as exc:
            code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
            if isinstance(exc, ClientError) and code not in ("SlowDown", "RequestTimeout", "InternalError", "ServiceUnavailable", "500", "503"):
                raise
            if attempt == attempts-1:
                raise
            time.sleep(2**attempt)


def manifest_for(trials):
    data = dict(protocol=PROTOCOL, generator_version=GENERATOR_VERSION, machine=MACHINE, competitors=list(COMPETITORS), schema_version=1, experiment_id=trials[0].experiment_id, mode=trials[0].mode, suite=trials[0].suite,
        source_hash=source_hash(), package_versions={name: importlib.metadata.version(name) for name in
            ("bankai-boruta", "bankai-random-forest", "Boruta", "lightgbm", "numpy", "scipy", "scikit-learn")},
        trials=[dict(**asdict(t), configuration_hash=t.configuration_hash, key=t.key) for t in trials])
    data["configuration_hash"] = digest(data)
    return data


def ensure_manifest(path, expected):
    if path.exists():
        if json.loads(path.read_text()) != expected:
            raise ValueError("Incompatible manifest; choose a new experiment ID")
    else:
        atomic_json(path, expected)


def restore(client, bucket, key, path):
    from botocore.exceptions import ClientError
    if path.exists():
        return
    try:
        content = client.get_object(Bucket=bucket, Key=key)["Body"].read()
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("NoSuchKey", "404"):
            return
        raise
    atomic_json(path, json.loads(content))


def runnable(path, trial, overwrite=False, retry_failed=False):
    if not path.exists():
        return True
    result = json.loads(path.read_text())
    if result["configuration_hash"] != trial.configuration_hash:
        raise ValueError(f"Configuration mismatch: {path}")
    return overwrite or (retry_failed and result["status"] != "success")


def run_trial(trial, cache, path, timeout):
    from .worker_single_run import base_result
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    command = [sys.executable, "-m", "bankai_benchmark.worker_single_run", "--trial", json.dumps(asdict(trial)),
               "--cache", str(cache), "--output", str(path)]
    try:
        code = execute(command, timeout)
        if not path.exists():
            result = base_result(trial)
            result.update(status="resource_failure" if code == -signal.SIGKILL else "execution_failure", error=dict(returncode=code))
            atomic_json(path, result)
    except subprocess.TimeoutExpired:
        result = base_result(trial)
        result.update(status="timeout", error=dict(timeout_seconds=timeout))
        atomic_json(path, result)
    return json.loads(path.read_text())


def require_public_release():
    version = importlib.metadata.version("bankai-boruta")
    # Replacing the source pin and filling the attestation is a deliberate release step.
    path = Path(__file__).with_name("release-verification.json")
    verification = json.loads(path.read_text())
    if "+" in version or verification.get("verified_version") != version or not verification.get("native_control_tests_passed"):
        raise RuntimeError("Full paper runs require a verified public Bankai release; current artifact is smoke-only")


def run_campaign(args):
    from .datasets import cache_dataset
    if args.mode == "full":
        require_public_release()
    experiment = f"{args.experiment}-{args.suite}"
    all_trials = trial_grid(experiment, args.mode, args.suite)
    trials = [t for t in all_trials if args.dataset is None or t.dataset == args.dataset]
    if not trials:
        raise ValueError("No trials match this dataset and suite")
    root = Path(args.results); manifest_path = root/experiment/"manifest.json"
    client = None
    if args.bucket:
        import boto3
        client = boto3.client("s3", region_name=args.region)
        restore(client, args.bucket, f"{experiment}/manifest.json", manifest_path)
    expected_manifest = manifest_for(all_trials)
    ensure_manifest(manifest_path, expected_manifest)
    if client:
        # Concurrent ECS shards use the same immutable document.
        from botocore.exceptions import ClientError
        try:
            client.put_object(Bucket=args.bucket, Key=f"{experiment}/manifest.json", Body=manifest_path.read_bytes(), IfNoneMatch="*")
        except ClientError as exc:
            if exc.response["Error"]["Code"] not in ("PreconditionFailed", "412"):
                raise
            remote = json.loads(client.get_object(Bucket=args.bucket, Key=f"{experiment}/manifest.json")["Body"].read())
            if remote != expected_manifest:
                raise ValueError("Incompatible remote manifest")
    failed = False; warmed = set()
    warmups = {"smoke": 0, "smoke-matrix": 1, "full": 2}[args.mode]
    for trial in trials:
        path = root/trial.key
        if client:
            restore(client, args.bucket, trial.key, path)
        if not runnable(path, trial, args.overwrite, args.retry_failed):
            print(f"skip {trial.dataset}/{trial.trial_id}", flush=True)
            result = json.loads(path.read_text())
        else:
            cache = cache_dataset(args.cache, trial.dataset, trial.seed, trial.mode)
            group = (trial.dataset, trial.competitor, trial.threads)
            if group not in warmed:
                for index in range(warmups):
                    warm = replace(trial, seed=900001+index, warmup=True)
                    warm_cache = cache_dataset(args.cache, warm.dataset, warm.seed, warm.mode)
                    warm_output = root/experiment/"warmups"/trial.dataset/f"{warm.trial_id}.json"
                    if run_trial(warm, warm_cache, warm_output, args.timeout)["status"] != "success":
                        raise RuntimeError(f"Warmup failed: {warm_output}")
                warmed.add(group)
            print(f"run {trial.dataset}/{trial.trial_id}", flush=True)
            result = run_trial(trial, cache, path, args.timeout)
        failed |= result["status"] != "success"
        if client:
            try:
                upload(client, path, args.bucket, trial.key)
            except Exception as exc:
                print(f"Upload failed; local result retained: {exc}", file=sys.stderr); failed = True
        # References use their own OS process and are independent of selector memory.
        reference = root/experiment/"references"/trial.dataset/f"seed{trial.seed}.json"
        if client:
            restore(client, args.bucket, f"{experiment}/references/{trial.dataset}/seed{trial.seed}.json", reference)
        if not reference.exists():
            cache = cache_dataset(args.cache, trial.dataset, trial.seed, trial.mode)
            reference.parent.mkdir(parents=True, exist_ok=True)
            try:
                code = execute([sys.executable, "-m", "bankai_benchmark.worker_single_run", "--trial", json.dumps(asdict(trial)),
                    "--cache", str(cache), "--output", str(reference), "--reference"], args.timeout)
                if code:
                    failed = True
            except subprocess.TimeoutExpired:
                failed = True
        if client and reference.exists():
            try:
                upload(client, reference, args.bucket, f"{experiment}/references/{trial.dataset}/seed{trial.seed}.json")
            except Exception as exc:
                print(f"Reference upload failed: {exc}", file=sys.stderr); failed = True
    return int(failed)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("smoke", "smoke-matrix", "full"))
    parser.add_argument("--suite", choices=("quality", "scaling"), default="quality")
    parser.add_argument("--dataset", choices=list(PROFILES)); parser.add_argument("--experiment", default="local")
    parser.add_argument("--results", default="results"); parser.add_argument("--cache", default=".cache/datasets")
    parser.add_argument("--bucket"); parser.add_argument("--region"); parser.add_argument("--timeout", type=float, default=2400)
    parser.add_argument("--overwrite", action="store_true"); parser.add_argument("--retry-failed", action="store_true")
    raise SystemExit(run_campaign(parser.parse_args()))


if __name__ == "__main__":
    main()
