import pytest

from b3_candidate_selection import select_candidates_without_reserve
from b3_instrument import InstrumentSpec


SPEC = InstrumentSpec('WINV26', 'IBOVESPA MINI', 5, 1, 1, 1, 1)


def bars(count=1200):
    prices = [150000 + index * 5 + (index % 30) * 2 for index in range(count)]
    return [dict(time=1756728000 + index * 300, open=price,
                 high=price + 10, low=price - 10, close=price,
                 tick_volume=10, spread=5) for index, price in enumerate(prices)]


def test_selector_never_executes_or_reports_reserve_performance():
    report = select_candidates_without_reserve(bars(), SPEC)
    assert report['development_bars'] == 720
    assert report['validation_bars'] == 240
    assert report['reserve']['bars'] == 240
    assert report['reserve']['executed'] is False
    assert report['reserve']['performance'] is None
    assert report['approved_for_orders'] is False
    assert len(report['candidates']) == 5


def test_selector_requires_enough_history():
    with pytest.raises(ValueError, match='1.000'):
        select_candidates_without_reserve(bars(999), SPEC)
