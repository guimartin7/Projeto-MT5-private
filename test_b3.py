from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from b3_backtest import evaluate_futures_periods, run_futures_backtest
from b3_instrument import InstrumentSpec, futures_pnl, load_b3_spec


SPEC = InstrumentSpec('WINV26', 'IBOVESPA MINI', 5, 1, 1, 1, 1)


def bars(count=200):
    base = 150000
    return [dict(time=1756728000 + index * 300, open=base + index * 5,
                 high=base + index * 5 + 10, low=base + index * 5 - 10,
                 close=base + index * 5, tick_volume=10, spread=5)
            for index in range(count)]


def test_win_point_value_and_pnl():
    assert SPEC.value_per_point == .2
    assert futures_pnl(100000, 100100, 1, 1, SPEC) == 20
    assert futures_pnl(100000, 99900, -1, 1, SPEC) == 20


def test_profile_requires_clear_demo():
    api = Mock(ACCOUNT_TRADE_MODE_DEMO=0)
    api.account_info.return_value = SimpleNamespace(trade_mode=2, server='ClearInvestimentos')
    with pytest.raises(RuntimeError, match='demo'):
        load_b3_spec(api, 'WINV26')


def test_profile_from_broker():
    api = Mock(ACCOUNT_TRADE_MODE_DEMO=0)
    api.account_info.return_value = SimpleNamespace(trade_mode=0, server='ClearInvestimentos-DEMO')
    api.symbol_info.return_value = SimpleNamespace(
        description='IBOVESPA MINI', trade_tick_size=5, trade_tick_value=1,
        volume_min=1, volume_step=1, expiration_time=123)
    assert load_b3_spec(api, 'WINV26').value_per_point == .2


def test_backtest_is_one_contract_and_never_approved():
    report = run_futures_backtest(bars(), SPEC, cost_per_side=0)
    assert report['contracts'] == 1
    assert report['approved_for_orders'] is False
    with pytest.raises(ValueError, match='1 contrato'):
        run_futures_backtest(bars(), SPEC, contracts=2)


def test_period_split_is_chronological():
    report = evaluate_futures_periods(bars(1200), SPEC, cost_per_side=0)
    assert report['development_bars'] == 840
    assert report['out_of_sample_bars'] == 360
    assert report['approved_for_orders'] is False
    assert report['research_gate']['approved_for_orders'] is False
    assert report['research_gate']['verdict'] in {
        'PASS_RESEARCH_GATE', 'FAIL_RESEARCH_GATE'}


def test_backtest_includes_trade_statistics():
    report = run_futures_backtest(bars(), SPEC, cost_per_side=0)
    assert report['statistics']['sample_size'] == report['trades']
    assert 'profit_factor' in report['statistics']
    assert 'approx_expectancy_95pct_interval' in report['statistics']


def test_backtest_accepts_trend_strength_filter():
    report = run_futures_backtest(bars(), SPEC, min_ma_gap_points=10,
                                  cost_per_side=0)
    assert report['min_ma_gap_points'] == 10


def test_insufficient_capital_blocks_entries():
    report = run_futures_backtest(bars(), SPEC, initial_balance=10,
                                  stop_reais=20, cost_per_side=1)
    assert report['trades'] == 0
    assert report['capital_blocks'] > 0


def test_strategy_drawdown_limit_stops_new_entries():
    adverse = bars(500)
    for index, bar in enumerate(adverse):
        price = 150000 + (50 if (index // 12) % 2 else 0)
        bar.update(open=price, high=price + 10, low=price - 10, close=price)
    report = run_futures_backtest(adverse, SPEC, initial_balance=500,
                                  max_strategy_drawdown_reais=1,
                                  cost_per_side=1)
    assert report['drawdown_blocks'] > 0
    assert report['max_strategy_drawdown_reais'] == 1
