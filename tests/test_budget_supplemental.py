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
    ledger = dict(schema_version=1, total_usd='165', launches={'a': {'reserved_usd': '162.00'}})
    s3 = stored(ledger)
    budget.reserve_supplemental(s3, 'bucket', 'b', 2)
    assert s3.put_object.call_args.kwargs['IfMatch'] == 'etag'
    s3 = stored(dict(ledger, launches={'a': {'reserved_usd': '163.00'}}))
    with pytest.raises(RuntimeError, match='exhausted'):
        budget.reserve_supplemental(s3, 'bucket', 'b', 2)
    s3.put_object.assert_not_called()


def test_hourly_rate_follows_the_instance():
    s3 = stored(dict(schema_version=1, total_usd='150', launches={'a': {'reserved_usd': '49.50'}}))
    ledger = budget.reserve_supplemental(s3, 'bucket', 'b', 2, budget.SUPPLEMENTAL_HOUR_USD_8XL)
    assert ledger['launches']['b']['reserved_usd'] == '6.00' and ledger['launches']['b']['hours'] == 2


def test_duplicate_launch_is_rejected():
    s3 = stored(dict(schema_version=1, total_usd='150', launches={'a': {'reserved_usd': '3.00'}}))
    with pytest.raises(RuntimeError, match='already reserved'):
        budget.reserve_supplemental(s3, 'bucket', 'a', 1)
    s3.put_object.assert_not_called()


def test_the_150_ledger_is_raised_to_165_once_and_records_it():
    s3 = stored(dict(schema_version=1, total_usd='150', launches={'a': {'reserved_usd': '136.50'}}))
    ledger = budget.reserve_supplemental(s3, 'bucket', 'b', 4, budget.SUPPLEMENTAL_HOUR_USD_16XL)
    assert ledger['total_usd'] == '165' and ledger['launches']['b']['reserved_usd'] == '24.00'
    assert ledger['raises'][0]['from_usd'] == '150' and ledger['raises'][0]['to_usd'] == '165'
    s3 = stored(dict(schema_version=1, total_usd='150', launches={'a': {'reserved_usd': '136.50'}}))
    with pytest.raises(RuntimeError, match='exhausted'):
        budget.reserve_supplemental(s3, 'bucket', 'b', 5, budget.SUPPLEMENTAL_HOUR_USD_16XL)
    s3 = stored(dict(schema_version=1, total_usd='200', launches={}))
    with pytest.raises(RuntimeError, match='Incompatible'):
        budget.reserve_supplemental(s3, 'bucket', 'b', 1)
