"""Conservative campaign reservations and AWS-side pilot shutdown.

Reservations are never refunded automatically, even after a failed launch.
The ledger must remain in the same bucket for every campaign launch.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json

TOTAL_BRL = Decimal('240')
RESERVE_BRL = Decimal('40')
PILOT_BRL = Decimal('20')
PILOT_SECONDS = 3600
LEDGER_KEY = 'bankai-budget/campaign-200-brl.json'
ACTION = 'bankai-budget-shutdown'
POLICY_EXPIRES = datetime(2026, 10, 24, tzinfo=timezone.utc)


def validate_policy(now=None):
    if (now or datetime.now(timezone.utc)) >= POLICY_EXPIRES:
        raise RuntimeError('Budget price/FX policy expired; review before launch')


def reserve(s3, bucket, launch_id):
    """Conditional writes serialize reservations across controllers/experiments."""
    condition = {'IfNoneMatch': '*'}
    try:
        response = s3.get_object(Bucket=bucket, Key=LEDGER_KEY)
    except s3.exceptions.NoSuchKey:
        ledger = {'schema_version': 1, 'total_brl': str(TOTAL_BRL),
                  'reserve_brl': str(RESERVE_BRL), 'launches': {}}
    else:
        with response['Body'] as body:
            ledger = json.load(body)
        condition = {'IfMatch': response['ETag']}
    if (ledger['schema_version'] != 1 or Decimal(ledger['total_brl']) != TOTAL_BRL
            or Decimal(ledger['reserve_brl']) != RESERVE_BRL):
        raise RuntimeError('Incompatible budget ledger')
    launches = ledger['launches']
    if any(Decimal(item['reserved_brl']) != PILOT_BRL for item in launches.values()):
        raise RuntimeError('Corrupt budget reservation')
    if launch_id in launches:
        raise RuntimeError('Launch already reserved; deadline cannot be extended')
    allocated = sum((Decimal(item['reserved_brl']) for item in launches.values()), Decimal(0))
    if allocated + PILOT_BRL > TOTAL_BRL - RESERVE_BRL:
        raise RuntimeError('Budget exhausted: launch blocked')
    launches[launch_id] = {'reserved_brl': str(PILOT_BRL),
                          'reserved_at': datetime.now(timezone.utc).isoformat()}
    s3.put_object(Bucket=bucket, Key=LEDGER_KEY, Body=json.dumps(ledger).encode(),
                  ContentType='application/json', **condition)
    return ledger


def arm(autoscaling, fleet, now=None):
    """Arm and read back a shutdown BEFORE allowing any paid capacity."""
    now = now or datetime.now(timezone.utc)
    deadline = (now + timedelta(seconds=PILOT_SECONDS)).replace(microsecond=0)
    groups = autoscaling.describe_auto_scaling_groups(AutoScalingGroupNames=[fleet])['AutoScalingGroups']
    if len(groups) != 1:
        raise RuntimeError('Budget fleet absent')
    group = groups[0]
    if (group['MinSize'] != 0 or group['MaxSize'] != 1 or group['DesiredCapacity'] != 0
            or group.get('Instances') or group.get('SuspendedProcesses')
            or group.get('NewInstancesProtectedFromScaleIn')):
        raise RuntimeError('Budget requires an idle, unsuspended, single-instance fleet')
    existing = autoscaling.describe_scheduled_actions(AutoScalingGroupName=fleet)['ScheduledUpdateGroupActions']
    if existing:
        raise RuntimeError('Fleet already has scheduled actions; refusing deadline changes')
    autoscaling.put_scheduled_update_group_action(AutoScalingGroupName=fleet,
        ScheduledActionName=ACTION, StartTime=deadline, MinSize=0, MaxSize=0, DesiredCapacity=0)
    actions = autoscaling.describe_scheduled_actions(AutoScalingGroupName=fleet,
        ScheduledActionNames=[ACTION])['ScheduledUpdateGroupActions']
    if len(actions) != 1 or any(actions[0].get(key) != 0 for key in ('MinSize', 'MaxSize', 'DesiredCapacity')) or actions[0].get('StartTime') != deadline or actions[0].get('Recurrence'):
        raise RuntimeError('AWS shutdown verification failed; capacity remains zero')
    if datetime.now(timezone.utc) >= deadline:
        raise RuntimeError('Shutdown deadline already expired')
    return deadline


def stop(autoscaling, fleet):
    autoscaling.update_auto_scaling_group(AutoScalingGroupName=fleet,
                                        MinSize=0, MaxSize=0, DesiredCapacity=0)
