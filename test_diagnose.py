from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from diagnose import collect, validate_bars


def bars():
    return [dict(time=i, open=2, high=3, low=1, close=2.5) for i in (1, 2)]


def test_valid():
    assert validate_bars(bars()) == 2


@pytest.mark.parametrize('value', [None, [], bars()[:1]])
def test_missing(value):
    with pytest.raises(ValueError):
        validate_bars(value)


@pytest.mark.parametrize('field,value', [('time', 1), ('high', 1), ('low', 4), ('open', float('nan')), ('close', -1)])
def test_invalid(field, value):
    data = bars()
    data[1][field] = value
    with pytest.raises(ValueError):
        validate_bars(data)


def test_reject_real_and_disconnect():
    api = Mock()
    api.ACCOUNT_TRADE_MODE_DEMO = 0
    api.account_info.return_value = SimpleNamespace(trade_mode=2)
    with pytest.raises(RuntimeError, match='demo'):
        collect(api, 'terminal')
    api.copy_rates_from_pos.assert_not_called()
    api.order_send.assert_not_called()
    api.shutdown.assert_called_once()


def test_future_timestamp_flagged():
    import time
    api = Mock()
    api.ACCOUNT_TRADE_MODE_DEMO = 0
    api.account_info.return_value = SimpleNamespace(trade_mode=0, server='Demo')
    api.terminal_info.return_value = SimpleNamespace(connected=True, build=1)
    api.symbols_get.return_value = [SimpleNamespace(name='EURUSD', visible=True)]
    api.copy_rates_from_pos.return_value = bars()
    api.symbol_info_tick.return_value = SimpleNamespace(time=time.time() + 10800)
    report = collect(api, 'terminal')
    assert report['time_status'] == 'FUTURE_TIMESTAMP'
    assert report['ready_for_trading'] is False


def test_demo_success():
    api = Mock()
    api.ACCOUNT_TRADE_MODE_DEMO = 0
    api.account_info.return_value = SimpleNamespace(trade_mode=0, server='Demo')
    api.terminal_info.return_value = SimpleNamespace(connected=True, build=1)
    api.symbols_get.return_value = [SimpleNamespace(name='EURUSD', visible=True)]
    api.copy_rates_from_pos.return_value = bars()
    api.symbol_info_tick.return_value = None
    assert collect(api, 'terminal')['closed_m1_bars'] == 2
    api.order_send.assert_not_called()
    api.shutdown.assert_called_once()
