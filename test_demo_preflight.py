from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest

from b3_instrument import InstrumentSpec
from demo_preflight import PreflightConfig, build_request, round_to_tick, run_preflight, validate_context


TZ = ZoneInfo('America/Sao_Paulo')


def api_mock():
    api = Mock()
    api.ACCOUNT_TRADE_MODE_DEMO = api.ACCOUNT_MARGIN_MODE_RETAIL_NETTING = 0
    api.TRADE_ACTION_DEAL, api.ORDER_TYPE_BUY, api.ORDER_TYPE_SELL = 1, 0, 1
    api.ORDER_TIME_DAY = api.ORDER_FILLING_IOC = 1
    api.terminal_info.return_value = SimpleNamespace(connected=True, trade_allowed=True, tradeapi_disabled=False)
    api.account_info.return_value = SimpleNamespace(trade_mode=0, server='ClearInvestimentos-DEMO', margin_mode=0, trade_allowed=True, trade_expert=True)
    api.positions_get.return_value = api.orders_get.return_value = ()
    api.symbol_info.return_value = SimpleNamespace(description='IBOVESPA MINI', trade_tick_size=5, trade_tick_value=1, volume_min=1, volume_step=1, expiration_time=1)
    api.symbol_info_tick.return_value = SimpleNamespace(time=0, bid=100000, ask=100005)
    api.order_calc_margin.return_value = 100
    api.order_check.return_value = SimpleNamespace(retcode=0, comment='Done')
    return api


def trading_time():
    return datetime(2026, 9, 3, 10, 0, tzinfo=TZ)


def test_request_has_server_side_protection(monkeypatch):
    api = api_mock()
    spec = InstrumentSpec('WINV26', '', 5, 1, 1, 1, 1)
    monkeypatch.setattr('demo_preflight.assess_feed', lambda *args: {'healthy': True, 'status': 'OK'})
    request, _ = build_request(api, PreflightConfig(), spec)
    assert round_to_tick(100003, 5) == 100005
    assert (request['volume'], request['sl'], request['tp']) == (1, 99905, 100205)


def test_context_guards():
    api = api_mock(); api.account_info.return_value.trade_mode = 2
    with pytest.raises(RuntimeError, match='Demo'): validate_context(api, PreflightConfig(), trading_time())
    api = api_mock(); api.positions_get.return_value = (object(),)
    with pytest.raises(RuntimeError, match='posição'): validate_context(api, PreflightConfig(), trading_time())
    api = api_mock(); api.terminal_info.return_value.trade_allowed = False
    with pytest.raises(RuntimeError, match='desabilitada'): validate_context(api, PreflightConfig(), trading_time())


def test_preflight_never_sends(monkeypatch):
    api = api_mock()
    monkeypatch.setattr('demo_preflight.assess_feed', lambda *args: {'healthy': True, 'status': 'OK'})
    report = run_preflight(api, PreflightConfig(), trading_time())
    assert report['check_approved'] and not report['would_send_order']
    api.order_check.assert_called_once(); api.order_send.assert_not_called()


def test_scope_is_one_winv26():
    api = api_mock()
    with pytest.raises(RuntimeError, match='1 contrato'): validate_context(api, PreflightConfig(volume=2), trading_time())
    with pytest.raises(RuntimeError, match='1 contrato'): validate_context(api, PreflightConfig(symbol='WDOV26'), trading_time())
