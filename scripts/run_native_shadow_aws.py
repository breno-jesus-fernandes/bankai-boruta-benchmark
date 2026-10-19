"""Provision and run the AMD Industrial native-shadow comparison (Bankai exact, binned, BorutaPy)."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time

import boto3
from botocore.exceptions import ClientError

from bankai_benchmark.aws_ecs import infrastructure
from bankai_benchmark.budget import ACTION, PILOT_SECONDS, arm, reserve_supplemental, stop, validate_policy


REGION = "us-east-1"
BUCKET = "bankai-benchmark-bootstrap-results-ku2wdx1kzzqb"
EXPERIMENT = "native-shadow-max40-v1"


def task_definition(outputs, image, datasets, seeds, threads, repeats):
    return dict(family=EXPERIMENT, requiresCompatibilities=["EC2"], networkMode="bridge",
        cpu="16384", memory="28672", executionRoleArn=outputs["ExecutionRole"],
        taskRoleArn=outputs["TaskRole"],
        runtimePlatform=dict(cpuArchitecture="X86_64", operatingSystemFamily="LINUX"),
        containerDefinitions=[dict(name="native-shadow", image=image, essential=True,
            cpu=16384, memory=28672,
            entryPoint=["/opt/candidate/bin/python", "/opt/native_shadow_pilot.py"],
            command=["--bucket", BUCKET, "--experiment", EXPERIMENT,
                "--datasets", *datasets, "--seeds", *map(str, seeds), "--threads", str(threads),
                "--repeats", str(repeats), "--timeout-seconds", "1800", "--max-iter", "40"],
            environment=[dict(name="AWS_REGION", value=REGION)],
            logConfiguration=dict(logDriver="awslogs", options={
                "awslogs-group": outputs["Logs"], "awslogs-region": REGION,
                "awslogs-stream-prefix": "native-shadow-max40"}))])


def create_stack(cf, stack_name, subnets, security_groups):
    template = infrastructure(EXPERIMENT, BUCKET, subnets, security_groups)
    cf.create_stack(StackName=stack_name, TemplateBody=json.dumps(template), Capabilities=["CAPABILITY_IAM"])
    cf.get_waiter("stack_create_complete").wait(StackName=stack_name, WaiterConfig={"Delay": 10, "MaxAttempts": 60})
    stack = cf.describe_stacks(StackName=stack_name)["Stacks"][0]
    return {item["OutputKey"]: item["OutputValue"] for item in stack["Outputs"]}


def stack_exists(cf, stack_name):
    try:
        stacks = cf.describe_stacks(StackName=stack_name).get("Stacks", [])
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") == "ValidationError":
            return False
        raise
    return bool(stacks)


def wait_for_container(ec2, ecs, cluster, deadline):
    while datetime.now(timezone.utc) < deadline:
        arns = ecs.list_container_instances(cluster=cluster, status="ACTIVE")["containerInstanceArns"]
        if arns:
            instances = ecs.describe_container_instances(cluster=cluster, containerInstances=arns)["containerInstances"]
            for item in instances:
                host = ec2.describe_instances(InstanceIds=[item["ec2InstanceId"]])["Reservations"][0]["Instances"][0]
                cpu = host.get("CpuOptions", {})
                if (host["InstanceType"] == "c7a.4xlarge"
                        and cpu.get("CoreCount") == 16 and cpu.get("ThreadsPerCore") == 1
                        and item["status"] == "ACTIVE"):
                    return item
            raise RuntimeError("ECS host did not match the required AMD 16-core topology")
        time.sleep(5)
    raise TimeoutError("AMD ECS host did not register before the readiness deadline")


def wait_for_empty_fleet(autoscaling, fleet, timeout=300):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        groups = autoscaling.describe_auto_scaling_groups(AutoScalingGroupNames=[fleet])["AutoScalingGroups"]
        if len(groups) == 1 and not groups[0]["Instances"] and groups[0]["DesiredCapacity"] == 0:
            return
        time.sleep(5)
    raise TimeoutError("AMD fleet did not return to zero capacity")


def run(args):
    validate_policy()
    session = boto3.Session(region_name=REGION)
    cf, ecs, ec2 = session.client("cloudformation"), session.client("ecs"), session.client("ec2")
    autoscaling, s3, ecr = session.client("autoscaling"), session.client("s3"), session.client("ecr")
    digest = args.image.rsplit("@sha256:", 1)[-1]
    if (args.image.count("@sha256:") != 1 or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)):
        raise ValueError("Use an immutable image URI containing @sha256:<digest>")
    details = ecr.describe_images(registryId="642504869083", repositoryName="bankai-image-publisher-images",
            imageIds=[{"imageDigest": args.image.rsplit("@", 1)[1]}]).get("imageDetails", [])
    if len(details) != 1:
        raise RuntimeError("Candidate image digest was not found in ECR")
    running = ec2.describe_instances(Filters=[{"Name": "instance-state-name", "Values": ["pending", "running"]}])
    if any(instance for reservation in running["Reservations"] for instance in reservation["Instances"]):
        raise RuntimeError("An EC2 instance is already active; refusing overlapping benchmark capacity")
    stack_name = args.stack
    if stack_exists(cf, stack_name):
        raise RuntimeError(f"Stack {stack_name} already exists; inspect it instead of creating a duplicate")
    outputs = create_stack(cf, stack_name, args.subnets, args.security_groups)
    definition = task_definition(outputs, args.image, args.datasets, args.seeds, args.threads, args.repeats)
    registered = ecs.register_task_definition(**definition)["taskDefinition"]
    group_name = outputs["Fleet"]
    current = autoscaling.describe_auto_scaling_groups(AutoScalingGroupNames=[group_name])["AutoScalingGroups"][0]
    if current["MinSize"] != 0 or current["MaxSize"] != 1 or current["DesiredCapacity"] != 0 or current["Instances"]:
        raise RuntimeError("New native-shadow fleet is not idle with max capacity one")

    # Install and verify the AWS shutdown before committing the budget reservation.
    shutdown = arm(autoscaling, group_name, duration_seconds=args.hours * PILOT_SECONDS)
    try:
        # The BRL 400 ledger is fully allocated; this run uses the USD 150 extension.
        reserve_supplemental(s3, BUCKET, group_name, args.hours)
    except Exception:
        autoscaling.delete_scheduled_action(AutoScalingGroupName=group_name, ScheduledActionName=ACTION)
        raise
    state = dict(protocol=EXPERIMENT, stack=stack_name, outputs=outputs,
        image=args.image, task_definition=registered["taskDefinitionArn"], datasets=args.datasets, seeds=args.seeds,
        threads=args.threads, repeats=args.repeats,
        reserved_usd=str(1.5 * args.hours), budget="supplemental-150-usd", shutdown_at=shutdown.isoformat(), status="reserved")
    Path(args.state).write_text(json.dumps(state, indent=2) + "\n")
    task_arn = None
    try:
        autoscaling.update_auto_scaling_group(AutoScalingGroupName=group_name, MinSize=0, MaxSize=1, DesiredCapacity=1)
        host = wait_for_container(ec2, ecs, outputs["Cluster"], shutdown.replace(microsecond=0))
        task_response = ecs.run_task(cluster=outputs["Cluster"], taskDefinition=registered["taskDefinitionArn"],
            count=1, launchType="EC2",
            placementConstraints=[dict(type="distinctInstance"),
                dict(type="memberOf", expression="attribute:ecs.instance-type == c7a.4xlarge")])
        if task_response.get("failures") or len(task_response.get("tasks", [])) != 1:
            raise RuntimeError(f"ECS rejected native-shadow task: {task_response.get('failures')}")
        task_arn = task_response["tasks"][0]["taskArn"]
        state.update(status="running", host=host["ec2InstanceId"], task=task_arn)
        Path(args.state).write_text(json.dumps(state, indent=2) + "\n")
        task_deadline = shutdown.timestamp() - 300
        while datetime.now(timezone.utc).timestamp() < task_deadline:
            item = ecs.describe_tasks(cluster=outputs["Cluster"], tasks=[task_arn])["tasks"][0]
            if item["lastStatus"] == "STOPPED":
                if item.get("stopCode") != "EssentialContainerExited":
                    raise RuntimeError(f"Pilot task stopped unexpectedly: {item}")
                container = item["containers"][0]
                if container.get("exitCode") != 0:
                    raise RuntimeError(f"Pilot task failed: {container}")
                state.update(status="completed", exit_code=0, stopped_at=datetime.now(timezone.utc).isoformat())
                break
            time.sleep(10)
        else:
            raise TimeoutError("Pilot reached its five-minute shutdown safety margin")
        keys = s3.list_objects_v2(Bucket=BUCKET, Prefix=f"{EXPERIMENT}/pilot/").get("Contents", [])
        state["result_objects"] = [{"key": item["Key"], "bytes": item["Size"]} for item in keys]
        if len(state["result_objects"]) < len(args.seeds) * len(args.datasets):
            raise RuntimeError("Task completed without one result artifact per seed")
        Path(args.state).write_text(json.dumps(state, indent=2) + "\n")
    finally:
        if task_arn:
            try:
                task = ecs.describe_tasks(cluster=outputs["Cluster"], tasks=[task_arn])["tasks"][0]
                if task["lastStatus"] != "STOPPED":
                    ecs.stop_task(cluster=outputs["Cluster"], task=task_arn, reason="Native-shadow cleanup")
            except Exception:
                pass
        stop(autoscaling, group_name)
        wait_for_empty_fleet(autoscaling, group_name)
    print(json.dumps(state, indent=2, default=str))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--subnets", nargs="+", required=True)
    parser.add_argument("--security-groups", nargs="+", required=True)
    parser.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44, 45, 46])
    parser.add_argument("--threads", type=int, default=16)
    parser.add_argument("--datasets", nargs="+", default=["industrial"])
    parser.add_argument("--hours", type=int, default=2)
    parser.add_argument("--stack", default="bankai-native-shadow-max40")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--state", default="verification/native-shadow-max40-amd-20261019.json")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
