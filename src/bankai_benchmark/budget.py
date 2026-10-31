"""Conservative campaign reservations and AWS-side pilot shutdown.

Reservations are never refunded automatically, even after a failed launch.
The ledger must remain in the same bucket for every campaign launch.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json

TOTAL_BRL = Decimal('400')
RESERVE_BRL = Decimal('80')
PILOT_BRL = Decimal('20')
PILOT_SECONDS = 3600
LEDGER_KEY = 'bankai-budget/campaign-400-brl.json'
LEGACY_LEDGER_KEY = 'bankai-budget/campaign-200-brl.json'
ACTION = 'bankai-budget-shutdown'
# Prices and PTAX reviewed on 2026-10-30; see verification/native-shadow-x2-cost-policy-20261030.md.
POLICY_EXPIRES = datetime(2026, 11, 6, tzinfo=timezone.utc)


def validate_policy(now=None):
    if (now or datetime.now(timezone.utc)) >= POLICY_EXPIRES:
        raise RuntimeError('Budget price/FX policy expired; review before launch')


def reserve(s3, bucket, launch_id):
    """Reserve one hour in the successor ledger."""
    return reserve_many(s3, bucket, [launch_id])


def reserve_many(s3, bucket, launch_ids):
    """Atomically reserve all hour slots before any paid capacity is enabled."""
    try:
        response = s3.get_object(Bucket=bucket, Key=LEDGER_KEY)
    except s3.exceptions.NoSuchKey:
        raise RuntimeError('Approved BRL400 ledger is missing; reconcile it before launch')
    with response['Body'] as body:
        ledger = json.load(body)
    if (ledger.get('schema_version') != 2 or Decimal(ledger.get('total_brl', '0')) != TOTAL_BRL
            or Decimal(ledger.get('reserve_brl', '0')) != RESERVE_BRL):
        raise RuntimeError('Incompatible budget ledger')
    launches = ledger.get('launches', {})
    if any(Decimal(item.get('reserved_brl', '0')) != PILOT_BRL for item in launches.values()):
        raise RuntimeError('Corrupt budget reservation')
    launch_ids = list(launch_ids)
    if not launch_ids or len(set(launch_ids)) != len(launch_ids):
        raise ValueError('Reservation IDs must be a nonempty unique sequence')
    if any(launch_id in launches for launch_id in launch_ids):
        raise RuntimeError('Launch already reserved; deadline cannot be extended')
    allocated = sum((Decimal(item['reserved_brl']) for item in launches.values()), Decimal(0))
    if allocated + PILOT_BRL*len(launch_ids) > TOTAL_BRL - RESERVE_BRL:
        raise RuntimeError('Budget exhausted: launch blocked')
    reserved_at = datetime.now(timezone.utc).isoformat()
    launches.update({launch_id: {'reserved_brl': str(PILOT_BRL), 'reserved_at': reserved_at}
                     for launch_id in launch_ids})
    s3.put_object(Bucket=bucket, Key=LEDGER_KEY, Body=json.dumps(ledger).encode(),
                  ContentType='application/json', IfMatch=response['ETag'])
    return ledger


def transfer_reservation(s3, autoscaling, bucket, old_fleet, new_fleet, now=None):
    """Move one approved pilot slot to an idle fleet without changing its deadline."""
    now = now or datetime.now(timezone.utc)
    validate_policy(now)
    response = s3.get_object(Bucket=bucket, Key=LEDGER_KEY)
    with response['Body'] as body:
        ledger = json.load(body)
    if (ledger.get('schema_version') != 2 or Decimal(ledger.get('total_brl', '0')) != TOTAL_BRL
            or Decimal(ledger.get('reserve_brl', '0')) != RESERVE_BRL):
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


def arm(autoscaling, fleet, now=None, *, duration_seconds=PILOT_SECONDS):
    """Arm and read back a shutdown BEFORE allowing any paid capacity."""
    now = now or datetime.now(timezone.utc)
    if duration_seconds < PILOT_SECONDS or duration_seconds % PILOT_SECONDS:
        raise ValueError('Shutdown duration must be one or more whole budget hours')
    deadline = (now + timedelta(seconds=duration_seconds)).replace(microsecond=0)
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


SUPPLEMENTAL_KEY = 'bankai-budget/supplemental-150-usd.json'
# Approved on 2026-10-31: USD 150 raised to 165 for the 64-core scaling run. The
# key keeps its original name; the ledger records the raise.
SUPPLEMENTAL_TOTAL_USD = Decimal('165')
SUPPLEMENTAL_RAISES = {Decimal('150'): '2026-10-31: c7a.16xlarge Industrial 2x thread scaling'}
# Conservative c7a.4xlarge hour: on-demand price plus EBS, IPv4 and contingency.
SUPPLEMENTAL_HOUR_USD = Decimal('1.50')
# c7a.8xlarge (about USD 1.99/h with contingency) reserves two 4xlarge slots per hour.
SUPPLEMENTAL_HOUR_USD_8XL = Decimal('3.00')
# c7a.16xlarge: USD 3.28448/h on demand on 2026-10-31, about 3.97/h with contingency.
SUPPLEMENTAL_HOUR_USD_16XL = Decimal('6.00')


def reserve_supplemental(s3, bucket, launch_id, hours, hour_usd=SUPPLEMENTAL_HOUR_USD):
    """Reserve armed hours against the separately approved USD extension (150, raised to 165).

    The BRL 400 ledger is left untouched; this ledger is created on first use
    and, like it, never refunds a reservation.
    """
    from botocore.exceptions import ClientError
    try:
        response = s3.get_object(Bucket=bucket, Key=SUPPLEMENTAL_KEY)
        with response['Body'] as body:
            ledger = json.load(body)
        condition = dict(IfMatch=response['ETag'])
    except ClientError as error:
        if error.response.get('Error', {}).get('Code') != 'NoSuchKey':
            raise
        ledger = dict(schema_version=1, total_usd=str(SUPPLEMENTAL_TOTAL_USD), launches={})
        condition = dict(IfNoneMatch='*')
    previous = Decimal(ledger.get('total_usd', '0'))
    if ledger.get('schema_version') == 1 and previous in SUPPLEMENTAL_RAISES:
        ledger['total_usd'] = str(SUPPLEMENTAL_TOTAL_USD)
        ledger.setdefault('raises', []).append(dict(from_usd=str(previous), to_usd=str(SUPPLEMENTAL_TOTAL_USD),
            reason=SUPPLEMENTAL_RAISES[previous], at=datetime.now(timezone.utc).isoformat()))
    if ledger.get('schema_version') != 1 or Decimal(ledger.get('total_usd', '0')) != SUPPLEMENTAL_TOTAL_USD:
        raise RuntimeError('Incompatible supplemental budget ledger')
    launches = ledger['launches']
    if launch_id in launches:
        raise RuntimeError('Launch already reserved; deadline cannot be extended')
    amount = Decimal(hour_usd) * hours
    allocated = sum((Decimal(item['reserved_usd']) for item in launches.values()), Decimal(0))
    if allocated + amount > SUPPLEMENTAL_TOTAL_USD:
        raise RuntimeError('Supplemental budget exhausted: launch blocked')
    launches[launch_id] = dict(reserved_usd=str(amount), hours=hours,
                               reserved_at=datetime.now(timezone.utc).isoformat())
    s3.put_object(Bucket=bucket, Key=SUPPLEMENTAL_KEY, Body=json.dumps(ledger).encode(),
                  ContentType='application/json', **condition)
    return ledger
