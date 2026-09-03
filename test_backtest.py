from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from backtest import (benchmark_buy_hold, evaluate_segments, fetch_closed_bars,
                      relative_strength_index, run_backtest,
                      run_strategy_backtest, simple_moving_average,
                      strategy_positions)


def make_bars(prices):
    return [dict(time=index + 1, open=price, high=price + .1, low=price - .1,
                 close=price, tick_volume=10, spread=1) for index, price in enumerate(prices)]


def test_moving_average():
    assert simple_moving_average([1, 2, 3, 4], 3) == [None, None, 2, 3]


def test_rsi_and_distinct_strategies():
    data = make_bars([10, 9, 8, 7, 8, 9, 10, 11, 10, 9] * 10)
    rsi = relative_strength_index([bar['close'] for bar in data], 3)
    assert rsi[3] == 0
    for strategy, parameters in (
        ('momentum_breakout', {'entry_window': 4, 'exit_window': 2}),
        ('rsi_mean_reversion', {'rsi_window': 3, 'entry_level': 30, 'exit_level': 55}),
    ):
        positions, warmup = strategy_positions(data, strategy, **parameters)
        assert len(positions) == len(data)
        assert warmup >= 2
        assert run_strategy_backtest(data, strategy, parameters, cost_bps=0)['strategy'] == strategy


def test_backtest_returns_metrics_and_charges_costs():
    prices = [10] * 6 + [11, 12, 13, 14] + [13, 12, 11, 10]
    free = run_backtest(make_bars(prices), fast=2, slow=3, cost_bps=0)
    paid = run_backtest(make_bars(prices), fast=2, slow=3, cost_bps=10)
    assert free['trades'] == 1
    assert paid['final_equity'] < free['final_equity']
    assert paid['max_drawdown_pct'] <= 0


def test_bad_parameters():
    data = make_bars(range(1, 10))
    with pytest.raises(ValueError):
        run_backtest(data, fast=4, slow=3)


def test_signal_executes_at_next_open():
    data = make_bars([10] * 6 + [11, 12, 13, 14, 13, 12, 11, 10])
    data[7].update(open=99, high=100, low=11.9)
    report = run_backtest(data, fast=2, slow=3, cost_bps=0)
    assert report['trade_log'][0]['price'] == 99


def test_segments_and_benchmarks():
    data = make_bars([10 + index / 10 for index in range(100)])
    report = evaluate_segments(data, 2, 5, 0, train_ratio=.7)
    assert report['train_bars'] == 70
    assert report['test_bars'] == 30
    assert report['buy_hold_test_return_pct'] > 0
    assert report['no_trade_test_return_pct'] == 0


def test_fetch_refuses_real_account_and_never_trades():
    api = Mock()
    api.ACCOUNT_TRADE_MODE_DEMO = 0
    api.account_info.return_value = SimpleNamespace(trade_mode=2)
    with pytest.raises(RuntimeError, match='demo'):
        fetch_closed_bars(api, 'terminal', 'EURUSD', 5, 100)
    api.copy_rates_from_pos.assert_not_called()
    api.order_send.assert_not_called()
    api.shutdown.assert_called_once()
