"""Verificações de saúde do feed sem depender do fuso do servidor MT5."""
from datetime import datetime, timezone


def assess_feed(tick_time, bid, ask, now=None, max_age_seconds=120):
    now = datetime.now(timezone.utc).timestamp() if now is None else now
    if tick_time is None or bid is None or ask is None:
        return {'healthy': False, 'status': 'MISSING_TICK'}
    raw_offset = float(tick_time) - now
    server_shift = round(raw_offset / 3600) * 3600
    normalized_age = now - (float(tick_time) - server_shift)
    if bid <= 0 or ask <= 0 or ask < bid:
        status = 'INVALID_QUOTE'
    elif abs(normalized_age) > max_age_seconds:
        status = 'STALE_OR_FUTURE_TICK'
    else:
        status = 'OK'
    return {
        'healthy': status == 'OK',
        'status': status,
        'bid': float(bid), 'ask': float(ask),
        'spread': float(ask - bid),
        'normalized_tick_age_seconds': round(normalized_age, 1),
        'estimated_server_shift_hours': server_shift / 3600,
    }
