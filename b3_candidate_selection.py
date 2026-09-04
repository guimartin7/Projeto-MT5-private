"""Seleciona sinais B3 sem executar a reserva cronológica final."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from b3_backtest import run_futures_backtest
from b3_instrument import load_b3_spec
from backtest import fetch_closed_bars


CANDIDATES = (
    {'name': 'sma_9_21', 'strategy': 'sma', 'fast': 9, 'slow': 21},
    {'name': 'sma_20_50', 'strategy': 'sma', 'fast': 20, 'slow': 50},
    {'name': 'sma_20_50_gap20', 'strategy': 'sma', 'fast': 20, 'slow': 50,
     'min_ma_gap_points': 20},
    {'name': 'breakout_20', 'strategy': 'breakout', 'breakout_window': 20},
    {'name': 'breakout_40', 'strategy': 'breakout', 'breakout_window': 40},
)


def compact(report):
    return {key: value for key, value in report.items() if key != 'trade_log'}


def validation_eligible(report):
    stats = report['statistics']
    factor = stats['profit_factor']
    return (report['net_pnl'] > 0 and report['trades'] >= 10 and
            stats['max_drawdown_pct'] <= 20 and factor is not None and factor >= 1.2)


def select_candidates_without_reserve(bars, spec, candidates=CANDIDATES, **kwargs):
    if len(bars) < 1000:
        raise ValueError('Use ao menos 1.000 candles para seleção com reserva.')
    development_end = int(len(bars) * .60)
    validation_end = int(len(bars) * .80)
    development = bars[:development_end]
    validation = bars[development_end:validation_end]
    reserve = bars[validation_end:]
    reports = []
    for candidate in candidates:
        parameters = {key: value for key, value in candidate.items() if key != 'name'}
        development_report = run_futures_backtest(
            development, spec, **parameters, **kwargs)
        validation_report = run_futures_backtest(
            validation, spec, **parameters, **kwargs)
        eligible = validation_eligible(validation_report)
        reports.append({
            'name': candidate['name'], 'parameters': parameters,
            'development': compact(development_report),
            'validation': compact(validation_report),
            'eligible_for_forward_observation': eligible,
        })
    eligible = [item for item in reports if item['eligible_for_forward_observation']]
    selected = max(
        eligible,
        key=lambda item: (item['validation']['statistics']['profit_factor'],
                          item['validation']['net_pnl']),
        default=None,
    )
    return {
        'mode': 'B3_CANDIDATE_SELECTION_NO_RESERVE_EXECUTION',
        'protocol': '60% development / 20% validation / 20% unexecuted reserve',
        'selection_rule': ('eligible: validation net > 0, >=10 trades, drawdown <=20%, '
                           'profit factor >=1.20; rank by profit factor then net PnL'),
        'development_bars': len(development),
        'validation_bars': len(validation),
        'candidates': reports,
        'selected_candidate': None if selected is None else selected['name'],
        'reserve': {
            'bars': len(reserve),
            'first_bar_utc': datetime.fromtimestamp(
                int(reserve[0]['time']), timezone.utc).isoformat(),
            'last_bar_utc': datetime.fromtimestamp(
                int(reserve[-1]['time']), timezone.utc).isoformat(),
            'executed': False,
            'performance': None,
            'warning': ('Reserva técnica: não executada neste seletor, mas o período '
                        'já apareceu em análises agregadas anteriores.'),
        },
        'approved_for_orders': False,
        'next_step': ('collect_new_forward_data' if selected is not None
                      else 'design_new_candidates_on_development_only'),
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
        report = select_candidates_without_reserve(bars, spec)
    except (RuntimeError, ValueError) as error:
        print(f'ERRO: {error}')
        return 1
    output = Path(__file__).parent / 'reports'
    output.mkdir(exist_ok=True)
    path = output / ('b3-candidates-' +
                     datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '.json')
    path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    printable = {**report, 'candidates': [
        {'name': item['name'], 'eligible_for_forward_observation':
         item['eligible_for_forward_observation'],
         'development_net_pnl': item['development']['net_pnl'],
         'validation_net_pnl': item['validation']['net_pnl'],
         'validation_trades': item['validation']['trades'],
         'validation_drawdown_pct':
         item['validation']['statistics']['max_drawdown_pct'],
         'validation_profit_factor':
         item['validation']['statistics']['profit_factor']}
        for item in report['candidates']]}
    print(json.dumps(printable, indent=2, ensure_ascii=False))
    print(f'Relatório: {path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
