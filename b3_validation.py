"""Métricas e critérios objetivos para avaliar backtests do WIN."""
import math
from dataclasses import asdict, dataclass
from statistics import mean, median, stdev


@dataclass(frozen=True)
class ResearchGate:
    min_out_of_sample_trades: int = 30
    min_profit_factor: float = 1.20
    max_drawdown_pct: float = 20.0
    require_positive_development: bool = True
    require_positive_expectancy_lower_bound: bool = True

    def to_dict(self):
        return asdict(self)


DEFAULT_RESEARCH_GATE = ResearchGate()


def trade_statistics(trades, initial_balance, max_drawdown_reais):
    pnls = [float(trade['net_pnl']) for trade in trades]
    wins = [value for value in pnls if value > 0]
    losses = [value for value in pnls if value < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = (gross_profit / gross_loss if gross_loss else None)
    expectancy = mean(pnls) if pnls else 0.0
    sample_deviation = stdev(pnls) if len(pnls) >= 2 else 0.0
    margin = 1.96 * sample_deviation / math.sqrt(len(pnls)) if pnls else 0.0
    consecutive = worst_consecutive_losses(pnls)
    return {
        'sample_size': len(pnls),
        'gross_profit_reais': round(gross_profit, 2),
        'gross_loss_reais': round(gross_loss, 2),
        'profit_factor': None if profit_factor is None else round(profit_factor, 4),
        'expectancy_reais_per_trade': round(expectancy, 2),
        'median_pnl_reais': round(median(pnls), 2) if pnls else 0.0,
        'largest_win_reais': round(max(wins), 2) if wins else 0.0,
        'largest_loss_reais': round(min(losses), 2) if losses else 0.0,
        'max_consecutive_losses': consecutive,
        'max_drawdown_pct': round(abs(float(max_drawdown_reais)) /
                                  float(initial_balance) * 100, 2),
        'approx_expectancy_95pct_interval': [round(expectancy - margin, 2),
                                              round(expectancy + margin, 2)],
        'interval_note': 'Aproximação normal exploratória; não prova lucro futuro.',
    }


def worst_consecutive_losses(pnls):
    worst = current = 0
    for value in pnls:
        current = current + 1 if value < 0 else 0
        worst = max(worst, current)
    return worst


def evaluate_research_gate(development, out_of_sample,
                           policy=DEFAULT_RESEARCH_GATE):
    metrics = out_of_sample['statistics']
    factor = metrics['profit_factor']
    checks = {
        'enough_out_of_sample_trades': (
            metrics['sample_size'] >= policy.min_out_of_sample_trades),
        'positive_out_of_sample_net_pnl': out_of_sample['net_pnl'] > 0,
        'positive_out_of_sample_expectancy': (
            metrics['expectancy_reais_per_trade'] > 0),
        'minimum_out_of_sample_profit_factor': (
            factor is not None and factor >= policy.min_profit_factor),
        'maximum_out_of_sample_drawdown': (
            metrics['max_drawdown_pct'] <= policy.max_drawdown_pct),
        'maximum_development_drawdown': (
            development['statistics']['max_drawdown_pct'] <=
            policy.max_drawdown_pct),
        'positive_expectancy_confidence_lower_bound': (
            metrics['approx_expectancy_95pct_interval'][0] > 0
            if policy.require_positive_expectancy_lower_bound else True),
        'positive_development_net_pnl': (
            development['net_pnl'] > 0 if policy.require_positive_development else True),
    }
    failed = [name for name, passed in checks.items() if not passed]
    return {
        'verdict': 'PASS_RESEARCH_GATE' if not failed else 'FAIL_RESEARCH_GATE',
        'policy': policy.to_dict(),
        'checks': checks,
        'failed_checks': failed,
        'approved_for_orders': False,
        'warning': ('Passar neste portão permite apenas avançar a pesquisa; '
                    'nunca autoriza execução Demo ou real.'),
    }
