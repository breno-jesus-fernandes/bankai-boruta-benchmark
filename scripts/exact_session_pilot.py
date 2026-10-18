"""Run one bounded Industrial a6/a15 versus a7/a16 pilot and upload each result."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from datetime import datetime, timezone

import boto3

COMPARE = "/opt/compare_exact_session.py"
REFERENCE = "/opt/reference/bin/python"
CANDIDATE = "/opt/candidate/bin/python"
BENCHMARK_ROOT = "/opt/bankai-benchmark"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--threads", type=int, default=16)
    parser.add_argument("--trees", type=int, default=100)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=int, default=2400)
    args = parser.parse_args()

    region = os.environ.get("AWS_REGION", "us-east-1")
    s3 = boto3.client("s3", region_name=region)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    configurations = (("fixed-5", 5), ("complete", 0))
    with tempfile.TemporaryDirectory(prefix="exact-session-a7-") as temporary:
        for label, rounds in configurations:
            output = Path(temporary) / f"industrial-seed{args.seed}-t{args.threads}-{label}.json"
            command = [CANDIDATE, COMPARE,
                "--reference-python", REFERENCE,
                "--candidate-python", CANDIDATE,
                "--benchmark-root", BENCHMARK_ROOT,
                "--trees", str(args.trees), "--threads", str(args.threads),
                "--seed", str(args.seed), "--fixed-rounds", str(rounds),
                "--max-iter", "120", "--repeats", str(args.repeats),
                "--timeout-seconds", str(args.timeout_seconds),
                "--output", str(output)]
            subprocess.run(command, check=True, timeout=args.timeout_seconds + 120)
            payload = output.read_bytes()
            digest = hashlib.sha256(payload).hexdigest()
            key = f"{args.experiment}/pilot/{run_id}/{output.name}"
            s3.put_object(Bucket=args.bucket, Key=key, Body=payload,
                ContentType="application/json", Metadata={"sha256": digest})
            print(json.dumps({"s3_uri": f"s3://{args.bucket}/{key}",
                "sha256": digest, "bytes": len(payload)}, sort_keys=True), flush=True)
    print(json.dumps({"status": "success", "experiment": args.experiment,
        "run_id": run_id, "seed": args.seed, "threads": args.threads,
        "trees": args.trees, "repeats": args.repeats}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
