"""Explicit user-authorized successor to the exhausted BRL200 campaign ledger.

The old ledger is preserved. Existing paid workers need no restart. All future
additional capacity must reserve against this successor, retaining history.
"""
from datetime import datetime, timezone
from decimal import Decimal
import json

from bankai_benchmark.budget import LEDGER_KEY as OLD_KEY, validate_policy

LEDGER_KEY = 'bankai-budget/campaign-400-brl.json'
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
        launches={key:dict(row) for key,row in previous['launches'].items()},supersedes=dict(key=OLD_KEY,etag=etag),
        authorization=dict(total_brl='400',authorized_at=datetime.now(timezone.utc).isoformat(),
                           source='Explicit user authorization: 400 reais'))
    validate(ledger)
    return ledger


def read(s3,bucket,key):
    response=s3.get_object(Bucket=bucket,Key=key)
    with response['Body'] as body:
        return json.load(body),response['ETag']


def migrate(s3,bucket):
    previous,etag=read(s3,bucket,OLD_KEY)
    ledger=successor(previous,etag)
    try:
        existing,_=read(s3,bucket,LEDGER_KEY)
    except s3.exceptions.NoSuchKey:
        s3.put_object(Bucket=bucket,Key=LEDGER_KEY,Body=json.dumps(ledger).encode(),
                      ContentType='application/json',IfNoneMatch='*')
    else:
        validate(existing)
        if existing['supersedes'] != ledger['supersedes']:
            raise RuntimeError('Successor history differs; refusing to mix budgets')
        if any(existing['launches'].get(key) != row for key,row in previous['launches'].items()):
            raise RuntimeError('Successor is missing historical reservations')
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
