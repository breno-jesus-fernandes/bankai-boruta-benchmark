"""Check CPU availability and wait for the controller's five-host barrier."""
import json
import os
import time
import urllib.request


def main():
    import boto3
    from botocore.exceptions import ClientError
    from .orchestrator import main as orchestrate, require_public_release
    require_public_release()
    url = os.environ.get("ECS_CONTAINER_METADATA_URI_V4")
    if not url:
        raise RuntimeError("ECS metadata endpoint required")
    with urllib.request.urlopen(url+"/task", timeout=10) as response:
        metadata = json.load(response)
    os.environ["BENCHMARK_TASK_ARN"] = metadata["TaskARN"]
    if len(os.sched_getaffinity(0)) < 16:
        raise RuntimeError("Sixteen available logical CPUs required")
    s3 = boto3.client("s3"); deadline = time.monotonic()+1200
    while True:
        try:
            response = s3.get_object(Bucket=os.environ["BENCHMARK_BARRIER_BUCKET"], Key=os.environ["BENCHMARK_BARRIER_KEY"])
            barrier = json.loads(response["Body"].read())
            if metadata["TaskARN"] not in barrier["tasks"]:
                raise RuntimeError("Task absent from controller barrier")
            os.environ["BENCHMARK_INSTANCE_ID"] = barrier["instances"].get(metadata.get("ContainerInstanceARN"), "recorded_in_controller_state")
            os.environ["BENCHMARK_LOG_LOCATION"] = barrier["logs"]+"/benchmark/benchmark/"+metadata["TaskARN"].rsplit("/", 1)[-1]
            break
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "NoSuchKey":
                raise
        if time.monotonic() >= deadline:
            raise TimeoutError("Controller barrier timeout")
        time.sleep(5)
    orchestrate()


if __name__ == "__main__":
    main()
