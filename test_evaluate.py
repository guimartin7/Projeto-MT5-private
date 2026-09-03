import pytest

from evaluate import evaluate_candidates


def make_bars(count=1200):
    prices = [100 + index * .01 + (index % 20) * .02 for index in range(count)]
    return [dict(time=index * 300, open=price, high=price + .1, low=price - .1,
                 close=price, tick_volume=10, spread=1)
            for index, price in enumerate(prices)]


def test_three_way_evaluation_only_runs_selected_on_holdout():
    report = evaluate_candidates(make_bars(), cost_bps=0)
    assert report['development_bars'] == 720
    assert report['validation_bars'] == 240
    assert report['holdout_bars'] == 240
    assert len(report['candidates']) == 3
    assert report['selected_candidate'] in {item['name'] for item in report['candidates']}
    assert {item['strategy'] for item in report['candidates']} == {
        'sma_trend', 'momentum_breakout', 'rsi_mean_reversion'}
    assert 'trade_log' in report['holdout_result']


def test_requires_enough_history():
    with pytest.raises(ValueError, match='1.000'):
        evaluate_candidates(make_bars(999))
