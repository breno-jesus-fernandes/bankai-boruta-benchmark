"""Compare candidate bankai-boruta wheels on the native-shadow datasets (AMD, one task).

Uploads each local Linux wheel under the experiment's wheels/ prefix, then runs
the published native-shadow image once per wheel, in order: the container
unpacks the wheel into its own directory and puts it first on PYTHONPATH for
the pilot and its fit workers, together with every --extra-wheel (for example
the bankai-random-forest release the candidates require). Each wheel uploads one artifact per seed under
its own pilot run id; the state file records the wheel order and digests.

Usage: run_candidate_probe_aws.py --wheel NAME=PATH [--wheel ...] [--extra-wheel PATH] ...
"""
import argparse
import hashlib
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
UNPACK = ("import boto3, os, sys, zipfile; "
    "s3 = boto3.client('s3', region_name=os.environ['AWS_REGION']); "
    "[(s3.download_file(sys.argv[1], key, '/tmp/wheel.whl'), zipfile.ZipFile('/tmp/wheel.whl').extractall(sys.argv[-1])) "
    "for key in sys.argv[2:-1]]")


def script(wheels, extras, seeds, threads, methods, datasets, repeats=1):
    lines = ["set -e"]
    for wheel in wheels:
        site = f"/tmp/site-{wheel['name']}"
        lines.append(f"echo WHEEL {wheel['name']}")
        lines.append(f"/opt/candidate/bin/python -c {shlex.quote(UNPACK)} {BUCKET} {wheel['key']} {' '.join(extra['key'] for extra in extras)} {site}")
        lines.append(f"PYTHONPATH={site} /opt/candidate/bin/python -c 'import bankai_boruta; print(bankai_boruta.__file__)'")
        lines.append(f"PYTHONPATH={site} /opt/candidate/bin/python /opt/native_shadow_pilot.py --bucket {BUCKET} "
            f"--experiment {EXPERIMENT} --datasets {' '.join(datasets)} --methods {' '.join(wheel.get('methods') or methods)} --seeds {' '.join(map(str, seeds))} "
            f"--threads {threads} --repeats {repeats} --timeout-seconds 3600 --max-iter 40")
    return "\n".join(lines)


def task_definition(outputs, image, wheels, extras, seeds, threads, methods, datasets, repeats=1):
    return dict(family=EXPERIMENT, requiresCompatibilities=["EC2"], networkMode="bridge",
        cpu="16384", memory="28672", executionRoleArn=outputs["ExecutionRole"], taskRoleArn=outputs["TaskRole"],
        runtimePlatform=dict(cpuArchitecture="X86_64", operatingSystemFamily="LINUX"),
        containerDefinitions=[dict(name="native-shadow", image=image, essential=True, cpu=16384, memory=28672,
            entryPoint=["sh", "-c"], command=[script(wheels, extras, seeds, threads, methods, datasets, repeats)],
            environment=[dict(name="AWS_REGION", value=REGION)],
            logConfiguration=dict(logDriver="awslogs", options={"awslogs-group": outputs["Logs"],
                "awslogs-region": REGION, "awslogs-stream-prefix": "candidate-probe"}))])


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
    def upload(name, path):
        data = Path(path).read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        key = f"{EXPERIMENT}/wheels/{digest[:16]}/{Path(path).name}"
        s3.put_object(Bucket=BUCKET, Key=key, Body=data)
        return dict(name=name, file=Path(path).name, sha256=digest, key=key)
    wheels = []
    for item in args.wheel:
        name, path = item.split("=", 1)
        path, _, methods = path.partition("@")
        wheels.append(dict(upload(name, path), methods=methods.split(",") if methods else None))
    extras = [upload(Path(path).name, path) for path in args.extra_wheel]
    before = {item["Key"] for item in s3.list_objects_v2(Bucket=BUCKET, Prefix=f"{EXPERIMENT}/pilot/").get("Contents", [])}
    outputs = runner.create_stack(cf, args.stack, args.subnets, args.security_groups)
    registered = ecs.register_task_definition(**task_definition(outputs, args.image, wheels, extras, args.seeds, args.threads, args.methods, args.datasets, args.repeats))["taskDefinition"]
    group = outputs["Fleet"]
    shutdown = arm(autoscaling, group, duration_seconds=args.hours * PILOT_SECONDS)
    try:
        reserve_supplemental(s3, BUCKET, group, args.hours)
    except Exception:
        autoscaling.delete_scheduled_action(AutoScalingGroupName=group, ScheduledActionName=ACTION)
        raise
    state = dict(protocol=EXPERIMENT, probe="candidate-wheels", stack=args.stack, outputs=outputs, image=args.image,
        task_definition=registered["taskDefinitionArn"], seeds=args.seeds, threads=args.threads, repeats=args.repeats, methods=args.methods, datasets=args.datasets, wheels=wheels, extra_wheels=extras,
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
        if len(state["result_objects"]) != len(wheels) * len(args.seeds) * len(args.datasets):  # one artifact per dataset and seed holds every method
            raise RuntimeError("Probe completed without one artifact per wheel and seed")
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
        # The stack's capacity provider and log group use fixed experiment names,
        # so a leftover stack would block the next probe.
        cf.delete_stack(StackName=args.stack)
    print(json.dumps(state, indent=2, default=str))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--wheel", action="append", required=True, help="NAME=PATH[@METHOD,...] of a Linux x86_64 wheel; methods default to --methods")
    parser.add_argument("--extra-wheel", action="append", default=[], help="wheel unpacked next to every candidate")
    parser.add_argument("--threads", type=int, default=16)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--methods", nargs="+", default=["bankai_exact"])
    parser.add_argument("--datasets", nargs="+", default=["cicids2017"])
    parser.add_argument("--subnets", nargs="+", required=True)
    parser.add_argument("--security-groups", nargs="+", required=True)
    parser.add_argument("--seeds", type=int, nargs="+", default=[46, 42])
    parser.add_argument("--hours", type=int, default=2)
    parser.add_argument("--stack", default="bankai-candidate-probe")
    parser.add_argument("--state", required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
