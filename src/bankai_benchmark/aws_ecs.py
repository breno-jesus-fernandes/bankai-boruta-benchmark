"""Offline deployment planning and explicit AWS resource lifecycle."""
import argparse
import json
from pathlib import Path
import re
import time
from .config import atomic_json, PROFILES

AMI_PARAMETER = "/aws/service/ecs/optimized-ami/amazon-linux-2023/recommended/image_id"


def ref(name): return {"Ref": name}
def attr(name, attribute): return {"Fn::GetAtt": [name, attribute]}
def sub(value): return {"Fn::Sub": value}


def infrastructure(experiment, bucket, subnets, security_groups):
    if not re.fullmatch(r"[a-z][a-z0-9-]{2,40}", experiment):
        raise ValueError("experiment must match [a-z][a-z0-9-]{2,40}")
    resources = {}
    def resource(name, kind, **properties):
        resources[name] = dict(Type="AWS::"+kind, Properties=properties)
    def role(name, service, policies=None, managed=None):
        resource(name, "IAM::Role", AssumeRolePolicyDocument=dict(Version="2012-10-17", Statement=[dict(Effect="Allow", Principal={"Service": service}, Action="sts:AssumeRole")]), ManagedPolicyArns=managed or [], Policies=policies or [])
    resource("Repository", "ECR::Repository", RepositoryName=experiment, ImageTagMutability="IMMUTABLE", EmptyOnDelete=True, ImageScanningConfiguration=dict(ScanOnPush=True))
    resource("Cluster", "ECS::Cluster", ClusterName=experiment)
    resource("Logs", "Logs::LogGroup", LogGroupName=f"/bankai/{experiment}", RetentionInDays=1)
    role("InstanceRole", "ec2.amazonaws.com", managed=["arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role"])
    role("ExecutionRole", "ecs-tasks.amazonaws.com", managed=["arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"])
    prefixes = [experiment+"/", experiment+"-quality/", experiment+"-scaling/"]
    statements = [dict(Effect="Allow", Action=["s3:GetObject", "s3:PutObject"], Resource=[f"arn:aws:s3:::{bucket}/{prefix}*" for prefix in prefixes]),
        dict(Effect="Allow", Action=["s3:ListBucket"], Resource=f"arn:aws:s3:::{bucket}", Condition={"StringLike": {"s3:prefix": [prefix+"*" for prefix in prefixes]}})]
    role("TaskRole", "ecs-tasks.amazonaws.com", policies=[dict(PolicyName="ExperimentResults", PolicyDocument=dict(Version="2012-10-17", Statement=statements))])
    resource("InstanceProfile", "IAM::InstanceProfile", Roles=[ref("InstanceRole")])
    resource("LaunchTemplate", "EC2::LaunchTemplate", LaunchTemplateData=dict(ImageId=ref("EcsAmi"), InstanceType="c7i.4xlarge",
        IamInstanceProfile={"Arn": attr("InstanceProfile", "Arn")}, SecurityGroupIds=security_groups,
        MetadataOptions=dict(HttpTokens="required", HttpPutResponseHopLimit=2),
        BlockDeviceMappings=[dict(DeviceName="/dev/xvda", Ebs=dict(VolumeSize=100, VolumeType="gp3", Encrypted=True, DeleteOnTermination=True))],
        UserData={"Fn::Base64": sub("#!/bin/bash\necho ECS_CLUSTER=${Cluster} >> /etc/ecs/ecs.config\n")}))
    resource("Fleet", "AutoScaling::AutoScalingGroup", MinSize="0", MaxSize="1", DesiredCapacity="0", NewInstancesProtectedFromScaleIn=False, VPCZoneIdentifier=subnets,
        LaunchTemplate=dict(LaunchTemplateId=ref("LaunchTemplate"), Version=attr("LaunchTemplate", "LatestVersionNumber")),
        Tags=[dict(Key="Name", Value=experiment, PropagateAtLaunch=True)])
    resource("CapacityProvider", "ECS::CapacityProvider", Name=experiment, AutoScalingGroupProvider=dict(AutoScalingGroupArn=ref("Fleet"), ManagedScaling=dict(Status="DISABLED"), ManagedTerminationProtection="DISABLED", ManagedDraining="DISABLED"))
    resource("Association", "ECS::ClusterCapacityProviderAssociations", Cluster=ref("Cluster"), CapacityProviders=[ref("CapacityProvider")], DefaultCapacityProviderStrategy=[dict(CapacityProvider=ref("CapacityProvider"), Weight=1)])
    return dict(AWSTemplateFormatVersion="2010-09-09", Description="Budget-limited benchmark pilot; capacity remains zero until AWS shutdown is verified.", Metadata={"AWSToolsMetrics": {"AWSAgentToolkit": "aws-cloudformation@3"}, "com.aws.cloudformation.Context": {"ref": ["README.md", "BUDGET.md"]}}, Parameters=dict(EcsAmi=dict(Type="AWS::SSM::Parameter::Value<AWS::EC2::Image::Id>", Default=AMI_PARAMETER)),
        Resources=resources, Outputs={name: {"Value": value} for name, value in dict(Cluster=ref("Cluster"), CapacityProvider=ref("CapacityProvider"),
            Fleet=ref("Fleet"), Repository=attr("Repository", "RepositoryUri"), ExecutionRole=attr("ExecutionRole", "Arn"), TaskRole=attr("TaskRole", "Arn"), Logs=ref("Logs")).items()})


