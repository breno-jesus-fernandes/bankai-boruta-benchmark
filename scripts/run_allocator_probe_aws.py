"""Probe glibc allocator retention: Bankai exact on CIC-IDS2017 under malloc variants (AMD, one task).

Runs the published native-shadow image once per variant, in order, with the
variant's environment exported to the pilot and its fit workers:

- baseline: default glibc malloc, 16 threads;
- arena2: MALLOC_ARENA_MAX=2;
- mmap64k: a fixed 64 KiB mmap threshold, so large blocks return to the OS on free;
- t8: default malloc, 8 threads.

Each variant uploads one artifact per seed under its own pilot run id; the
state file records the variant order.
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
VARIANTS = (
    ("baseline", {}, 16),
    ("arena2", {"MALLOC_ARENA_MAX": "2"}, 16),
    ("mmap64k", {"GLIBC_TUNABLES": "glibc.malloc.mmap_threshold=65536"}, 16),
    ("t8", {}, 8),
)


def script(seeds):
    lines = ["set -e"]
    for name, environment, threads in VARIANTS:
        exports = " ".join(f"{key}={shlex.quote(value)}" for key, value in environment.items())
        lines.append(f"echo VARIANT {name}")
        lines.append(f"{exports} /opt/candidate/bin/python /opt/native_shadow_pilot.py --bucket {BUCKET} "
            f"--experiment {EXPERIMENT} --datasets cicids2017 --methods bankai_exact --seeds {' '.join(map(str, seeds))} "
            f"--threads {threads} --repeats 1 --timeout-seconds 3600 --max-iter 40".strip())
    return "\n".join(lines)


def task_definition(outputs, image, seeds):
    return dict(family=EXPERIMENT, requiresCompatibilities=["EC2"], networkMode="bridge",
        cpu="16384", memory="28672", executionRoleArn=outputs["ExecutionRole"], taskRoleArn=outputs["TaskRole"],
        runtimePlatform=dict(cpuArchitecture="X86_64", operatingSystemFamily="LINUX"),
        containerDefinitions=[dict(name="native-shadow", image=image, essential=True, cpu=16384, memory=28672,
            entryPoint=["sh", "-c"], command=[script(seeds)],
            environment=[dict(name="AWS_REGION", value=REGION)],
            logConfiguration=dict(logDriver="awslogs", options={"awslogs-group": outputs["Logs"],
                "awslogs-region": REGION, "awslogs-stream-prefix": "allocator-probe"}))])


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
    before = {item["Key"] for item in s3.list_objects_v2(Bucket=BUCKET, Prefix=f"{EXPERIMENT}/pilot/").get("Contents", [])}
    outputs = runner.create_stack(cf, args.stack, args.subnets, args.security_groups)
    registered = ecs.register_task_definition(**task_definition(outputs, args.image, args.seeds))["taskDefinition"]
    group = outputs["Fleet"]
    shutdown = arm(autoscaling, group, duration_seconds=args.hours * PILOT_SECONDS)
    try:
        reserve_supplemental(s3, BUCKET, group, args.hours)
    except Exception:
        autoscaling.delete_scheduled_action(AutoScalingGroupName=group, ScheduledActionName=ACTION)
        raise
    state = dict(protocol=EXPERIMENT, probe="allocator", stack=args.stack, outputs=outputs, image=args.image,
        task_definition=registered["taskDefinitionArn"], seeds=args.seeds,
        variants=[dict(name=name, environment=environment, threads=threads) for name, environment, threads in VARIANTS],
        reserved_usd=str(1.5 * args.hours), budget="supplemental-150-usd", shutdown_at=shutdown.isoformat(), status="reserved")
    Path(args.state).write_text(json.dumps(state, indent=2) + "\n")
    task_arn = None
    try:
        autoscaling.update_auto_scaling_group(AutoScalingGroupName=group, MinSize=0, MaxSize=1, DesiredCapacity=1)
        host = runner.wait_for_container(ec2, ecs, outputs["Cluster"], shutdown.replace(microsecond=0))
        response = ecs.run_task(cluster=outputs["Cluster"], taskDefinition=registered["taskDefinitionArn"], count=1,
            launchType="EC2", placementConstraints=[dict(type="distinctInstance"),
                dict(type="memberOf", expression="attribute:ecs.instance-type == c7a.4xlarge")])
        if response.get("failures") or len(response.get("tasks", [])) != 1:
            raise RuntimeError(f"ECS rejected the probe task: {response.get('failures')}")
        task_arn = response["tasks"][0]["taskArn"]
        state.update(status="running", host=host["ec2InstanceId"], task=task_arn)
        Path(args.state).write_text(json.dumps(state, indent=2) + "\n")
        while datetime.now(timezone.utc).timestamp() < shutdown.timestamp() - 300:
            item = ecs.describe_tasks(cluster=outputs["Cluster"], tasks=[task_arn])["tasks"][0]
            if item["lastStatus"] == "STOPPED":
                container = item["containers"][0]
                if item.get("stopCode") != "EssentialContainerExited" or container.get("exitCode") != 0:
                    raise RuntimeError(f"Probe task failed: {container}")
                state.update(status="completed", exit_code=0, stopped_at=datetime.now(timezone.utc).isoformat())
                break
            time.sleep(10)
        else:
            raise TimeoutError("Probe reached its five-minute shutdown safety margin")
        after = s3.list_objects_v2(Bucket=BUCKET, Prefix=f"{EXPERIMENT}/pilot/").get("Contents", [])
        state["result_objects"] = sorted(item["Key"] for item in after if item["Key"] not in before)
        if len(state["result_objects"]) != len(VARIANTS) * len(args.seeds):
            raise RuntimeError("Probe completed without one artifact per variant and seed")
        Path(args.state).write_text(json.dumps(state, indent=2) + "\n")
    finally:
        if task_arn:
            try:
                if ecs.describe_tasks(cluster=outputs["Cluster"], tasks=[task_arn])["tasks"][0]["lastStatus"] != "STOPPED":
                    ecs.stop_task(cluster=outputs["Cluster"], task=task_arn, reason="Allocator probe cleanup")
            except Exception:
                pass
        stop(autoscaling, group)
        runner.wait_for_empty_fleet(autoscaling, group)
    print(json.dumps(state, indent=2, default=str))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--subnets", nargs="+", required=True)
    parser.add_argument("--security-groups", nargs="+", required=True)
    parser.add_argument("--seeds", type=int, nargs="+", default=[46, 42])
    parser.add_argument("--hours", type=int, default=2)
    parser.add_argument("--stack", default="bankai-allocator-probe")
    parser.add_argument("--state", default="verification/allocator-probe-amd-20261023.json")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
