"""Compute native-shadow downstream AUC on AWS when the data is too large for a laptop.

Uploads native_shadow_auc.py, the artifacts of ARTIFACT_DIR and any existing
auc.json under the experiment's auc/<stamp>/ prefix, then runs the published
native-shadow image once: the container downloads them, runs the AUC script
with the image's benchmark sources (so 2x artifacts regenerate their 2x data)
and uploads the updated auc.json, which is copied back into ARTIFACT_DIR.
The AUC is deterministic given the seed and the platform: the thread count does
not change it, but arm64 and x86 differ slightly (up to 0.0016).

Usage: run_native_shadow_auc_aws.py --image URI@sha256:... --artifacts DIR --subnets ... --security-groups ...
"""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import shlex
import time

import boto3

from bankai_benchmark.budget import ACTION, PILOT_SECONDS, arm, reserve_supplemental, stop, validate_policy

spec = importlib.util.spec_from_file_location("runner", Path(__file__).with_name("run_native_shadow_aws.py"))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
REGION, BUCKET, EXPERIMENT = runner.REGION, runner.BUCKET, runner.EXPERIMENT
SYNC = ("import boto3, os, sys; s3 = boto3.client('s3', region_name=os.environ['AWS_REGION']); "
    "bucket, prefix, target = sys.argv[1:]; os.makedirs(target, exist_ok=True); "
    "[s3.download_file(bucket, item['Key'], os.path.join(target, item['Key'][len(prefix):])) "
    "for page in s3.get_paginator('list_objects_v2').paginate(Bucket=bucket, Prefix=prefix) "
    "for item in page.get('Contents', [])]")


def script(prefix, threads):
    job = "/tmp/auc"
    return "\n".join(["set -e",
        f"/opt/candidate/bin/python -c {shlex.quote(SYNC)} {BUCKET} {prefix}input/ {job}",
        f"PYTHONPATH=/opt/bankai-benchmark/src /opt/candidate/bin/python {job}/native_shadow_auc.py {job} {job}/auc.json {threads}",
        f"/opt/candidate/bin/python -c \"import boto3, os; boto3.client('s3', region_name=os.environ['AWS_REGION'])"
        f".upload_file('{job}/auc.json', '{BUCKET}', '{prefix}output/auc.json')\""])


def task_definition(outputs, image, prefix, threads, instance):
    spec = runner.INSTANCES[instance]
    return dict(family=EXPERIMENT, requiresCompatibilities=["EC2"], networkMode="bridge",
        cpu=str(spec["cpu"]), memory=str(spec["memory"]), executionRoleArn=outputs["ExecutionRole"],
        taskRoleArn=outputs["TaskRole"], runtimePlatform=dict(cpuArchitecture="X86_64", operatingSystemFamily="LINUX"),
        containerDefinitions=[dict(name="native-shadow", image=image, essential=True, cpu=spec["cpu"], memory=spec["memory"],
            entryPoint=["sh", "-c"], command=[script(prefix, threads)],
            environment=[dict(name="AWS_REGION", value=REGION)],
            logConfiguration=dict(logDriver="awslogs", options={"awslogs-group": outputs["Logs"],
                "awslogs-region": REGION, "awslogs-stream-prefix": "native-shadow-auc"}))])


