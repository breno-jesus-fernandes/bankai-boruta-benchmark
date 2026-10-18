"""Conservative campaign reservations and AWS-side pilot shutdown.

Reservations are never refunded automatically, even after a failed launch.
The ledger must remain in the same bucket for every campaign launch.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json

TOTAL_BRL = Decimal('260')
PREVIOUS_TOTAL_BRL = Decimal('240')
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
    if ledger['schema_version'] != 1 or Decimal(ledger['reserve_brl']) != RESERVE_BRL:
        raise RuntimeError('Incompatible budget ledger')
    launches = ledger['launches']
    if any(Decimal(item['reserved_brl']) != PILOT_BRL for item in launches.values()):
        raise RuntimeError('Corrupt budget reservation')
    allocated = sum((Decimal(item['reserved_brl']) for item in launches.values()), Decimal(0))
    total = Decimal(ledger['total_brl'])
    if total == PREVIOUS_TOTAL_BRL:
        if allocated != PREVIOUS_TOTAL_BRL - RESERVE_BRL:
            raise RuntimeError('Previous budget ledger is not eligible for the approved increase')
        ledger['total_brl'] = str(TOTAL_BRL)
    elif total != TOTAL_BRL:
        raise RuntimeError('Incompatible budget ledger')
    if launch_id in launches:
        raise RuntimeError('Launch already reserved; deadline cannot be extended')
    if allocated + PILOT_BRL > TOTAL_BRL - RESERVE_BRL:
        raise RuntimeError('Budget exhausted: launch blocked')
    launches[launch_id] = {'reserved_brl': str(PILOT_BRL),
                          'reserved_at': datetime.now(timezone.utc).isoformat()}
    s3.put_object(Bucket=bucket, Key=LEDGER_KEY, Body=json.dumps(ledger).encode(),
                  ContentType='application/json', **condition)
    return ledger


def transfer_reservation(s3, autoscaling, bucket, old_fleet, new_fleet, now=None):
    """Move one approved pilot slot to an idle fleet without changing its deadline."""
    now = now or datetime.now(timezone.utc)
    validate_policy(now)
    response = s3.get_object(Bucket=bucket, Key=LEDGER_KEY)
    with response['Body'] as body:
        ledger = json.load(body)
    if ledger.get('schema_version') != 1 or Decimal(ledger.get('reserve_brl', '0')) != RESERVE_BRL:
        raise RuntimeError('Incompatible budget ledger')
    launches = ledger.get('launches', {})
    reservation = launches.get(old_fleet)
    if reservation is None or Decimal(reservation.get('reserved_brl', '0')) != PILOT_BRL:
        raise RuntimeError('Source fleet has no transferable pilot reservation')
    if new_fleet in launches:
        raise RuntimeError('Destination fleet already has a reservation')

    groups = autoscaling.describe_auto_scaling_groups(
        AutoScalingGroupNames=[old_fleet, new_fleet])['AutoScalingGroups']
    by_name = {group['AutoScalingGroupName']: group for group in groups}
    if set(by_name) != {old_fleet, new_fleet}:
        raise RuntimeError('Source or destination budget fleet absent')
    for name, group in by_name.items():
        allowed_max = (0, 1) if name == old_fleet else (1,)
        if (group['MinSize'] != 0 or group['MaxSize'] not in allowed_max or group['DesiredCapacity'] != 0
                or group.get('Instances') or group.get('SuspendedProcesses')
                or group.get('NewInstancesProtectedFromScaleIn')):
            raise RuntimeError(f'{name} is not an idle, unsuspended, single-instance fleet')

    old_actions = autoscaling.describe_scheduled_actions(
        AutoScalingGroupName=old_fleet)['ScheduledUpdateGroupActions']
    old_actions = [a for a in old_actions if a.get('ScheduledActionName') == ACTION]
    if len(old_actions) != 1:
        raise RuntimeError('Source fleet must have one verified shutdown action')
    action = old_actions[0]
    deadline = action.get('StartTime')
    if not isinstance(deadline, datetime):
        deadline = datetime.fromisoformat(str(deadline).replace('Z', '+00:00'))
    if (deadline.tzinfo is None or now >= deadline or action.get('Recurrence')
            or any(action.get(key) != 0 for key in ('MinSize', 'MaxSize', 'DesiredCapacity'))):
        raise RuntimeError('Source shutdown deadline is invalid or expired')
    if autoscaling.describe_scheduled_actions(
            AutoScalingGroupName=new_fleet)['ScheduledUpdateGroupActions']:
        raise RuntimeError('Destination fleet already has scheduled actions')

    autoscaling.put_scheduled_update_group_action(
        AutoScalingGroupName=new_fleet, ScheduledActionName=ACTION, StartTime=deadline,
        MinSize=0, MaxSize=0, DesiredCapacity=0)
    copied = autoscaling.describe_scheduled_actions(
        AutoScalingGroupName=new_fleet,
        ScheduledActionNames=[ACTION])['ScheduledUpdateGroupActions']
    if (len(copied) != 1 or copied[0].get('StartTime') != deadline
            or any(copied[0].get(key) != 0 for key in ('MinSize', 'MaxSize', 'DesiredCapacity'))
            or copied[0].get('Recurrence')):
        raise RuntimeError('Destination shutdown verification failed; capacity remains zero')

    moved = dict(reservation, transferred_from=old_fleet, shutdown_deadline=deadline.isoformat())
    del launches[old_fleet]
    launches[new_fleet] = moved
    try:
        s3.put_object(Bucket=bucket, Key=LEDGER_KEY, Body=json.dumps(ledger).encode(),
                      ContentType='application/json', IfMatch=response['ETag'])
    except Exception:
        autoscaling.delete_scheduled_action(
            AutoScalingGroupName=new_fleet, ScheduledActionName=ACTION)
        raise
    return deadline


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
