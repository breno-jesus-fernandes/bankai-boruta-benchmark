"""Paid capacity cannot start before a reservation AND verified AWS deadline."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

spec = importlib.util.spec_from_file_location("quality_controller", Path(__file__).parents[1] / "scripts/continue_quality.py")
controller_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(controller_module)


def bare_controller(tmp_path):
    controller = controller_module.Controller.__new__(controller_module.Controller)
    controller.args = SimpleNamespace(experiment="pilot-test", bucket="bucket", cluster="cluster")
    controller.state = {"stages": {}}
    controller.state_path = tmp_path / "controller.json"
    controller.asg = Mock()
    controller.s3 = Mock()
    controller.ecs = Mock()
    controller.assert_idle_cluster = Mock()
    return controller


@pytest.mark.parametrize("failure", ["reserve", "arm"])
def test_failed_budget_gate_never_starts_paid_capacity(tmp_path, monkeypatch, failure):
    controller = bare_controller(tmp_path)
    monkeypatch.setattr(controller_module, "reserve", Mock())
    monkeypatch.setattr(controller_module, "arm", Mock())
    getattr(controller_module, failure).side_effect = RuntimeError("budget gate rejected")
    source = {"LaunchTemplate": {"LaunchTemplateId": "lt-id", "Version": "1"}, "VPCZoneIdentifier": "subnet-id"}
    with pytest.raises(RuntimeError, match="budget gate rejected"):
        controller.start("credito", source)
    request = controller.asg.create_auto_scaling_group.call_args.kwargs
    assert request["DesiredCapacity"] == 0 and request["MaxSize"] == 1
    controller.asg.update_auto_scaling_group.assert_not_called()
    controller.ecs.run_task.assert_not_called()
    assert controller.state["stages"]["credito"]["status"] == "preparing"


def test_busy_cluster_prevents_even_creating_another_fleet(tmp_path):
    controller = bare_controller(tmp_path)
    controller.assert_idle_cluster.side_effect = RuntimeError("cluster busy")
    with pytest.raises(RuntimeError, match="cluster busy"):
        controller.start("credito", {})
    controller.asg.create_auto_scaling_group.assert_not_called()


def test_full_seed_grid_required_before_advancing():
    expected = [{"dataset": "credito", "competitor": str(m), "seed": s, "threads": 16}
                for m in range(7) for s in range(42, 47)]
    results = [dict(row, status="success") for row in expected]
    assert controller_module.dataset_complete(results, expected, "credito")
    assert not controller_module.dataset_complete(results[:-1], expected, "credito")
    results[-1]["status"] = "timeout"
    assert not controller_module.dataset_complete(results, expected, "credito")


def test_zero_exit_with_missing_result_is_not_success(tmp_path):
    controller = bare_controller(tmp_path)
    controller.sync = Mock(return_value=([], [], []))
    controller.summary = Mock()
    controller.ecs.describe_tasks.return_value = {"tasks": [{"lastStatus": "STOPPED", "containers": [{"exitCode": 0}]}]}
    with pytest.raises(RuntimeError, match="stopped/incomplete"):
        controller.monitor("credito", {"shutdown_at": "2099-01-01T00:00:00+00:00", "tasks": ["task"]})


def test_cleanup_zeros_fleet_and_stops_running_task_before_waiting(tmp_path, monkeypatch):
    controller = bare_controller(tmp_path)
    stop = Mock()
    monkeypatch.setattr(controller_module, "stop", stop)
    controller.wait_empty = Mock()
    controller.ecs.describe_tasks.return_value = {"tasks": [{"lastStatus": "RUNNING"}]}
    controller.cleanup({"fleet": "fleet", "tasks": ["task"]})
    stop.assert_called_once_with(controller.asg, "fleet")
    controller.ecs.stop_task.assert_called_once()
    controller.wait_empty.assert_called_once_with("fleet")


def resume_controller(tmp_path):
    from datetime import datetime, timezone
    controller = bare_controller(tmp_path)
    controller.args.task_definition = "definition"
    stage = {"fleet": "fleet", "status": "running", "tasks": ["task"],
             "shutdown_at": "2099-01-01T00:00:00+00:00"}
    controller.state["stages"]["bioinformatica"] = stage
    controller.asg.describe_scheduled_actions.return_value = {"ScheduledUpdateGroupActions": [
        {"StartTime": datetime(2099, 1, 1, tzinfo=timezone.utc),
         "MinSize": 0, "MaxSize": 0, "DesiredCapacity": 0}]}
    controller.ecs.get_paginator.return_value.paginate.return_value = [{"taskArns": ["task"]}]
    controller.ecs.describe_tasks.return_value = {"tasks": [{"lastStatus": "RUNNING", "taskDefinitionArn": "definition"}]}
    controller.monitor = Mock()
    controller.cleanup = Mock()
    controller.summary = Mock()
    return controller, stage


def test_resume_reuses_task_without_new_capacity_or_deadline_changes(tmp_path):
    controller, stage = resume_controller(tmp_path)
    controller.resume("bioinformatica")
    controller.monitor.assert_called_once_with("bioinformatica", stage)
    controller.cleanup.assert_called_once_with(stage)
    controller.ecs.run_task.assert_not_called()
    controller.asg.create_auto_scaling_group.assert_not_called()
    controller.asg.put_scheduled_update_group_action.assert_not_called()


def test_resume_rejects_mismatched_aws_deadline_before_touching_task(tmp_path):
    controller, _ = resume_controller(tmp_path)
    controller.asg.describe_scheduled_actions.return_value["ScheduledUpdateGroupActions"][0]["MaxSize"] = 1
    with pytest.raises(RuntimeError, match="armed AWS shutdown"):
        controller.resume("bioinformatica")
    controller.monitor.assert_not_called()
    controller.cleanup.assert_not_called()


def test_resume_monitor_failure_still_cleans_up(tmp_path):
    controller, stage = resume_controller(tmp_path)
    controller.monitor.side_effect = TimeoutError("deadline")
    with pytest.raises(TimeoutError):
        controller.resume("bioinformatica")
    controller.cleanup.assert_called_once_with(stage)
