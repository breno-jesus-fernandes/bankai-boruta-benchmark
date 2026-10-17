"""Run the three remaining quality shards with AWS-side deadlines, without an LLM.

Uses the already verified image, cluster, roles and launch template. Each shard
gets a fresh, zero-capacity ASG and a separate nonrefundable budget reservation.
No benchmark implementation or manifest is changed. A failed/incomplete shard
halts the campaign; restarting this controller never repeats a paid launch.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import fcntl
import json
from pathlib import Path
import subprocess
import sys
import time

import boto3
from botocore.config import Config

from bankai_benchmark.aggregate_latex import aggregate, validated_results
from bankai_benchmark.budget import arm, reserve, stop, validate_policy
from bankai_benchmark.config import atomic_json


DATASETS = ("credito", "bioinformatica", "ciberseguranca")


def successful_exit(task):
    return (task.get("lastStatus") == "STOPPED"
            and len(task.get("containers", [])) == 1
            and task["containers"][0].get("exitCode") == 0)


def dataset_complete(results, expected, dataset):
    specs = [s for s in expected if s["dataset"] == dataset]
    found = {(r["competitor"], r["seed"], r["threads"]) for r in results
             if r["dataset"] == dataset and r["status"] == "success"}
    wanted = {(s["competitor"], s["seed"], s["threads"]) for s in specs}
    return len(specs) == 35 and found == wanted


class Controller:
    def __init__(self, args):
        self.args = args
        session = boto3.Session(profile_name=args.profile, region_name="us-east-1")
        config = Config(retries={"total_max_attempts": 3, "mode": "standard"},
                        connect_timeout=5, read_timeout=20)
        self.s3, self.ecs, self.asg, self.ec2 = [session.client(name, config=config)
            for name in ("s3", "ecs", "autoscaling", "ec2")]
        self.directory = Path(args.directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.state_path = self.directory / "controller.json"
        self.state = json.loads(self.state_path.read_text()) if self.state_path.exists() else {"stages": {}}
        self.results = self.directory / "results"
        self.report = self.directory / "report"
        self.last_report = 0

    def save(self):
        atomic_json(self.state_path, self.state)

    def summary(self, message, notify=False):
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        text = f"{now} | {message}"
        (self.directory / "status.txt").write_text(text + "\n")
        print(text, flush=True)
        if notify or time.monotonic() - self.last_report >= 1800:
            with (self.directory / "updates.txt").open("a") as handle:
                handle.write(text + "\n")
            if self.args.notify:
                # Local desktop notification only; no email/chat/API/model call.
                try:
                    subprocess.run(["osascript", "-e", "on run argv", "-e",
                        'display notification (item 1 of argv) with title "Bankai benchmark"',
                        "-e", "end run", message], check=False, timeout=10,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except (OSError, subprocess.TimeoutExpired):
                    pass  # Desktop delivery is optional; the local report is retained.
            self.last_report = time.monotonic()

    def sync(self):
        prefix = self.args.experiment + "-quality/"
        for page in self.s3.get_paginator("list_objects_v2").paginate(Bucket=self.args.bucket, Prefix=prefix):
            for item in page.get("Contents", []):
                key = item["Key"]
                if not key.endswith(".json") or ".." in Path(key).parts:
                    continue
                target = self.results / key
                if not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    temporary = target.with_suffix(".download")
                    self.s3.download_file(self.args.bucket, key, str(temporary))
                    temporary.replace(target)
        return validated_results(self.results)

    def group(self, name):
        groups = self.asg.describe_auto_scaling_groups(AutoScalingGroupNames=[name])["AutoScalingGroups"]
        if len(groups) != 1:
            raise RuntimeError(f"Expected one ASG: {name}")
        return groups[0]

    def wait_empty(self, name):
        deadline = time.monotonic() + 600
        while self.group(name).get("Instances"):
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Previous fleet has not terminated: {name}")
            time.sleep(30)

    def assert_idle_cluster(self):
        tasks = []
        for page in self.ecs.get_paginator("list_tasks").paginate(cluster=self.args.cluster):
            tasks.extend(page["taskArns"])
        if tasks:
            raise RuntimeError("Cluster has other tasks; refusing overlapping paid capacity")
        # ASG removal can precede EC2 termination; enforce no overlap in billable hosts.
        pages = self.ec2.get_paginator("describe_instances").paginate(Filters=[
            {"Name": "tag:Name", "Values": [self.args.experiment, self.args.experiment + "-*"]},
            {"Name": "instance-state-name", "Values": ["pending", "running", "stopping", "shutting-down"]}])
        if any(r.get("Instances") for page in pages for r in page["Reservations"]):
            raise RuntimeError("Previous campaign EC2 host still exists; refusing overlap")

    def start(self, dataset, source):
        self.assert_idle_cluster()
        validate_policy()
        name = f"{self.args.experiment}-{dataset}"
        stage = {"fleet": name, "status": "preparing", "dataset": dataset}
        self.state["stages"][dataset] = stage
        self.save()  # A failed/reserved attempt must never be silently relaunched.
        self.asg.create_auto_scaling_group(AutoScalingGroupName=name,
            MinSize=0, MaxSize=1, DesiredCapacity=0,
            LaunchTemplate={k: source["LaunchTemplate"][k] for k in ("LaunchTemplateId", "Version")},
            VPCZoneIdentifier=source["VPCZoneIdentifier"],
            NewInstancesProtectedFromScaleIn=False,
            Tags=[{"Key": "Name", "Value": name, "PropagateAtLaunch": True}])
        reserve(self.s3, self.args.bucket, name)
        shutdown = arm(self.asg, name)
        stage.update(status="starting", shutdown_at=shutdown.isoformat(), reserved_brl="20")
        self.save()
        self.asg.update_auto_scaling_group(AutoScalingGroupName=name, DesiredCapacity=1)
        deadline = time.monotonic() + 600
        while True:
            hosts = self.ecs.list_container_instances(cluster=self.args.cluster, status="ACTIVE")["containerInstanceArns"]
            instances = self.ecs.describe_container_instances(cluster=self.args.cluster,
                containerInstances=hosts)["containerInstances"] if hosts else []
            own = {i["InstanceId"] for i in self.group(name).get("Instances", [])}
            ready = [i for i in instances if i["ec2InstanceId"] in own and i.get("agentConnected")]
            if ready:
                resources = {r["name"]: r.get("integerValue", 0) for r in ready[0]["remainingResources"]}
                if len(ready) != 1 or resources.get("CPU", 0) < 16384 or resources.get("MEMORY", 0) < 28672:
                    raise RuntimeError("Unexpected ECS registration")
                break
            if time.monotonic() >= deadline:
                raise TimeoutError("ECS registration timeout")
            time.sleep(15)
        barrier = f"{self.args.experiment}/control/{dataset}-{time.time_ns()}.json"
        response = self.ecs.run_task(cluster=self.args.cluster,
            taskDefinition=self.args.task_definition, count=1, launchType="EC2",
            placementConstraints=[{"type": "distinctInstance"}, {"type": "memberOf",
                "expression": "attribute:ecs.instance-type == c7i.4xlarge"}],
            overrides={"containerOverrides": [{"name": "benchmark", "command": [
                "full", "--suite", "quality", "--dataset", dataset,
                "--experiment", self.args.experiment, "--bucket", self.args.bucket,
                "--region", "us-east-1"], "environment": [
                    {"name": "BENCHMARK_BARRIER_BUCKET", "value": self.args.bucket},
                    {"name": "BENCHMARK_BARRIER_KEY", "value": barrier}]}]})
        stage["tasks"] = [t["taskArn"] for t in response.get("tasks", [])]
        self.save()
        if response.get("failures") or len(stage["tasks"]) != 1:
            raise RuntimeError(f"ECS launch failed: {response.get('failures')}")
        deadline = time.monotonic() + 600
        while True:
            task = self.ecs.describe_tasks(cluster=self.args.cluster, tasks=stage["tasks"])["tasks"][0]
            if task["lastStatus"] == "STOPPED":
                raise RuntimeError(f"ECS stopped before barrier: {task.get('stoppedReason')}")
            if task["lastStatus"] == "RUNNING":
                if task["containerInstanceArn"] != ready[0]["containerInstanceArn"]:
                    raise RuntimeError("Task placed on unexpected host")
                break
            if time.monotonic() >= deadline:
                raise TimeoutError("ECS task start timeout")
            time.sleep(15)
        stage.update(status="running", instances={ready[0]["containerInstanceArn"]: ready[0]["ec2InstanceId"]},
            task_instances={stage["tasks"][0]: ready[0]["ec2InstanceId"]},
            image=self.args.image, logs=f"/bankai/{self.args.cluster}", barrier=barrier,
            budget={"reserved_brl": "20", "shutdown_at": shutdown.isoformat(), "ledger_bucket": self.args.bucket})
        self.save()
        self.s3.put_object(Bucket=self.args.bucket, Key=barrier, Body=json.dumps(stage).encode())
        self.summary(f"{dataset}: iniciado; reserva R$20; corte {shutdown:%H:%M UTC}", notify=True)
        return stage

    def monitor(self, dataset, stage):
        shutdown = datetime.fromisoformat(stage["shutdown_at"])
        while True:
            results, expected, issues = self.sync()
            counts = Counter(r["status"] for r in results if r["dataset"] == dataset)
            self.summary(f"{dataset}: {counts['success']}/35; falhas {sum(v for k,v in counts.items() if k != 'success')}")
            response = self.ecs.describe_tasks(cluster=self.args.cluster, tasks=stage["tasks"])
            if response.get("failures") or len(response["tasks"]) != 1:
                raise RuntimeError("ECS task status unavailable")
            task = response["tasks"][0]
            if task["lastStatus"] == "STOPPED":
                if not successful_exit(task) or not dataset_complete(results, expected, dataset):
                    raise RuntimeError(f"{dataset} stopped/incomplete: {task.get('stoppedReason')}; {dict(counts)}")
                stage.update(status="complete", completed_at=datetime.now(timezone.utc).isoformat())
                self.save()
                self.summary(f"{dataset}: 35/35 OK; desligando host", notify=True)
                return
            if any(k != "success" and v for k, v in counts.items()):
                raise RuntimeError(f"Trial failure; campaign halted: {dict(counts)}")
            if datetime.now(timezone.utc) >= shutdown:
                raise TimeoutError(f"{dataset}: one-hour deadline reached; no automatic retry")
            time.sleep(60)

    def cleanup(self, stage):
        stop(self.asg, stage["fleet"])
        for task in stage.get("tasks", []):
            described = self.ecs.describe_tasks(cluster=self.args.cluster, tasks=[task])
            if any(t["lastStatus"] != "STOPPED" for t in described.get("tasks", [])):
                self.ecs.stop_task(cluster=self.args.cluster, task=task, reason="Budget-controlled quality shard finished or failed")
        self.wait_empty(stage["fleet"])

    def run(self):
        source = self.group(self.args.source_fleet)
        if not str(source["LaunchTemplate"]["Version"]).isdigit():
            raise RuntimeError("Source launch-template version must be pinned")
        definition = self.ecs.describe_task_definition(taskDefinition=self.args.task_definition)["taskDefinition"]
        if definition["containerDefinitions"][0]["image"] != self.args.image or "@sha256:" not in self.args.image:
            raise RuntimeError("Immutable image verification failed")
        results, expected, _ = self.sync()
        if not dataset_complete(results, expected, "industrial"):
            raise RuntimeError("Industrial pilot is not complete")
        # Initial pilot has finished; remove idle paid capacity before next shard.
        if self.ecs.list_tasks(cluster=self.args.cluster)["taskArns"]:
            raise RuntimeError("Cluster still busy; leaving it untouched")
        stop(self.asg, self.args.source_fleet)
        self.wait_empty(self.args.source_fleet)
        for dataset in DATASETS:
            results, expected, _ = self.sync()
            if dataset_complete(results, expected, dataset):
                continue
            if dataset in self.state["stages"]:
                raise RuntimeError(f"{dataset} has a prior attempt; manual review required, no duplicate launch")
            try:
                stage = self.start(dataset, source)
                self.monitor(dataset, stage)
            finally:
                stage = self.state["stages"].get(dataset)
                if stage:
                    self.cleanup(stage)
            # EC2 may briefly remain shutting-down after its ASG removes it.
            deadline = time.monotonic() + 300
            while True:
                try:
                    self.assert_idle_cluster()
                    break
                except RuntimeError:
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(30)
        self.sync()
        aggregate(self.results, self.report, provisional=True)
        self.summary("Qualidade: 140/140 OK; todos os hosts desligados. Relatorios locais prontos.", notify=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("profile", "bucket", "experiment", "cluster", "source-fleet", "task-definition", "image", "directory"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--notify", action="store_true")
    args = parser.parse_args()
    directory = Path(args.directory)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "controller.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        controller = Controller(args)
        try:
            controller.run()
        except Exception as exc:
            # No auto-restart/reservation: AWS shutdown stays armed if local auth fails.
            controller.summary(f"PARADO para revisao: {type(exc).__name__}: {exc}", notify=True)
            raise


if __name__ == "__main__":
    main()
