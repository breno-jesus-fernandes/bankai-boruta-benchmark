from datetime import datetime, timezone
from io import BytesIO
import json
import pytest
from bankai_benchmark.budget import reserve, reserve_many, arm, transfer_reservation, PILOT_SECONDS, TOTAL_BRL


class S3:
    class exceptions:
        class NoSuchKey(Exception): pass
    def __init__(self):
        self.version = 0
        self.data = json.dumps(dict(schema_version=2,total_brl='400',reserve_brl='80',launches={})).encode()
    def get_object(self, **kwargs):
        return dict(Body=BytesIO(self.data), ETag=str(self.version))
    def put_object(self, **kwargs):
        assert kwargs['IfMatch'] == str(self.version)
        self.version += 1
        self.data = kwargs['Body']


def test_cumulative_campaign_limit_and_no_refunds():
    s3 = S3()
    assert TOTAL_BRL == 400
    for index in range(16): reserve(s3, 'bucket', f'fleet{index}')
    assert len(json.loads(s3.data)['launches']) == 16
    with pytest.raises(RuntimeError, match='exhausted'): reserve(s3, 'bucket', 'fleet16')
    assert s3.version == 16
    with pytest.raises(RuntimeError, match='already reserved'): reserve(s3, 'bucket', 'fleet0')


def test_three_hour_reservation_is_atomic_when_budget_is_insufficient():
    s3=S3()
    for index in range(14): reserve(s3,'bucket',f'prior-{index}')
    version=s3.version; snapshot=json.loads(s3.data)
    with pytest.raises(RuntimeError,match='exhausted'):
        reserve_many(s3,'bucket',['calibration','calibration-hour2','calibration-hour3'])
    assert s3.version==version
    assert json.loads(s3.data)==snapshot


def test_three_hour_reservation_commits_all_slots_with_one_conditional_write():
    s3=S3()
    reserve_many(s3,'bucket',['calibration','calibration-hour2','calibration-hour3'])
    ledger=json.loads(s3.data)
    assert set(ledger['launches'])=={'calibration','calibration-hour2','calibration-hour3'}
    assert {row['reserved_brl'] for row in ledger['launches'].values()}=={'20'}
    assert s3.version==1


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


def test_three_hour_shutdown_is_armed_and_read_back():
    client=ASG(); now=datetime.now(timezone.utc).replace(microsecond=0)
    deadline=arm(client,'fleet',now,duration_seconds=3*PILOT_SECONDS)
    assert (deadline-now).total_seconds()==3*PILOT_SECONDS
    assert client.action['MaxSize']==0 and client.action['DesiredCapacity']==0


def test_shutdown_duration_must_be_whole_budget_hours():
    with pytest.raises(ValueError,match='whole budget hours'):
        arm(ASG(),'fleet',duration_seconds=90)


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
    monkeypatch.setattr(budget, 'reserve_many', lambda *args: None)
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


def test_legacy_ledger_is_not_used_after_successor_budget_approval():
    s3 = S3()
    s3.data = json.dumps({'schema_version': 1, 'total_brl': '260', 'reserve_brl': '40',
                          'launches': {'old': {'reserved_brl': '20'}}}).encode()
    with pytest.raises(RuntimeError, match='Incompatible budget ledger'):
        reserve(s3, 'bucket', 'new-fleet')


def test_missing_approved_budget_ledger_requires_reconciliation():
    class Missing(S3):
        def get_object(self, **kwargs): raise self.exceptions.NoSuchKey()
    with pytest.raises(RuntimeError, match='reconcile'):
        reserve(Missing(), 'bucket', 'new-fleet')


def test_reservation_transfer_preserves_budget_and_shutdown_deadline():
    s3 = S3(); reserve(s3, 'bucket', 'old-fleet')
    ledger = json.loads(s3.data); reserved_at = ledger['launches']['old-fleet']['reserved_at']
    class Fleets:
        def __init__(self):
            self.groups = {
                'old-fleet': dict(AutoScalingGroupName='old-fleet', MinSize=0, MaxSize=0, DesiredCapacity=0, Instances=[]),
                'new-fleet': dict(AutoScalingGroupName='new-fleet', MinSize=0, MaxSize=1, DesiredCapacity=0, Instances=[]),
            }
            self.actions = {'old-fleet': [dict(ScheduledActionName='bankai-budget-shutdown',
                StartTime=datetime(2026,10,18,19,5,55,tzinfo=timezone.utc), MinSize=0, MaxSize=0,
                DesiredCapacity=0)]}
        def describe_auto_scaling_groups(self, **kwargs):
            return dict(AutoScalingGroups=[self.groups[n] for n in kwargs['AutoScalingGroupNames']])
        def describe_scheduled_actions(self, **kwargs):
            return dict(ScheduledUpdateGroupActions=self.actions.get(kwargs['AutoScalingGroupName'], []))
        def put_scheduled_update_group_action(self, **kwargs):
            self.actions[kwargs['AutoScalingGroupName']] = [dict(kwargs)]
        def delete_scheduled_action(self, **kwargs):
            self.actions.pop(kwargs['AutoScalingGroupName'], None)
    asg=Fleets(); now=datetime(2026,10,18,18,40,tzinfo=timezone.utc)
    deadline=transfer_reservation(s3,asg,'bucket','old-fleet','new-fleet',now=now)
    moved=json.loads(s3.data)['launches']
    assert set(moved)=={'new-fleet'}
    assert moved['new-fleet']['reserved_at']==reserved_at
    assert moved['new-fleet']['transferred_from']=='old-fleet'
    assert moved['new-fleet']['shutdown_deadline']==deadline.isoformat()
    assert asg.actions['new-fleet'][0]['StartTime']==deadline
    assert moved['new-fleet']['reserved_brl']=='20'


def test_reservation_transfer_rejects_expired_shutdown_deadline():
    s3 = S3(); reserve(s3, 'bucket', 'old-fleet')
    class Fleets:
        def describe_auto_scaling_groups(self, **kwargs):
            return dict(AutoScalingGroups=[dict(AutoScalingGroupName=name, MinSize=0,
                MaxSize=0 if name=='old-fleet' else 1, DesiredCapacity=0, Instances=[])
                for name in kwargs['AutoScalingGroupNames']])
        def describe_scheduled_actions(self, **kwargs):
            return dict(ScheduledUpdateGroupActions=[dict(ScheduledActionName='bankai-budget-shutdown',
                StartTime=datetime(2026,10,18,18,39,tzinfo=timezone.utc), MinSize=0,MaxSize=0,DesiredCapacity=0)]
                if kwargs['AutoScalingGroupName']=='old-fleet' else [])
    with pytest.raises(RuntimeError,match='invalid or expired'):
        transfer_reservation(s3,Fleets(),'bucket','old-fleet','new-fleet',
            now=datetime(2026,10,18,18,40,tzinfo=timezone.utc))
