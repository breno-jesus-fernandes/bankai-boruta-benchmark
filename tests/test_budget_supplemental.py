import io
import json
from unittest.mock import Mock

from botocore.exceptions import ClientError
import pytest

from bankai_benchmark import budget


def stored(ledger, etag='etag'):
    s3 = Mock()
    s3.get_object.return_value = {'Body': io.BytesIO(json.dumps(ledger).encode()), 'ETag': etag}
    return s3


def test_first_reservation_creates_the_ledger_conditionally():
    s3 = Mock()
    s3.get_object.side_effect = ClientError({'Error': {'Code': 'NoSuchKey'}}, 'GetObject')
    ledger = budget.reserve_supplemental(s3, 'bucket', 'fleet', 2)
    assert ledger['launches']['fleet']['reserved_usd'] == '3.00'
    kwargs = s3.put_object.call_args.kwargs
    assert kwargs['Key'] == budget.SUPPLEMENTAL_KEY and kwargs['IfNoneMatch'] == '*'


def test_reservations_accumulate_with_etag_and_never_exceed_cap():
    ledger = dict(schema_version=1, total_usd='150', launches={'a': {'reserved_usd': '147.00'}})
    s3 = stored(ledger)
    budget.reserve_supplemental(s3, 'bucket', 'b', 2)
    assert s3.put_object.call_args.kwargs['IfMatch'] == 'etag'
    s3 = stored(dict(ledger, launches={'a': {'reserved_usd': '148.00'}}))
    with pytest.raises(RuntimeError, match='exhausted'):
        budget.reserve_supplemental(s3, 'bucket', 'b', 2)
    s3.put_object.assert_not_called()


def test_duplicate_launch_is_rejected():
    s3 = stored(dict(schema_version=1, total_usd='150', launches={'a': {'reserved_usd': '3.00'}}))
    with pytest.raises(RuntimeError, match='already reserved'):
        budget.reserve_supplemental(s3, 'bucket', 'a', 1)
    s3.put_object.assert_not_called()
