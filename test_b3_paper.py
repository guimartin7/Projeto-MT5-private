from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from b3_instrument import InstrumentSpec
from b3_paper import (initial_state, market_phase, process_bar,
                      validate_state)


TZ = ZoneInfo('America/Sao_Paulo')
SPEC = InstrumentSpec('WINV26', 'IBOVESPA MINI', 5, 1, 1, 1, 1)


def bars(up=True):
    prices = range(100000, 100250, 5) if up else range(100250, 100000, -5)
    return [dict(time=1000 + i * 300, open=p, high=p + 5, low=p - 5,
                 close=p, spread=5, tick_volume=10) for i, p in enumerate(prices)]


def moment(hour=10, minute=0):
    return datetime(2026, 9, 3, hour, minute, tzinfo=TZ)


def test_market_phases():
    assert market_phase(moment(8)) == 'CLOSED'
    assert market_phase(moment(9, 5)) == 'OBSERVE_ONLY'
    assert market_phase(moment(10)) == 'ENTRY_ALLOWED'
    assert market_phase(moment(17, 40)) == 'OBSERVE_ONLY'
    assert market_phase(moment(17, 55)) == 'FLATTEN_ONLY'


def test_one_contract_entry_and_duplicate_guard():
    state, event = process_bar(initial_state(), bars(), SPEC, 100245, 100250,
                               moment(), cost_per_side=1)
    assert event['action'] == 'PAPER_ENTRY'
    assert state['position']['contracts'] == 1
    state, event = process_bar(state, bars(), SPEC, 100245, 100250,
                               moment(), cost_per_side=1)
    assert event['reason'] == 'bar_already_processed'


def test_kill_switch_exits_position():
    state, _ = process_bar(initial_state(), bars(), SPEC, 100245, 100250,
                           moment(), cost_per_side=0)
    newer = bars()
    newer[-1]['time'] += 300
    state, event = process_bar(state, newer, SPEC, 100245, 100250,
                               moment(10, 5), cost_per_side=0, kill_switch=True)
    assert event['action'] == 'PAPER_EXIT'
    assert event['reason'] == 'KILL_SWITCH'
    assert state['position'] is None


def test_invalid_position_is_rejected():
    state = initial_state()
    state['position'] = {'direction': 1, 'contracts': 2}
    with pytest.raises(ValueError, match='posição inválida'):
        validate_state(state)
