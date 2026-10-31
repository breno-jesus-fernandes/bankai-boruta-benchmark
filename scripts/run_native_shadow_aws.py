"""Provision and run the AMD native-shadow comparison (Bankai exact, binned, BorutaPy).

One task runs the pilot once per --threads value, in order, on one host. While
polling, expired local AWS credentials do not abort the launch: the runner
waits for a fresh `aws login` (the armed AWS shutdown bounds the cost meanwhile)
and `--resume STATE` finalizes a launch from its state file.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time

import boto3
from botocore import exceptions as botocore_errors
from botocore.exceptions import ClientError

from bankai_benchmark.aws_ecs import infrastructure
from bankai_benchmark.budget import (ACTION, PILOT_SECONDS, SUPPLEMENTAL_HOUR_USD, SUPPLEMENTAL_HOUR_USD_8XL,
    SUPPLEMENTAL_HOUR_USD_16XL, arm, reserve_supplemental, stop, validate_policy)


REGION = "us-east-1"
BUCKET = "bankai-benchmark-bootstrap-results-ku2wdx1kzzqb"
EXPERIMENT = "native-shadow-max40-v1"
# AMD hosts without SMT; ECS memory leaves headroom for the OS and agent.
INSTANCES = {
    "c7a.4xlarge": dict(cores=16, cpu=16384, memory=28672, memory_gib=32, hour_usd=SUPPLEMENTAL_HOUR_USD),
    "c7a.8xlarge": dict(cores=32, cpu=32768, memory=59392, memory_gib=64, hour_usd=SUPPLEMENTAL_HOUR_USD_8XL),
    "c7a.16xlarge": dict(cores=64, cpu=65536, memory=122880, memory_gib=128, hour_usd=SUPPLEMENTAL_HOUR_USD_16XL),
}
LOG_PREFIX = "native-shadow-max40"
CREDENTIAL_CODES = {"ExpiredToken", "ExpiredTokenException", "RequestExpired", "InvalidClientTokenId",
    "UnrecognizedClientException"}
CREDENTIAL_ERRORS = (botocore_errors.NoCredentialsError, botocore_errors.TokenRetrievalError,
    botocore_errors.CredentialRetrievalError, botocore_errors.UnauthorizedSSOTokenError, botocore_errors.SSOTokenLoadError,
    botocore_errors.LoginTokenLoadError)


def credentials_expired(error):
    if isinstance(error, ClientError):
        return error.response.get("Error", {}).get("Code") in CREDENTIAL_CODES
    return isinstance(error, CREDENTIAL_ERRORS)


class Aws:
    """boto3 clients that are rebuilt, after a wait, when the local credentials expire."""

    def __init__(self, wait_seconds=60):
        self.wait_seconds = wait_seconds
        self.renew()

    def renew(self):
        self.session, self.clients = boto3.Session(region_name=REGION), {}

    def client(self, name):
        if name not in self.clients:
            self.clients[name] = self.session.client(name)
        return self.clients[name]

    def retry(self, call, deadline):
        warned = False
        while True:
            try:
                return call(self)
            except Exception as error:
                if not credentials_expired(error) or datetime.now(timezone.utc) >= deadline:
                    raise
                if not warned:
                    print(f"{datetime.now(timezone.utc).isoformat()} AWS credentials expired; run `aws login`. "
                          f"Retrying every {self.wait_seconds} s until {deadline.isoformat()}.", flush=True)
                    warned = True
                time.sleep(self.wait_seconds)
                self.renew()


def machine(instance):
    spec = INSTANCES[instance]
    return dict(instance_type=instance, physical_cores=spec["cores"], threads_per_core=1, memory_gib=spec["memory_gib"])


def pilot_arguments(datasets, methods, seeds, threads, repeats, scale, auc=False):
    return ["--bucket", BUCKET, "--experiment", EXPERIMENT, "--datasets", *datasets, "--methods", *methods,
        "--seeds", *map(str, seeds), "--threads", str(threads), "--repeats", str(repeats), "--timeout-seconds", "3600",
        "--max-iter", "40", "--scale", str(scale), *(["--auc"] if auc else [])]


def task_definition(outputs, image, datasets, methods, seeds, threads, repeats, instance="c7a.4xlarge", scale=1, auc=False):
    """One pilot per thread count; with several, the downstream AUC runs only after the last."""
    spec = INSTANCES[instance]
    sweep = threads if isinstance(threads, (list, tuple)) else [threads]
    if len(sweep) == 1:
        entry_point = ["/opt/candidate/bin/python", "/opt/native_shadow_pilot.py"]
        command = pilot_arguments(datasets, methods, seeds, sweep[0], repeats, scale, auc)
    else:
        entry_point = ["sh", "-c"]
        command = ["set -e\n" + "\n".join(" ".join(["/opt/candidate/bin/python", "/opt/native_shadow_pilot.py",
            *pilot_arguments(datasets, methods, seeds, count, repeats, scale, auc and index == len(sweep) - 1)])
            for index, count in enumerate(sweep))]
    return dict(family=EXPERIMENT, requiresCompatibilities=["EC2"], networkMode="bridge",
        cpu=str(spec["cpu"]), memory=str(spec["memory"]), executionRoleArn=outputs["ExecutionRole"],
        taskRoleArn=outputs["TaskRole"],
        runtimePlatform=dict(cpuArchitecture="X86_64", operatingSystemFamily="LINUX"),
        containerDefinitions=[dict(name="native-shadow", image=image, essential=True,
            cpu=spec["cpu"], memory=spec["memory"],
            entryPoint=entry_point, command=command,
            environment=[dict(name="AWS_REGION", value=REGION)],
            logConfiguration=dict(logDriver="awslogs", options={
                "awslogs-group": outputs["Logs"], "awslogs-region": REGION,
                "awslogs-stream-prefix": LOG_PREFIX}))])


def create_stack(cf, stack_name, subnets, security_groups, instance="c7a.4xlarge"):
    template = infrastructure(EXPERIMENT, BUCKET, subnets, security_groups, machine(instance))
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


def wait_for_container(ec2, ecs, cluster, deadline, instance="c7a.4xlarge"):
    while datetime.now(timezone.utc) < deadline:
        arns = ecs.list_container_instances(cluster=cluster, status="ACTIVE")["containerInstanceArns"]
        if arns:
            instances = ecs.describe_container_instances(cluster=cluster, containerInstances=arns)["containerInstances"]
            for item in instances:
                host = ec2.describe_instances(InstanceIds=[item["ec2InstanceId"]])["Reservations"][0]["Instances"][0]
                cpu = host.get("CpuOptions", {})
                if (host["InstanceType"] == instance
                        and cpu.get("CoreCount") == INSTANCES[instance]["cores"] and cpu.get("ThreadsPerCore") == 1
                        and item["status"] == "ACTIVE"):
                    return item
            raise RuntimeError(f"ECS host did not match the required AMD {INSTANCES[instance]['cores']}-core topology")
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


def save(path, state):
    Path(path).write_text(json.dumps(state, indent=2) + "\n")


def pilot_successes(aws, state, deadline):
    """Pilot runs that logged success; ECS forgets stopped tasks after about an hour, the logs stay."""
    stream = f"{LOG_PREFIX}/native-shadow/{state['task'].rsplit('/', 1)[-1]}"
    def count(client):
        found, token = 0, None
        while True:
            page = client.client("logs").filter_log_events(logGroupName=state["outputs"]["Logs"],
                logStreamNames=[stream], filterPattern='"success"', **({"nextToken": token} if token else {}))
            found += sum(1 for event in page["events"] if '"status": "success"' in event["message"])
            token = page.get("nextToken")
            if not token:
                return found
    return aws.retry(count, deadline)


def finish(aws, state, state_path):
    """Poll the task, verify its artifacts and drain the fleet; safe to run again with --resume."""
    outputs, task_arn = state["outputs"], state["task"]
    shutdown = datetime.fromisoformat(state["shutdown_at"])
    started = datetime.fromisoformat(state["started_at"])
    threads = state["threads"] if isinstance(state["threads"], list) else [state["threads"]]
    try:
        while datetime.now(timezone.utc).timestamp() < shutdown.timestamp() - 300:
            tasks = aws.retry(lambda client: client.client("ecs").describe_tasks(cluster=outputs["Cluster"],
                tasks=[task_arn])["tasks"], shutdown)
            if not tasks:
                # Forgotten by ECS: trust only every pilot's own success line.
                if pilot_successes(aws, state, shutdown) != len(threads):
                    raise RuntimeError("Task is gone from ECS without a success line for every pilot")
                state.update(status="completed", exit_code=0, exit_source="cloudwatch-logs")
                break
            item = tasks[0]
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
        # Count only this task's artifacts, not earlier runs under the same prefix.
        suffixes = tuple(f"-t{count}{'-x2' if state['scale'] == 2 else ''}.json" for count in threads)
        def listing(client):
            return [item for page in client.client("s3").get_paginator("list_objects_v2").paginate(
                Bucket=BUCKET, Prefix=f"{EXPERIMENT}/pilot/") for item in page.get("Contents", [])
                if item["LastModified"] >= started and item["Key"].endswith(suffixes)]
        keys = aws.retry(listing, shutdown)
        state["result_objects"] = [{"key": item["Key"], "bytes": item["Size"]} for item in keys]
        if len(state["result_objects"]) < len(state["seeds"]) * len(state["datasets"]) * len(threads):
            raise RuntimeError("Task completed without one result artifact per seed and thread count")
        save(state_path, state)
    finally:
        try:
            def cleanup(client):
                ecs = client.client("ecs")
                tasks = ecs.describe_tasks(cluster=outputs["Cluster"], tasks=[task_arn])["tasks"]
                if tasks and tasks[0]["lastStatus"] != "STOPPED":
                    ecs.stop_task(cluster=outputs["Cluster"], task=task_arn, reason="Native-shadow cleanup")
                stop(client.client("autoscaling"), outputs["Fleet"])
                wait_for_empty_fleet(client.client("autoscaling"), outputs["Fleet"])
            aws.retry(cleanup, shutdown)
        except Exception as error:
            # The armed AWS shutdown still drains the fleet at shutdown_at.
            print(f"Cleanup did not finish ({error!r}); the armed shutdown drains the fleet at {shutdown.isoformat()}", flush=True)
            raise
    return state


def run(args):
    validate_policy()
    aws = Aws()
    cf, ecs, ec2 = aws.client("cloudformation"), aws.client("ecs"), aws.client("ec2")
    autoscaling, s3, ecr = aws.client("autoscaling"), aws.client("s3"), aws.client("ecr")
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
    outputs = create_stack(cf, stack_name, args.subnets, args.security_groups, args.instance)
    definition = task_definition(outputs, args.image, args.datasets, args.methods, args.seeds, args.threads, args.repeats,
        args.instance, args.scale, args.auc)
    registered = ecs.register_task_definition(**definition)["taskDefinition"]
    group_name = outputs["Fleet"]
    current = autoscaling.describe_auto_scaling_groups(AutoScalingGroupNames=[group_name])["AutoScalingGroups"][0]
    if current["MinSize"] != 0 or current["MaxSize"] != 1 or current["DesiredCapacity"] != 0 or current["Instances"]:
        raise RuntimeError("New native-shadow fleet is not idle with max capacity one")

    # Install and verify the AWS shutdown before committing the budget reservation.
    shutdown = arm(autoscaling, group_name, duration_seconds=args.hours * PILOT_SECONDS)
    try:
        # The BRL 400 ledger is fully allocated; this run uses the USD supplemental extension.
        reserve_supplemental(s3, BUCKET, group_name, args.hours, INSTANCES[args.instance]["hour_usd"])
    except Exception:
        autoscaling.delete_scheduled_action(AutoScalingGroupName=group_name, ScheduledActionName=ACTION)
        raise
    state = dict(protocol=EXPERIMENT, stack=stack_name, outputs=outputs,
        image=args.image, task_definition=registered["taskDefinitionArn"], datasets=args.datasets, methods=args.methods, seeds=args.seeds,
        threads=args.threads if len(args.threads) > 1 else args.threads[0], repeats=args.repeats, instance=args.instance,
        scale=args.scale, auc=args.auc, reserved_usd=str(INSTANCES[args.instance]["hour_usd"] * args.hours),
        budget="supplemental-150-usd", shutdown_at=shutdown.isoformat(), status="reserved")
    save(args.state, state)
    try:
        autoscaling.update_auto_scaling_group(AutoScalingGroupName=group_name, MinSize=0, MaxSize=1, DesiredCapacity=1)
        host = wait_for_container(ec2, ecs, outputs["Cluster"], shutdown.replace(microsecond=0), args.instance)
        started = datetime.now(timezone.utc)
        task_response = ecs.run_task(cluster=outputs["Cluster"], taskDefinition=registered["taskDefinitionArn"],
            count=1, launchType="EC2",
            placementConstraints=[dict(type="distinctInstance"),
                dict(type="memberOf", expression="attribute:ecs.instance-type == " + args.instance)])
        if task_response.get("failures") or len(task_response.get("tasks", [])) != 1:
            raise RuntimeError(f"ECS rejected native-shadow task: {task_response.get('failures')}")
    except Exception:
        stop(autoscaling, group_name)
        wait_for_empty_fleet(autoscaling, group_name)
        raise
    state.update(status="running", host=host["ec2InstanceId"], task=task_response["tasks"][0]["taskArn"],
        started_at=started.isoformat())
    save(args.state, state)
    print(json.dumps(finish(aws, state, args.state), indent=2, default=str))


def resume(args):
    state = json.loads(Path(args.resume).read_text())
    if state.get("status") not in ("running", "completed") or "task" not in state:
        raise RuntimeError(f"Nothing to resume in {args.resume}: status {state.get('status')}")
    if "started_at" not in state:
        raise RuntimeError("State predates started_at; finalize it by hand")
    print(json.dumps(finish(Aws(), state, args.resume), indent=2, default=str))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resume", metavar="STATE", help="finish a launch from its state file (after `aws login`)")
    parser.add_argument("--image")
    parser.add_argument("--subnets", nargs="+")
    parser.add_argument("--security-groups", nargs="+")
    parser.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44, 45, 46])
    parser.add_argument("--instance", choices=sorted(INSTANCES), default="c7a.4xlarge")
    parser.add_argument("--threads", type=int, nargs="+",
        help="one pilot per value, in order, on the same host; defaults to the instance's physical cores")
    parser.add_argument("--auc", action="store_true", help="record the downstream AUC (after the last thread count)")
    parser.add_argument("--scale", type=int, choices=(1, 2), default=1, help="2 doubles synthetic rows and columns")
    parser.add_argument("--datasets", nargs="+", default=["industrial"])
    parser.add_argument("--methods", nargs="+",
        default=["bankai_exact", "bankai_binned", "borutapy", "borutapy_lgbm"])
    parser.add_argument("--hours", type=int, default=2)
    parser.add_argument("--stack", default="bankai-native-shadow-max40")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--state", default="verification/native-shadow-max40-amd-20261019.json")
    args = parser.parse_args()
    if args.resume:
        resume(args)
        return
    if not (args.image and args.subnets and args.security_groups):
        parser.error("--image, --subnets and --security-groups are required for a new launch")
    args.threads = args.threads or [INSTANCES[args.instance]["cores"]]
    if max(args.threads) > INSTANCES[args.instance]["cores"]:
        parser.error("--threads must not exceed the instance's physical cores")
    run(args)


if __name__ == "__main__":
    main()
