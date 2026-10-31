from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

pytest.importorskip('boto3')
from botocore.exceptions import ClientError  # noqa: E402

SCRIPTS = Path(__file__).parents[1]/'scripts'
spec = importlib.util.spec_from_file_location('runner', SCRIPTS/'run_native_shadow_aws.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
OUTPUTS = dict(ExecutionRole='execution', TaskRole='task', Logs='/bankai/x', Cluster='cluster', Fleet='fleet')
EXPIRED = ClientError({'Error': {'Code': 'ExpiredTokenException'}}, 'DescribeTasks')


class FakeAws(runner.Aws):
    """Aws whose sessions hand out the given mocks; each renew moves to the next set."""

    def __init__(self, *sessions):
        self.sessions = list(sessions)
        super().__init__(wait_seconds=0)

    def renew(self):
        self.clients = self.sessions.pop(0) if self.sessions else self.clients


def state(tmp_path, **extra):
    now = datetime.now(timezone.utc)
    value = dict(outputs=OUTPUTS, task='arn:aws:ecs:us-east-1:1:task/cluster/abc', threads=[8, 64], seeds=[42],
        datasets=['industrial'], scale=2, started_at=(now - timedelta(minutes=5)).isoformat(),
        shutdown_at=(now + timedelta(hours=1)).isoformat(), status='running', **extra)
    path = tmp_path/'state.json'
    path.write_text(json.dumps(value))
    return value, path


def clients(tasks, keys=(), events=()):
    ecs, s3, logs, autoscaling = Mock(), Mock(), Mock(), Mock()
    ecs.describe_tasks.return_value = {'tasks': tasks}
    s3.get_paginator.return_value.paginate.return_value = [{'Contents': [
        {'Key': key, 'Size': 1, 'LastModified': datetime.now(timezone.utc)} for key in keys]}]
    logs.filter_log_events.return_value = {'events': [{'message': message} for message in events]}
    autoscaling.describe_auto_scaling_groups.return_value = {'AutoScalingGroups': [{'Instances': [], 'DesiredCapacity': 0}]}
    return dict(ecs=ecs, s3=s3, logs=logs, autoscaling=autoscaling)


KEYS = ['native-shadow-max40-v1/pilot/r/industrial-seed42-t8-x2.json', 'native-shadow-max40-v1/pilot/r/industrial-seed42-t64-x2.json']


def test_sweep_runs_one_pilot_per_thread_count_and_auc_only_last():
    definition = runner.task_definition(OUTPUTS, 'repo@sha256:'+'a'*64, ['industrial'], ['bankai_exact'], [42],
                                        [8, 16, 32, 64], 1, 'c7a.16xlarge', 2, auc=True)
    assert (definition['cpu'], definition['memory']) == ('65536', '122880')
    container = definition['containerDefinitions'][0]
    assert container['entryPoint'] == ['sh', '-c']
    lines = container['command'][0].splitlines()
    assert lines[0] == 'set -e' and len(lines) == 5
    assert [line.split('--threads ')[1].split()[0] for line in lines[1:]] == ['8', '16', '32', '64']
    assert [line.endswith('--auc') for line in lines[1:]] == [False, False, False, True]
    single = runner.task_definition(OUTPUTS, 'repo@sha256:'+'a'*64, ['industrial'], ['bankai_exact'], [42], 16, 5)
    assert single['containerDefinitions'][0]['entryPoint'][-1] == '/opt/native_shadow_pilot.py'


def test_expired_credentials_wait_for_a_new_login():
    stale, fresh = clients([]), clients([{'lastStatus': 'STOPPED', 'stopCode': 'EssentialContainerExited',
                                          'containers': [{'exitCode': 0}]}])
    stale['ecs'].describe_tasks.side_effect = EXPIRED
    aws = FakeAws(stale, fresh)
    deadline = datetime.now(timezone.utc) + timedelta(minutes=1)
    tasks = aws.retry(lambda client: client.client('ecs').describe_tasks(cluster='c', tasks=['t'])['tasks'], deadline)
    assert tasks[0]['lastStatus'] == 'STOPPED' and aws.clients is fresh
    other = ClientError({'Error': {'Code': 'AccessDenied'}}, 'DescribeTasks')
    fresh['ecs'].describe_tasks.side_effect = other
    with pytest.raises(ClientError):
        aws.retry(lambda client: client.client('ecs').describe_tasks(cluster='c', tasks=['t']), deadline)


def test_finish_verifies_artifacts_and_drains_the_fleet(tmp_path):
    value, path = state(tmp_path)
    aws = FakeAws(clients([{'lastStatus': 'STOPPED', 'stopCode': 'EssentialContainerExited',
                            'containers': [{'exitCode': 0}]}], KEYS))
    result = runner.finish(aws, value, path)
    assert result['status'] == 'completed' and len(result['result_objects']) == 2
    aws.clients['autoscaling'].update_auto_scaling_group.assert_called_once()
    assert json.loads(path.read_text())['status'] == 'completed'


def test_a_task_forgotten_by_ecs_needs_every_pilot_success_line(tmp_path):
    success = json.dumps({'status': 'success', 'run_id': 'r'})
    value, path = state(tmp_path)
    result = runner.finish(FakeAws(clients([], KEYS, [success, success])), value, path)
    assert result['status'] == 'completed' and result['exit_source'] == 'cloudwatch-logs'
    value, path = state(tmp_path)
    aws = FakeAws(clients([], KEYS, [success]))
    with pytest.raises(RuntimeError, match='success line'):
        runner.finish(aws, value, path)
    aws.clients['autoscaling'].update_auto_scaling_group.assert_called_once()


def test_missing_artifacts_fail_the_launch(tmp_path):
    value, path = state(tmp_path)
    aws = FakeAws(clients([{'lastStatus': 'STOPPED', 'stopCode': 'EssentialContainerExited',
                            'containers': [{'exitCode': 0}]}], KEYS[:1]))
    with pytest.raises(RuntimeError, match='one result artifact'):
        runner.finish(aws, value, path)


def test_resume_refuses_states_without_a_running_task(tmp_path):
    _, path = state(tmp_path)
    data = json.loads(path.read_text())
    data['status'] = 'reserved'
    path.write_text(json.dumps(data))
    with pytest.raises(RuntimeError, match='Nothing to resume'):
        runner.resume(Mock(resume=str(path)))


def test_launch_template_targets_the_64_core_host():
    from bankai_benchmark.aws_ecs import infrastructure
    template = infrastructure('native-shadow-max40-v1', 'bucket', ['subnet'], ['sg'], runner.machine('c7a.16xlarge'))
    data = template['Resources']['LaunchTemplate']['Properties']['LaunchTemplateData']
    assert data['InstanceType'] == 'c7a.16xlarge' and data['CpuOptions'] == {'CoreCount': 64, 'ThreadsPerCore': 1}
    assert runner.INSTANCES['c7a.16xlarge']['hour_usd'] == 2*runner.INSTANCES['c7a.8xlarge']['hour_usd']
