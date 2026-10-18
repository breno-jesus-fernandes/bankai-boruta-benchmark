from datetime import datetime, timezone
from io import BytesIO
import json
import pytest
from bankai_benchmark.budget import reserve, arm, PILOT_SECONDS, TOTAL_BRL


class S3:
    class exceptions:
        class NoSuchKey(Exception): pass
    def __init__(self): self.data = None; self.version = 0
    def get_object(self, **kwargs):
        if self.data is None: raise self.exceptions.NoSuchKey()
        return dict(Body=BytesIO(self.data), ETag=str(self.version))
    def put_object(self, **kwargs):
        if self.data is None: assert kwargs['IfNoneMatch'] == '*'
        else: assert kwargs['IfMatch'] == str(self.version)
        self.version += 1
        self.data = kwargs['Body']


def test_cumulative_campaign_limit_and_no_refunds():
    s3 = S3()
    assert TOTAL_BRL == 260
    for index in range(11): reserve(s3, 'bucket', f'fleet{index}')
    assert len(json.loads(s3.data)['launches']) == 11
    with pytest.raises(RuntimeError, match='exhausted'): reserve(s3, 'bucket', 'fleet11')
    assert s3.version == 11
    with pytest.raises(RuntimeError, match='already reserved'): reserve(s3, 'bucket', 'fleet0')


class ASG:
    def __init__(self):
        self.group = dict(MinSize=0, MaxSize=1, DesiredCapacity=0, Instances=[])
        self.action = None
        self.corrupt = False
    def describe_auto_scaling_groups(self, **kwargs): return dict(AutoScalingGroups=[self.group])
    def describe_scheduled_actions(self, **kwargs):
        action = dict(self.action) if self.action else None
        if action and self.corrupt: action['MaxSize'] = 1
        return dict(ScheduledUpdateGroupActions=[action] if action else [])
    def put_scheduled_update_group_action(self, **kwargs): self.action = kwargs


def test_aws_shutdown_sets_all_capacity_limits_to_zero():
    client = ASG(); now = datetime.now(timezone.utc).replace(microsecond=0)
    deadline = arm(client, 'fleet', now)
    assert (deadline-now).total_seconds() == PILOT_SECONDS
    assert [client.action[k] for k in ('MinSize','MaxSize','DesiredCapacity')] == [0,0,0]
    with pytest.raises(RuntimeError, match='already has scheduled'): arm(client, 'fleet')


@pytest.mark.parametrize('field,value', [('NewInstancesProtectedFromScaleIn',True),('MinSize',1),('MaxSize',5),('DesiredCapacity',1),('SuspendedProcesses',[{'ProcessName':'ScheduledActions'}]),('Instances',[{}])])
def test_unsafe_fleet_is_rejected(field, value):
    client = ASG(); client.group[field] = value
    with pytest.raises(RuntimeError): arm(client, 'fleet')
    assert client.action is None


def test_readback_failure_blocks_activation():
    client = ASG(); client.corrupt = True
    with pytest.raises(RuntimeError, match='verification failed'): arm(client, 'fleet')


def test_expired_deadline_is_rejected():
    with pytest.raises(RuntimeError, match='expired'):
        arm(ASG(), 'fleet', datetime(2020,1,1,tzinfo=timezone.utc))


def test_ledger_conflict_does_not_retry_or_activate():
    class Conflict(S3):
        def put_object(self, **kwargs): raise RuntimeError('PreconditionFailed')
    with pytest.raises(RuntimeError, match='PreconditionFailed'):
        reserve(Conflict(), 'bucket', 'fleet')


def test_launch_cannot_start_without_verified_shutdown(monkeypatch):
    from bankai_benchmark.aws_ecs import launch
    from bankai_benchmark import budget
    monkeypatch.setattr(budget, 'reserve', lambda *args: None)
    client = ASG(); client.corrupt = True
    # ASG has deliberately no update method; ECS/S3 have no launch methods.
    with pytest.raises(RuntimeError, match='verification failed'):
        launch(object(), object(), {'Fleet':'fleet'}, {}, 'pilot', 'bucket', 'us-east-1', autoscaling=client)


def test_launch_rejects_other_regions_before_any_aws_calls():
    from bankai_benchmark.aws_ecs import launch
    with pytest.raises(ValueError, match='us-east-1'):
        launch(object(), object(), {}, {}, 'pilot', 'bucket', 'sa-east-1', autoscaling=object())


def test_expired_cost_policy_blocks_launch():
    from bankai_benchmark.budget import validate_policy, POLICY_EXPIRES
    with pytest.raises(RuntimeError, match='policy expired'): validate_policy(POLICY_EXPIRES)


def test_corrupt_reservation_blocks_budget_reuse():
    s3 = S3(); reserve(s3, 'bucket', 'fleet')
    ledger = json.loads(s3.data)
    ledger['launches']['fleet']['reserved_brl'] = '-20'
    s3.data = json.dumps(ledger).encode()
    with pytest.raises(RuntimeError, match='Corrupt'): reserve(s3, 'bucket', 'new-fleet')


def test_approved_budget_increase_migrates_and_reserves_atomically():
    s3 = S3()
    ledger = {'schema_version': 1, 'total_brl': '240', 'reserve_brl': '40',
              'launches': {f'old-{i}': {'reserved_brl': '20', 'reserved_at': 'old'} for i in range(10)}}
    s3.data = json.dumps(ledger).encode()
    reserve(s3, 'bucket', 'r4-smoke-fleet')
    updated = json.loads(s3.data)
    assert updated['total_brl'] == '260' and len(updated['launches']) == 11
