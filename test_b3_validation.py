from b3_validation import (ResearchGate, evaluate_research_gate,
                           trade_statistics, worst_consecutive_losses)


def result(pnls, drawdown=-50, initial=500):
    trades = [{'net_pnl': pnl} for pnl in pnls]
    return {
        'net_pnl': sum(pnls), 'initial_balance': initial,
        'statistics': trade_statistics(trades, initial, drawdown),
    }


def test_trade_statistics_exposes_risk_and_expectancy():
    stats = trade_statistics([{'net_pnl': value} for value in (10, -5, -5, 20)],
                             500, -50)
    assert stats['profit_factor'] == 3
    assert stats['expectancy_reais_per_trade'] == 5
    assert stats['max_drawdown_pct'] == 10
    assert stats['max_consecutive_losses'] == 2


def test_worst_consecutive_losses_resets_after_win():
    assert worst_consecutive_losses([-1, -2, 3, -4]) == 2


def test_gate_fails_small_out_of_sample_even_if_profitable():
    gate = evaluate_research_gate(result([10] * 30), result([20, -5]))
    assert gate['verdict'] == 'FAIL_RESEARCH_GATE'
    assert 'enough_out_of_sample_trades' in gate['failed_checks']
    assert gate['approved_for_orders'] is False


def test_gate_passes_research_only_when_all_checks_pass():
    policy = ResearchGate(min_out_of_sample_trades=6)
    gate = evaluate_research_gate(result([5] * 10, -20),
                                  result([10, 10, 10, -1] * 2, -40), policy)
    assert gate['verdict'] == 'PASS_RESEARCH_GATE'
    assert gate['failed_checks'] == []
    assert gate['approved_for_orders'] is False
