from data_audit import audit_bars


def test_audit_detects_gap_and_clock_shift():
    bars = [{'time': value} for value in (0, 300, 900)]
    report = audit_bars(bars, 'M5', tick_time=10800, checked_at=0)
    assert report['irregular_gap_count'] == 1
    assert report['estimated_missing_slots_including_market_closures'] == 1
    assert report['estimated_server_utc_shift_hours'] == 3
    assert report['timezone_interpretation'] == 'LIKELY_SERVER_TIME_ENCODED_AS_UTC'


def test_regular_series():
    report = audit_bars([{'time': 0}, {'time': 60}], 'M1', tick_time=0, checked_at=0)
    assert report['irregular_gap_count'] == 0
    assert report['timezone_interpretation'] == 'UTC_ALIGNED'
