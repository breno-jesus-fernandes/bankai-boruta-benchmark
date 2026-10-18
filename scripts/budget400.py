"""Explicit user-authorized successor to the exhausted BRL200 campaign ledger.

The old ledger is preserved. Existing paid workers need no restart. All future
additional capacity must reserve against this successor, retaining history.
"""
from datetime import datetime, timezone
from decimal import Decimal
import json

from bankai_benchmark.budget import LEDGER_KEY, LEGACY_LEDGER_KEY, validate_policy

CURRENT_KEY = LEGACY_LEDGER_KEY
TOTAL_BRL = Decimal('400')
RESERVE_BRL = Decimal('80')
SLOT_BRL = Decimal('20')


def allocation(ledger):
    launches=ledger['launches']
    if any(Decimal(row['reserved_brl']) != SLOT_BRL for row in launches.values()):
        raise RuntimeError('Invalid reservation history')
    return sum((Decimal(row['reserved_brl']) for row in launches.values()), Decimal(0))


def validate(ledger):
    if (ledger['schema_version'] != 2 or Decimal(ledger['total_brl']) != TOTAL_BRL
            or Decimal(ledger['reserve_brl']) != RESERVE_BRL):
        raise RuntimeError('Incompatible BRL400 policy')
    if allocation(ledger) > TOTAL_BRL-RESERVE_BRL:
        raise RuntimeError('Budget ledger exceeds permitted allocation')


def successor(previous, etag):
    """Require the legacy allowance to be exhausted so old controllers cannot spend more."""
    if (previous['schema_version'] != 1 or Decimal(previous['total_brl']) != Decimal('200')
            or Decimal(previous['reserve_brl']) != Decimal('40') or allocation(previous) != Decimal('160')):
        raise RuntimeError('Legacy ledger must be intact and exhausted before migration')
    ledger=dict(schema_version=2,total_brl=str(TOTAL_BRL),reserve_brl=str(RESERVE_BRL),
        launches={key:dict(row) for key,row in previous['launches'].items()},supersedes=dict(key=LEGACY_LEDGER_KEY,etag=etag),
        authorization=dict(total_brl='400',authorized_at=datetime.now(timezone.utc).isoformat(),
                           source='Explicit user authorization: 400 reais'))
    validate(ledger)
    return ledger


def reconcile(current, current_etag, existing, existing_etag):
    """Merge the exhausted v2 BRL260 ledger into its authorized BRL400 successor."""
    if (current.get('schema_version') != 1 or Decimal(current.get('total_brl', '0')) != Decimal('260')
            or Decimal(current.get('reserve_brl', '0')) != Decimal('40')):
        raise RuntimeError('Current v2 budget ledger is incompatible')
    if (existing.get('schema_version') != 2 or Decimal(existing.get('total_brl', '0')) != TOTAL_BRL
            or Decimal(existing.get('reserve_brl', '0')) != RESERVE_BRL):
        raise RuntimeError('Approved BRL400 successor is incompatible')
    current_launches = current.get('launches', {})
    existing_launches = existing.get('launches', {})
    if allocation(current) != Decimal('220'):
        raise RuntimeError('Current BRL260 ledger is not exhausted as expected')
    if allocation(existing) > TOTAL_BRL - RESERVE_BRL:
        raise RuntimeError('BRL400 successor exceeds its authorized allocation')
    if any(existing_launches.get(key) != row for key, row in current_launches.items()
           if key in existing_launches):
        raise RuntimeError('Current and successor reservation histories conflict')
    if any(key not in current_launches for key in existing_launches):
        raise RuntimeError('Successor contains reservations missing from the current ledger')
    missing = {key: dict(row) for key, row in current_launches.items() if key not in existing_launches}
    if any(Decimal(row.get('reserved_brl', '0')) != SLOT_BRL for row in missing.values()):
        raise RuntimeError('Current ledger contains an invalid reservation')
    merged = dict(existing)
    merged['launches'] = {**existing_launches, **missing}
    reconciliations=merged.setdefault('reconciliations', [])
    if not any(row.get('key')==CURRENT_KEY and row.get('etag')==current_etag for row in reconciliations):
        reconciliations.append(dict(key=CURRENT_KEY, etag=current_etag,
            merged_at=datetime.now(timezone.utc).isoformat(), reservations_added=sorted(missing)))
    validate(merged)
    return merged


def read(s3,bucket,key):
    response=s3.get_object(Bucket=bucket,Key=key)
    with response['Body'] as body:
        return json.load(body),response['ETag']


def migrate(s3,bucket):
    current,current_etag=read(s3,bucket,CURRENT_KEY)
    existing,existing_etag=read(s3,bucket,LEDGER_KEY)
    ledger=reconcile(current,current_etag,existing,existing_etag)
    if ledger != existing:
        s3.put_object(Bucket=bucket,Key=LEDGER_KEY,Body=json.dumps(ledger).encode(),
                      ContentType='application/json',IfMatch=existing_etag)
    confirmed,_=read(s3,bucket,LEDGER_KEY)
    validate(confirmed)
    return confirmed


def reserve(s3,bucket,launch_id):
    validate_policy()
    ledger,etag=read(s3,bucket,LEDGER_KEY)
    validate(ledger)
    if launch_id in ledger['launches']:
        raise RuntimeError('Already reserved; no automatic repeat')
    if allocation(ledger)+SLOT_BRL > TOTAL_BRL-RESERVE_BRL:
        raise RuntimeError('BRL400 campaign allocation exhausted')
    ledger['launches'][launch_id]=dict(reserved_brl=str(SLOT_BRL),reserved_at=datetime.now(timezone.utc).isoformat())
    s3.put_object(Bucket=bucket,Key=LEDGER_KEY,Body=json.dumps(ledger).encode(),
                  ContentType='application/json',IfMatch=etag)
    return ledger


def main():
    import argparse
    import boto3

    parser=argparse.ArgumentParser(description='Reconcile the authorized BRL400 ledger with current BRL260 reservations.')
    parser.add_argument('--profile',default='bankai')
    parser.add_argument('--region',default='us-east-1')
    parser.add_argument('--bucket',required=True)
    args=parser.parse_args()
    session=boto3.Session(profile_name=args.profile,region_name=args.region)
    ledger=migrate(session.client('s3'),args.bucket)
    print(json.dumps(dict(total_brl=ledger['total_brl'],reserve_brl=ledger['reserve_brl'],
        allocated_brl=str(allocation(ledger)),available_brl=str(TOTAL_BRL-RESERVE_BRL-allocation(ledger)),
        launch_count=len(ledger['launches']),reconciliations=ledger.get('reconciliations',[])),indent=2))


if __name__=='__main__':
    main()
