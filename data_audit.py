"""Auditoria de integridade e horario de series de candles."""
from collections import Counter
from datetime import datetime, timezone


TIMEFRAME_SECONDS = {'M1': 60, 'M5': 300, 'M15': 900, 'H1': 3600}


def audit_bars(bars, timeframe_name, tick_time=None, checked_at=None):
    interval = TIMEFRAME_SECONDS[timeframe_name]
    stamps = [int(bar['time']) for bar in bars]
    gaps = [right - left for left, right in zip(stamps, stamps[1:])]
    irregular = [gap for gap in gaps if gap != interval]
    # Finais de semana e pausas de mercado sao informados, nao preenchidos artificialmente.
    largest = max(gaps, default=0)
    missing_slots = sum(max(0, gap // interval - 1) for gap in irregular)
    now = datetime.now(timezone.utc).timestamp() if checked_at is None else checked_at
    tick_offset = None if tick_time is None else tick_time - now
    estimated_shift = None if tick_offset is None else round(tick_offset / 3600) * 3600
    return {
        'expected_interval_seconds': interval,
        'irregular_gap_count': len(irregular),
        'estimated_missing_slots_including_market_closures': missing_slots,
        'largest_gap_seconds': largest,
        'gap_seconds_frequency': dict(Counter(irregular).most_common(10)),
        'tick_clock_offset_seconds': None if tick_offset is None else round(tick_offset, 1),
        'estimated_server_utc_shift_hours': None if estimated_shift is None else estimated_shift / 3600,
        'timezone_interpretation': (
            'UNVERIFIED' if tick_offset is None else
            ('LIKELY_SERVER_TIME_ENCODED_AS_UTC' if abs(tick_offset) > 1800 else 'UTC_ALIGNED')
        ),
        'warning': 'Lacunas podem ser fechamento do mercado; calendario do ativo ainda nao e aplicado.',
    }