def task_definition(experiment, image, region, outputs):
    if not re.fullmatch(r"[^\s@]+@sha256:[0-9a-f]{64}", image):
        raise ValueError("Image must be repository@sha256:digest")
    return dict(family=experiment, requiresCompatibilities=["EC2"], networkMode="bridge", cpu="16384", memory="28672",
        executionRoleArn=outputs["ExecutionRole"], taskRoleArn=outputs["TaskRole"], runtimePlatform=dict(cpuArchitecture="X86_64", operatingSystemFamily="LINUX"),
        containerDefinitions=[dict(name="benchmark", image=image, essential=True, cpu=16384, memory=28672,
            entryPoint=["/app/.venv/bin/python", "-m", "bankai_benchmark.ecs_entrypoint"],
            environment=[dict(name="BENCHMARK_IMAGE_DIGEST", value=image)],
            logConfiguration=dict(logDriver="awslogs", options={"awslogs-group": outputs["Logs"], "awslogs-region": region, "awslogs-stream-prefix": "benchmark"}))])


def commands(experiment, bucket, region):
    return [["full", "--suite", "quality", "--dataset", dataset, "--experiment", experiment, "--bucket", bucket, "--region", region] for dataset in PROFILES] + [
        ["full", "--suite", "scaling", "--dataset", "industrial", "--experiment", experiment, "--bucket", bucket, "--region", region]]


def verify_hosts(tasks):
    if len(tasks) != 1 or any(task.get("lastStatus") != "RUNNING" for task in tasks):
        raise RuntimeError("One pilot task must be running before releasing the barrier")
    hosts = [task.get("containerInstanceArn") for task in tasks]
    if None in hosts or len(set(hosts)) != 1:
        raise RuntimeError("Pilot must occupy one host")
    return hosts


def outputs_for(cf, name):
    return {item["OutputKey"]: item["OutputValue"] for item in cf.describe_stacks(StackName=name)["Stacks"][0]["Outputs"]}


