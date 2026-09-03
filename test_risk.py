from risk import RiskLimits, entry_risk_check, update_risk_state


def test_daily_reset_and_loss_block():
    state = {}
    update_risk_state(state, 10000, '2026-09-02')
    update_risk_state(state, 9890, '2026-09-02')
    decision = entry_risk_check(state, RiskLimits(max_daily_loss_pct=1))
    assert not decision['allowed']
    assert 'daily_loss_limit' in decision['reasons']
    update_risk_state(state, 9890, '2026-09-03')
    assert state['entries_today'] == 0
    assert state['daily_return_pct'] == 0


def test_drawdown_entries_and_kill_switch():
    state = {'drawdown_pct': -2.1, 'daily_return_pct': 0, 'entries_today': 5}
    decision = entry_risk_check(state, RiskLimits(), kill_switch=True)
    assert set(decision['reasons']) == {
        'kill_switch_active', 'drawdown_limit', 'daily_entry_limit'}


def test_risk_allows_healthy_state():
    state = {'drawdown_pct': -.2, 'daily_return_pct': -.1, 'entries_today': 1}
    assert entry_risk_check(state, RiskLimits())['allowed']