def run(args):
    validate_policy()
    session = boto3.Session(region_name=REGION)
    cf, ecs, ec2 = session.client("cloudformation"), session.client("ecs"), session.client("ec2")
    autoscaling, s3 = session.client("autoscaling"), session.client("s3")
    if args.image.count("@sha256:") != 1:
        raise ValueError("Use an immutable image URI containing @sha256:<digest>")
    running = ec2.describe_instances(Filters=[{"Name": "instance-state-name", "Values": ["pending", "running"]}])
    if any(instance for reservation in running["Reservations"] for instance in reservation["Instances"]):
        raise RuntimeError("An EC2 instance is already active; refusing overlapping benchmark capacity")
    if runner.stack_exists(cf, args.stack):
        raise RuntimeError(f"Stack {args.stack} already exists")
    source = Path(args.artifacts)
    prefix = f"{EXPERIMENT}/auc/{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}/"
    files = [Path(__file__).with_name("native_shadow_auc.py"), *sorted(source.glob("*-seed*-t*.json"))]
    if (source / "auc.json").exists():
        files.append(source / "auc.json")
    for path in files:
        s3.upload_file(str(path), BUCKET, f"{prefix}input/{path.name}")
    outputs = runner.create_stack(cf, args.stack, args.subnets, args.security_groups, args.instance)
    registered = ecs.register_task_definition(**task_definition(outputs, args.image, prefix, args.threads, args.instance))["taskDefinition"]
    group = outputs["Fleet"]
    shutdown = arm(autoscaling, group, duration_seconds=args.hours * PILOT_SECONDS)
    try:
        reserve_supplemental(s3, BUCKET, group, args.hours, runner.INSTANCES[args.instance]["hour_usd"])
    except Exception:
        autoscaling.delete_scheduled_action(AutoScalingGroupName=group, ScheduledActionName=ACTION)
        raise
    state = dict(protocol=EXPERIMENT, job="downstream-auc", stack=args.stack, outputs=outputs, image=args.image,
        task_definition=registered["taskDefinitionArn"], prefix=prefix, inputs=[path.name for path in files],
        threads=args.threads, instance=args.instance,
        reserved_usd=str(runner.INSTANCES[args.instance]["hour_usd"] * args.hours), budget="supplemental-150-usd",
        shutdown_at=shutdown.isoformat(), status="reserved")
    Path(args.state).write_text(json.dumps(state, indent=2) + "\n")
    task_arn = None
    try:
        autoscaling.update_auto_scaling_group(AutoScalingGroupName=group, MinSize=0, MaxSize=1, DesiredCapacity=1)
        host = runner.wait_for_container(ec2, ecs, outputs["Cluster"], shutdown.replace(microsecond=0), args.instance)
        response = ecs.run_task(cluster=outputs["Cluster"], taskDefinition=registered["taskDefinitionArn"], count=1,
            launchType="EC2", placementConstraints=[dict(type="distinctInstance"),
                dict(type="memberOf", expression="attribute:ecs.instance-type == " + args.instance)])
        if response.get("failures") or len(response.get("tasks", [])) != 1:
            raise RuntimeError(f"ECS rejected the AUC task: {response.get('failures')}")
        task_arn = response["tasks"][0]["taskArn"]
        state.update(status="running", host=host["ec2InstanceId"], task=task_arn)
        Path(args.state).write_text(json.dumps(state, indent=2) + "\n")
        while datetime.now(timezone.utc).timestamp() < shutdown.timestamp() - 300:
            item = ecs.describe_tasks(cluster=outputs["Cluster"], tasks=[task_arn])["tasks"][0]
            if item["lastStatus"] == "STOPPED":
                container = item["containers"][0]
                if item.get("stopCode") != "EssentialContainerExited" or container.get("exitCode") != 0:
                    raise RuntimeError(f"AUC task failed: {container}")
                state.update(status="completed", exit_code=0, stopped_at=datetime.now(timezone.utc).isoformat())
                break
            time.sleep(10)
        else:
            raise TimeoutError("AUC task reached its five-minute shutdown safety margin")
        s3.download_file(BUCKET, f"{prefix}output/auc.json", str(source / "auc.json"))
        state["output"] = f"s3://{BUCKET}/{prefix}output/auc.json"
        Path(args.state).write_text(json.dumps(state, indent=2) + "\n")
    finally:
        if task_arn:
            try:
                if ecs.describe_tasks(cluster=outputs["Cluster"], tasks=[task_arn])["tasks"][0]["lastStatus"] != "STOPPED":
                    ecs.stop_task(cluster=outputs["Cluster"], task=task_arn, reason="AUC cleanup")
            except Exception:
                pass
        stop(autoscaling, group)
        runner.wait_for_empty_fleet(autoscaling, group)
    print(json.dumps(state, indent=2, default=str))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--artifacts", required=True)
    parser.add_argument("--instance", choices=sorted(runner.INSTANCES), default="c7a.8xlarge")
    parser.add_argument("--threads", type=int, default=32)
    parser.add_argument("--subnets", nargs="+", required=True)
    parser.add_argument("--security-groups", nargs="+", required=True)
    parser.add_argument("--hours", type=int, default=2)
    parser.add_argument("--stack", default="bankai-ns-x2-auc")
    parser.add_argument("--state", required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
