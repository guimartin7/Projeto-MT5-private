from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

from reconciliation import MANAGED_MAGIC, broker_snapshot, compare_expected


def api_mock(positions=(), orders=(), deals=()):
    api = Mock(ACCOUNT_TRADE_MODE_DEMO=0)
    api.account_info.return_value = SimpleNamespace(
        trade_mode=0, server='ClearInvestimentos-DEMO')
    api.terminal_info.return_value = SimpleNamespace(connected=True)
    api.positions_get.return_value = positions
    api.orders_get.return_value = orders
    api.history_deals_get.return_value = deals
    return api


def position(magic=MANAGED_MAGIC, volume=1, kind=0, sl=100):
    return SimpleNamespace(ticket=1, time=1, type=kind, magic=magic, volume=volume,
                           price_open=1, sl=sl, tp=2, price_current=1, profit=0)


def test_clean_account_is_safe():
    snapshot = broker_snapshot(api_mock(), now=datetime(2026, 9, 3, tzinfo=timezone.utc))
    assert snapshot['status'] == 'CLEAN'
    assert snapshot['safe_for_new_entry']
    assert compare_expected(snapshot)['matches']


def test_manual_position_creates_conflict():
    snapshot = broker_snapshot(api_mock(positions=(position(magic=0),)))
    assert snapshot['status'] == 'CONFLICT'
    assert 'foreign_or_manual_position' in snapshot['conflict_reasons']
    assert not snapshot['safe_for_new_entry']


def test_local_and_broker_mismatches_are_detected():
    snapshot = broker_snapshot(api_mock(positions=(position(volume=1, kind=0, sl=0),)))
    comparison = compare_expected(snapshot, {'volume': 2, 'type': 1})
    assert not comparison['matches']
    assert set(comparison['reasons']) == {
        'position_volume_mismatch', 'position_direction_mismatch',
        'broker_position_without_stop'}
    assert not compare_expected(snapshot)['matches']


def test_local_position_missing_at_broker():
    snapshot = broker_snapshot(api_mock())
    comparison = compare_expected(snapshot, {'volume': 1, 'type': 0})
    assert comparison['reasons'] == ['local_state_has_position_but_broker_is_flat']


def test_no_order_is_ever_sent():
    api = api_mock()
    broker_snapshot(api)
    api.order_send.assert_not_called()
