"""Motor de risco para simulação local; não possui integração com ordens."""
from dataclasses import dataclass


@dataclass(frozen=True)
class RiskLimits:
    max_daily_loss_pct: float = 1.0
    max_drawdown_pct: float = 2.0
    max_entries_per_day: int = 5


def update_risk_state(state, equity, session_date):
    if state.get('session_date') != session_date:
        state['session_date'] = session_date
        state['daily_start_equity'] = equity
        state['entries_today'] = 0
    state['peak_equity'] = max(float(state.get('peak_equity', equity)), equity)
    state['daily_return_pct'] = (equity / state['daily_start_equity'] - 1) * 100
    state['drawdown_pct'] = (equity / state['peak_equity'] - 1) * 100
    return state


def entry_risk_check(state, limits, kill_switch=False):
    reasons = []
    if kill_switch:
        reasons.append('kill_switch_active')
    if state.get('daily_return_pct', 0) <= -limits.max_daily_loss_pct:
        reasons.append('daily_loss_limit')
    if state.get('drawdown_pct', 0) <= -limits.max_drawdown_pct:
        reasons.append('drawdown_limit')
    if state.get('entries_today', 0) >= limits.max_entries_per_day:
        reasons.append('daily_entry_limit')
    return {'allowed': not reasons, 'reasons': reasons}
