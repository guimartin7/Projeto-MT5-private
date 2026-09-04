"""Modelo puro do painel local; não conecta ao MT5 nem envia ordens."""
import json
from datetime import datetime, timezone
from pathlib import Path


def load_dashboard_snapshot(state_path, readiness=None):
    state = {}
    error = None
    path = Path(state_path)
    if path.exists():
        try:
            state = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            error = str(exc)
    else:
        error = 'Nenhum estado de paper trading encontrado.'
    snapshot = {
        'mode': state.get('mode', 'NO_PAPER_STATE'),
        'symbol': state.get('symbol', 'WINV26'),
        'balance': state.get('balance', 0.0),
        'equity': state.get('equity', state.get('balance', 0.0)),
        'position': state.get('position'),
        'entries_today': state.get('entries_today', 0),
        'daily_realized_pnl': state.get('daily_realized_pnl', 0.0),
        'drawdown_reais': state.get('drawdown_reais', 0.0),
        'updated_at_utc': state.get('updated_at_utc'),
        'feed_health': state.get('feed_health', {}),
        'readiness': readiness or {'ready': False, 'blockers': ['paper_only_dashboard']},
        'error': error,
        'read_only': True,
        'captured_at_utc': datetime.now(timezone.utc).isoformat(),
    }
    return snapshot
