from pathlib import Path

import pytest

from paper_trade import (INITIAL_STATE, load_state, process_latest_closed_bar,
                         save_state, validate_state)
from risk import RiskLimits


def bars(up=True):
    prices = list(range(100, 160)) if up else list(range(160, 100, -1))
    return [dict(time=i * 300, open=p, high=p + 1, low=p - 1, close=p,
                 spread=2, tick_volume=10) for i, p in enumerate(prices)]


def test_paper_buy_and_duplicate_protection():
    state, event = process_latest_closed_bar(dict(INITIAL_STATE), bars(), .01, 0)
    assert event['action'] == 'PAPER_BUY'
    assert state['position'] == 'LONG'
    same, event = process_latest_closed_bar(state, bars(), .01, 0)
    assert event['action'] == 'WAIT'
    assert len(same['trades']) == 1


def test_paper_sell_without_mt5_order():
    state, _ = process_latest_closed_bar(dict(INITIAL_STATE), bars(), .01, 0)
    falling = bars(False)
    for index, bar in enumerate(falling):
        bar['time'] += 100000
    state, event = process_latest_closed_bar(state, falling, .01, 0)
    assert event['action'] == 'PAPER_SELL'
    assert state['position'] == 'FLAT'


def test_state_roundtrip_and_mode_guard(tmp_path):
    path = tmp_path / 'state.json'
    save_state(path, dict(INITIAL_STATE))
    assert load_state(path)['mode'] == 'LOCAL_PAPER_ONLY'
    path.write_text('{"mode":"REAL"}', encoding='utf-8')
    with pytest.raises(ValueError, match='recusado'):
        load_state(path)


def test_old_state_is_migrated(tmp_path):
    path = tmp_path / 'old.json'
    path.write_text('{"mode":"LOCAL_PAPER_ONLY","cash":9000}', encoding='utf-8')
    state = load_state(path)
    assert state['cash'] == 9000
    assert state['entries_today'] == 0
    assert state['daily_return_pct'] == 0


def test_kill_switch_blocks_new_entry():
    state, event = process_latest_closed_bar(
        dict(INITIAL_STATE), bars(), .01, 0, RiskLimits(), kill_switch=True)
    assert event['action'] == 'RISK_BLOCK'
    assert event['reasons'] == ['kill_switch_active']
    assert state['position'] == 'FLAT'


def test_live_quote_is_used_for_paper_fill():
    state, event = process_latest_closed_bar(dict(INITIAL_STATE), bars(), .01, 0,
                                             quote=(150, 151))
    assert event['price'] == 151


def test_inconsistent_state_is_rejected():
    broken = dict(INITIAL_STATE, position='FLAT', units=1)
    with pytest.raises(ValueError, match='inconsistente'):
        validate_state(broken)
