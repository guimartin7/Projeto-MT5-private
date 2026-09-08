import json
from datetime import datetime
from zoneinfo import ZoneInfo

from dashboard_model import (load_dashboard_snapshot, market_status,
                             synchronization_status)

TZ = ZoneInfo('America/Sao_Paulo')


def test_market_status_reflects_weekend_holiday_and_open_window():
    assert market_status(datetime(2026, 9, 6, 10, tzinfo=TZ))['code'] == 'CLOSED'
    assert market_status(datetime(2026, 9, 7, 10, tzinfo=TZ))['code'] == 'CLOSED'
    assert market_status(datetime(2026, 9, 8, 10, tzinfo=TZ))['code'] == 'OPEN'


def test_synchronization_status_classifies_fresh_and_stale_data():
    snapshot = {'updated_at_utc': '2026-09-08T13:00:00+00:00'}
    now = datetime(2026, 9, 8, 13, 1, tzinfo=ZoneInfo('UTC'))
    assert synchronization_status(snapshot, now)['code'] == 'ON'
    now = datetime(2026, 9, 8, 13, 10, tzinfo=ZoneInfo('UTC'))
    assert synchronization_status(snapshot, now)['code'] == 'WARN'


def test_dashboard_snapshot_is_read_only_and_surfaces_state(tmp_path):
    path = tmp_path / 'state.json'
    path.write_text(json.dumps({
        'mode': 'B3_LOCAL_PAPER_ONLY', 'symbol': 'WINV26',
        'balance': 480, 'equity': 475, 'position': None,
        'entries_today': 2, 'daily_realized_pnl': -20,
        'drawdown_reais': -25, 'updated_at_utc': '2026-09-04T12:00:00Z',
    }), encoding='utf-8')
    snapshot = load_dashboard_snapshot(path)
    assert snapshot['balance'] == 480
    assert snapshot['entries_today'] == 2
    assert snapshot['read_only'] is True
    assert 'order_send' not in snapshot
    assert snapshot['market']['code'] in {'OPEN', 'OBSERVE_ONLY', 'FLATTEN_ONLY', 'CLOSED'}


def test_dashboard_snapshot_handles_missing_state(tmp_path):
    snapshot = load_dashboard_snapshot(tmp_path / 'missing.json')
    assert snapshot['mode'] == 'NO_PAPER_STATE'
    assert snapshot['error']
    assert snapshot['read_only'] is True


def test_dashboard_snapshot_surfaces_market_scan(tmp_path):
    (tmp_path / 'market-scan.json').write_text(
        json.dumps({'contracts_found': 3, 'quote_available': 1}), encoding='utf-8')
    snapshot = load_dashboard_snapshot(tmp_path / 'state.json')
    assert snapshot['scanner']['quote_available'] == 1


def test_fresh_market_scan_makes_sync_status_current(tmp_path):
    (tmp_path / 'state.json').write_text(json.dumps({
        'mode': 'B3_LOCAL_PAPER_ONLY', 'symbol': 'WINV26',
        'balance': 500, 'equity': 500,
        'updated_at_utc': '2026-09-08T12:00:00+00:00'}), encoding='utf-8')
    (tmp_path / 'market-scan.json').write_text(json.dumps({
        'contracts_found': 3, 'quote_available': 0,
        'captured_at_utc': '2026-09-08T13:00:00+00:00'}), encoding='utf-8')
    snapshot = load_dashboard_snapshot(tmp_path / 'state.json')
    now = datetime(2026, 9, 8, 13, 0, 30, tzinfo=ZoneInfo('UTC'))
    assert synchronization_status({**snapshot, 'scanner': snapshot['scanner']}, now)['code'] == 'ON'
