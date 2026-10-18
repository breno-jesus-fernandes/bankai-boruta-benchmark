from copy import deepcopy
import importlib
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest

sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
budget=importlib.import_module('budget400')


def legacy(n=8):
    return dict(schema_version=1,total_brl='200',reserve_brl='40',
                launches={str(i):{'reserved_brl':'20'} for i in range(n)})


def test_successor_preserves_history_and_leaves_80_safety_margin():
    old=legacy(); snapshot=deepcopy(old)
    new=budget.successor(old,'etag')
    assert old==snapshot
    assert new['launches']==old['launches']
    assert budget.allocation(new)==160
    assert new['total_brl']=='400' and new['reserve_brl']=='80'
    assert new['supersedes']['etag']=='etag'


def test_unexhausted_legacy_guard_cannot_overlap_successor():
    with pytest.raises(RuntimeError,match='exhausted'):
        budget.successor(legacy(7),'etag')


def test_reservation_uses_conditional_write_and_carries_old_allocation(monkeypatch):
    ledger=budget.successor(legacy(),'etag')
    monkeypatch.setattr(budget,'read',lambda *args:(ledger,'current-etag'))
    s3=Mock()
    result=budget.reserve(s3,'bucket','new-slot')
    assert budget.allocation(result)==180
    assert s3.put_object.call_args.kwargs['IfMatch']=='current-etag'


def test_exhaustion_or_duplicate_never_writes(monkeypatch):
    ledger=budget.successor(legacy(),'etag')
    ledger['launches'].update({f'new-{i}':{'reserved_brl':'20'} for i in range(8)})
    monkeypatch.setattr(budget,'read',lambda *args:(ledger,'etag'))
    s3=Mock()
    with pytest.raises(RuntimeError,match='exhausted'):
        budget.reserve(s3,'bucket','beyond-cap')
    with pytest.raises(RuntimeError,match='Already reserved'):
        budget.reserve(s3,'bucket','new-0')
    s3.put_object.assert_not_called()


def test_reconcile_merges_current_v2_reservations_without_resetting_history():
    previous=legacy()
    existing=budget.successor(previous,'old-etag')
    current=dict(schema_version=1,total_brl='260',reserve_brl='40',launches={
        **previous['launches'],
        'r5-smoke':{'reserved_brl':'20','reserved_at':'new-1'},
        'r5-calibration':{'reserved_brl':'20','reserved_at':'new-2'},
        'a6-smoke':{'reserved_brl':'20','reserved_at':'new-3'},
    })
    result=budget.reconcile(current,'current-etag',existing,'successor-etag')
    assert set(result['launches'])==set(current['launches'])
    assert budget.allocation(result)==220
    assert result['launches']['r5-calibration']==current['launches']['r5-calibration']
    assert result['reconciliations'][0]['etag']=='current-etag'


def test_reconcile_refuses_conflicting_reservation_history():
    previous=legacy()
    existing=budget.successor(previous,'old-etag')
    current=dict(schema_version=1,total_brl='260',reserve_brl='40',launches={
        **previous['launches'],
        'new':{'reserved_brl':'20','reserved_at':'different'},
        'newer':{'reserved_brl':'20','reserved_at':'newer'},
        'newest':{'reserved_brl':'20','reserved_at':'newest'},
    })
    existing['launches']['0']['reserved_at']='changed'
    with pytest.raises(RuntimeError,match='conflict'):
        budget.reconcile(current,'current-etag',existing,'successor-etag')
