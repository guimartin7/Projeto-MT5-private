import pytest

from b3_signals import build_directions, strategy_label


def bars(prices):
    return [dict(open=value, high=value + 1, low=value - 1, close=value)
            for value in prices]


def test_sma_signal_and_label():
    directions = build_directions(bars(range(20)), 'sma', fast=2, slow=4)
    assert directions[-1] == 1
    assert strategy_label('sma', 2, 4) == 'SMA 2/4'


def test_breakout_waits_then_carries_direction():
    sample = bars([10, 10, 10, 15, 14])
    directions = build_directions(sample, 'breakout', breakout_window=3)
    assert directions[2] is None
    assert directions[3:] == [1, 1]


def test_unknown_strategy_is_rejected():
    with pytest.raises(ValueError, match='desconhecida'):
        build_directions(bars(range(10)), 'magic')


def test_sma_gap_filter_keeps_previous_signal_during_weak_cross():
    prices = list(range(30)) + [29]
    directions = build_directions(bars(prices), 'sma', fast=2, slow=4,
                                  min_ma_gap_points=1)
    assert directions[29] == 1
    assert directions[-1] == 1
