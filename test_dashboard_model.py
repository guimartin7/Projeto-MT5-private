import json

from dashboard_model import load_dashboard_snapshot


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


def test_dashboard_snapshot_handles_missing_state(tmp_path):
    snapshot = load_dashboard_snapshot(tmp_path / 'missing.json')
    assert snapshot['mode'] == 'NO_PAPER_STATE'
    assert snapshot['error']
    assert snapshot['read_only'] is True
