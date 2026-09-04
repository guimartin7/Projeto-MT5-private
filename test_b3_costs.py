from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from b3_costs import B3CostModel, DEFAULT_WIN_COSTS
from margin_diagnostic import calculate_margin_report


def api_with_tick(bid, ask):
    api = Mock(ACCOUNT_TRADE_MODE_DEMO=0, ORDER_TYPE_BUY=0, ORDER_TYPE_SELL=1)
    api.account_info.return_value = SimpleNamespace(
        trade_mode=0, server='ClearInvestimentos-DEMO')
    api.symbol_info.return_value = SimpleNamespace(
        description='IBOVESPA MINI', trade_tick_size=5, trade_tick_value=1,
        volume_min=1, volume_step=1, expiration_time=123)
    api.symbol_info_tick.return_value = SimpleNamespace(bid=bid, ask=ask)
    return api


def test_default_cost_model_is_explicit_and_conservative():
    assert DEFAULT_WIN_COSTS.broker_commission_per_side == 0
    assert DEFAULT_WIN_COSTS.normal_cost_per_side == 1
    assert DEFAULT_WIN_COSTS.normal_round_trip_cost == 2
    assert DEFAULT_WIN_COSTS.to_dict()['sources']['clear_costs'].startswith('https://')


def test_cost_model_rejects_negative_values():
    with pytest.raises(ValueError, match='negativas'):
        B3CostModel(exchange_fees_per_side=-1)


def test_margin_diagnostic_uses_broker_calculation_without_sending():
    api = api_with_tick(150000, 150005)
    api.order_calc_margin.side_effect = [155.0, 156.0]
    report = calculate_margin_report(api)
    assert report['status'] == 'OK'
    assert report['broker_buy_margin'] == 155
    assert report['broker_sell_margin'] == 156
    assert report['order_send_called'] is False
    api.order_calc_margin.assert_any_call(0, 'WINV26', 1.0, 150005)


def test_margin_diagnostic_does_not_calculate_with_zero_quote():
    api = api_with_tick(0, 0)
    report = calculate_margin_report(api)
    assert report['status'] == 'UNAVAILABLE_NO_VALID_QUOTE'
    api.order_calc_margin.assert_not_called()
