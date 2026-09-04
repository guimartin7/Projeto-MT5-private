from b3_instrument import InstrumentSpec
from b3_stress import run_stress_test


SPEC = InstrumentSpec('WINV26', 'IBOVESPA MINI', 5, 1, 1, 1, 1)


def bars(count=1200):
    return [dict(time=1756728000 + index * 300,
                 open=150000 + index * 5,
                 high=150010 + index * 5,
                 low=149990 + index * 5,
                 close=150000 + index * 5,
                 tick_volume=10, spread=5)
            for index in range(count)]


def test_stress_test_keeps_scenarios_separate_and_never_approves_orders():
    report = run_stress_test(bars(), SPEC)
    assert [item['name'] for item in report['scenarios']] == [
        'baseline', 'adverse', 'severe']
    assert report['approved_for_orders'] is False
    assert isinstance(report['robust_across_all_scenarios'], bool)
    assert all('failed_checks' in item for item in report['scenarios'])
