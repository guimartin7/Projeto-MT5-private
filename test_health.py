from health import assess_feed


def test_accepts_quote_with_three_hour_server_shift():
    report = assess_feed(10805, 1.1, 1.2, now=0, max_age_seconds=10)
    assert report['healthy']
    assert report['normalized_tick_age_seconds'] == -5
    assert report['estimated_server_shift_hours'] == 3


def test_rejects_stale_missing_and_inverted_quotes():
    assert not assess_feed(None, None, None, now=0)['healthy']
    assert assess_feed(1000, 1, 2, now=2000, max_age_seconds=10)['status'] == 'STALE_OR_FUTURE_TICK'
    assert assess_feed(0, 2, 1, now=0)['status'] == 'INVALID_QUOTE'
