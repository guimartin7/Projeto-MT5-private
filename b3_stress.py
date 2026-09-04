"""Cenários adversos fixos para o backtest do WIN, sem otimização."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from b3_backtest import evaluate_futures_periods
from b3_instrument import load_b3_spec
from backtest import fetch_closed_bars


STRESS_SCENARIOS = (
    {'name': 'baseline', 'cost_per_side': 1.0, 'slippage_ticks': 1.0},
    {'name': 'adverse', 'cost_per_side': 2.0, 'slippage_ticks': 2.0},
    {'name': 'severe', 'cost_per_side': 3.0, 'slippage_ticks': 3.0},
)


def run_stress_test(bars, spec, scenarios=STRESS_SCENARIOS, **kwargs):
    results = []
    for scenario in scenarios:
        report = evaluate_futures_periods(
            bars, spec, cost_per_side=scenario['cost_per_side'],
            slippage_ticks=scenario['slippage_ticks'], **kwargs)
        results.append({
            **scenario,
            'development_net_pnl': report['development']['net_pnl'],
            'out_of_sample_net_pnl': report['out_of_sample']['net_pnl'],
            'out_of_sample_drawdown_pct':
                report['out_of_sample']['statistics']['max_drawdown_pct'],
            'out_of_sample_trades': report['out_of_sample']['trades'],
            'research_verdict': report['research_gate']['verdict'],
            'failed_checks': report['research_gate']['failed_checks'],
        })
    all_pass = all(item['research_verdict'] == 'PASS_RESEARCH_GATE'
                   for item in results)
    return {
        'mode': 'B3_EXPLORATORY_STRESS_ONLY',
        'rule': 'fixed scenarios; no parameter selection from these results',
        'scenarios': results,
        'robust_across_all_scenarios': all_pass,
        'approved_for_orders': False,
        'warning': 'Resultado exploratório; dados futuros ainda são necessários.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--terminal', default=r'C:\Program Files\MetaTrader 5\terminal64.exe')
    parser.add_argument('--symbol', default='WINV26')
    parser.add_argument('--bars', type=int, default=10000)
    args = parser.parse_args()
    import MetaTrader5 as mt5
    if not mt5.initialize(args.terminal, timeout=15000):
        print(f'ERRO: conexão MT5: {mt5.last_error()}')
        return 1
    try:
        spec = load_b3_spec(mt5, args.symbol)
    finally:
        mt5.shutdown()
    try:
        bars = fetch_closed_bars(
            mt5, args.terminal, args.symbol, mt5.TIMEFRAME_M5, args.bars)
        report = run_stress_test(bars, spec)
    except (RuntimeError, ValueError) as error:
        print(f'ERRO: {error}')
        return 1
    output = Path(__file__).parent / 'reports'
    output.mkdir(exist_ok=True)
    path = output / ('b3-stress-' +
                     datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '.json')
    path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f'Relatório: {path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