def launch(ecs, s3, outputs, state, experiment, bucket, region, *, autoscaling, dataset="industrial"):
    from .budget import reserve, arm, stop, validate_policy
    validate_policy()
    if region != "us-east-1":
        raise ValueError("Budget policy permits us-east-1 only")
    if dataset not in PROFILES:
        raise ValueError("Unknown pilot dataset")
    if state.get("tasks"):
        raise RuntimeError("Tasks already recorded; use a new experiment/state")
    reserve(s3, bucket, outputs["Fleet"])
    shutdown = arm(autoscaling, outputs["Fleet"])
    state["budget"] = dict(reserved_brl="20", shutdown_at=shutdown.isoformat(), ledger_bucket=bucket)
    barrier = f"{experiment}/control/{time.time_ns()}.json"
    tasks = []
    try:
        autoscaling.update_auto_scaling_group(AutoScalingGroupName=outputs["Fleet"], MinSize=0, MaxSize=1, DesiredCapacity=1)
        readiness = time.monotonic() + 600
        while not ecs.list_container_instances(cluster=outputs["Cluster"], status="ACTIVE")["containerInstanceArns"]:
            if time.monotonic() >= readiness:
                raise TimeoutError("Budget pilot instance registration timeout")
            time.sleep(5)
        command = next(command for command in commands(experiment, bucket, region) if command[2] == "quality" and command[4] == dataset)
        response = ecs.run_task(cluster=outputs["Cluster"], taskDefinition=state["task_definition"], count=1,
            capacityProviderStrategy=[dict(capacityProvider=outputs["CapacityProvider"], weight=1)],
            placementConstraints=[dict(type="distinctInstance"), dict(type="memberOf", expression="attribute:ecs.instance-type == c7i.4xlarge")],
            overrides=dict(containerOverrides=[dict(name="benchmark", command=command, environment=[dict(name="BENCHMARK_BARRIER_BUCKET", value=bucket), dict(name="BENCHMARK_BARRIER_KEY", value=barrier)])]))
        if response.get("failures"):
            raise RuntimeError(response["failures"])
        tasks.extend(task["taskArn"] for task in response["tasks"])
        deadline = time.monotonic()+900
        while True:
            described = ecs.describe_tasks(cluster=outputs["Cluster"], tasks=tasks)["tasks"]
            if any(task["lastStatus"] == "STOPPED" for task in described):
                raise RuntimeError("Task stopped before launch barrier")
            if len(described) == 1 and all(task["lastStatus"] == "RUNNING" for task in described):
                hosts = verify_hosts(described); break
            if time.monotonic() > deadline:
                raise TimeoutError("Pilot launch timeout")
            time.sleep(5)
        instances = ecs.describe_container_instances(cluster=outputs["Cluster"], containerInstances=hosts)["containerInstances"]
        identities = {item["containerInstanceArn"]: item["ec2InstanceId"] for item in instances}
        state.update(tasks=tasks, instances=identities, task_instances={task["taskArn"]: identities[task["containerInstanceArn"]] for task in described}, barrier=barrier, logs=outputs["Logs"])
        s3.put_object(Bucket=bucket, Key=barrier, Body=json.dumps(state).encode())
        return state
    except Exception:
        try:
            stop(autoscaling, outputs["Fleet"])
        finally:
            for task in tasks:
                ecs.stop_task(cluster=outputs["Cluster"], task=task, reason="Failed benchmark launch barrier")
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("plan", "provision", "register", "launch", "status", "destroy"))
    parser.add_argument("--region", required=True); parser.add_argument("--bucket", required=True)
    parser.add_argument("--experiment", required=True); parser.add_argument("--subnets", nargs="+", required=True)
    parser.add_argument("--security-groups", nargs="+", required=True); parser.add_argument("--image")
    parser.add_argument("--state", default="aws-state.json")
    parser.add_argument("--dataset", choices=list(PROFILES), default="industrial")
    args = parser.parse_args()
    if args.action in ("provision", "launch") and args.region != "us-east-1":
        raise ValueError("Budget policy permits us-east-1 only")
    template = infrastructure(args.experiment, args.bucket, args.subnets, args.security_groups)
    if args.action == "plan":
        fake_outputs = dict(ExecutionRole="${ExecutionRole}", TaskRole="${TaskRole}", Logs=f"/bankai/{args.experiment}")
        definition = task_definition(args.experiment, args.image, args.region, fake_outputs) if args.image else None
        print(json.dumps(dict(template=template, task_definition=definition, commands=[command for command in commands(args.experiment, args.bucket, args.region) if command[2] == "quality" and command[4] == args.dataset], budget=dict(total_brl=200, reserve_brl=40, pilot_reserved_brl=20, max_instances=1, shutdown_seconds=3600), reservations=dict(cpu=16384, memory_mib=28672),
            constraints=[dict(type="distinctInstance"), dict(type="memberOf", expression="attribute:ecs.instance-type == c7i.4xlarge")]), indent=2)); return
    import boto3
    session = boto3.Session(region_name=args.region); cf, ecs = session.client("cloudformation"), session.client("ecs")
    name = "bankai-"+args.experiment
    if args.action == "provision":
        response = cf.create_stack(StackName=name, TemplateBody=json.dumps(template), Capabilities=["CAPABILITY_IAM"])
        atomic_json(args.state, dict(stack=response["StackId"], experiment=args.experiment)); print(response["StackId"]); return
    outputs = outputs_for(cf, name)
    if args.action == "destroy":
        for page in ecs.get_paginator("list_tasks").paginate(cluster=outputs["Cluster"]):
            for task in page["taskArns"]:
                ecs.stop_task(cluster=outputs["Cluster"], task=task, reason="Explicit benchmark teardown")
        cf.delete_stack(StackName=name); print("Deletion requested; result bucket retained"); return
    path = Path(args.state); state = json.loads(path.read_text()) if path.exists() else {}
    if args.action == "register":
        definition = task_definition(args.experiment, args.image or "", args.region, outputs)
        repository, image_hash = args.image.split("@")
        registry, repository_name = repository.split("/", 1)
        session.client("ecr").describe_images(registryId=registry.split(".")[0], repositoryName=repository_name, imageIds=[{"imageDigest": image_hash}])
        response = ecs.register_task_definition(**definition)
        state.update(task_definition=response["taskDefinition"]["taskDefinitionArn"], image=args.image)
    elif args.action == "launch":
        from .orchestrator import require_public_release
        require_public_release()
        if not state.get("task_definition"):
            raise ValueError("Register the immutable image first")
        state = launch(ecs, session.client("s3"), outputs, state, args.experiment, args.bucket, args.region, autoscaling=session.client("autoscaling"), dataset=args.dataset)
    else:
        tasks = ecs.describe_tasks(cluster=outputs["Cluster"], tasks=state["tasks"])["tasks"] if state.get("tasks") else []
        # AWS response dates are not JSON-native.
        print(json.dumps(dict(state=state, tasks=tasks), indent=2, default=str)); return
    atomic_json(path, state)


if __name__ == "__main__":
    main()
