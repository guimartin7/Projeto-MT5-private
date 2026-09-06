import json
from datetime import datetime
from zoneinfo import ZoneInfo

from dashboard_model import load_dashboard_snapshot, market_status

TZ = ZoneInfo('America/Sao_Paulo')


def test_market_status_reflects_weekend_holiday_and_open_window():
    assert market_status(datetime(2026, 9, 6, 10, tzinfo=TZ))['code'] == 'CLOSED'
    assert market_status(datetime(2026, 9, 7, 10, tzinfo=TZ))['code'] == 'CLOSED'
    assert market_status(datetime(2026, 9, 8, 10, tzinfo=TZ))['code'] == 'OPEN'


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
