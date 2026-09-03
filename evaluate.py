"""Compara configuracoes fixas sem expor o holdout durante a selecao."""
import argparse
import json

from backtest import (benchmark_buy_hold, fetch_closed_bars, run_strategy_backtest,
                      save_outputs)
from data_audit import audit_bars


CANDIDATES = (
    {'name': 'tendencia_sma', 'strategy': 'sma_trend',
     'parameters': {'fast': 20, 'slow': 50}},
    {'name': 'momentum_rompimento', 'strategy': 'momentum_breakout',
     'parameters': {'entry_window': 40, 'exit_window': 20}},
    {'name': 'reversao_rsi', 'strategy': 'rsi_mean_reversion',
     'parameters': {'rsi_window': 14, 'entry_level': 30, 'exit_level': 55}},
)


def compact(report):
    return {key: value for key, value in report.items() if key != 'trade_log'}


def evaluate_candidates(bars, cost_bps=2.0, point=0.0, use_bar_spread=True,
                        candidates=CANDIDATES):
    if len(bars) < 1000:
        raise ValueError('Use ao menos 1.000 candles para a avaliacao em tres partes.')
    first = int(len(bars) * .60)
    second = int(len(bars) * .80)
    development, validation, holdout = bars[:first], bars[first:second], bars[second:]
    common = dict(cost_bps=cost_bps, point=point, use_bar_spread=use_bar_spread)
    candidates_report = []
    for candidate in candidates:
        parameters = candidate['parameters']
        development_result = run_strategy_backtest(
            development, candidate['strategy'], parameters, **common)
        validation_result = run_strategy_backtest(
            validation, candidate['strategy'], parameters, **common)
        candidates_report.append({
            'name': candidate['name'], 'strategy': candidate['strategy'],
            'parameters': parameters,
            'development': compact(development_result),
            'validation': compact(validation_result),
        })
    # Criterio declarado previamente: maior retorno liquido na validacao.
    selected = max(candidates_report, key=lambda item: item['validation']['return_pct'])
    holdout_result = run_strategy_backtest(
        holdout, selected['strategy'], selected['parameters'], **common)
    return {
        'protocol': '60% development / 20% validation / 20% untouched holdout',
        'selection_rule': 'highest net validation return; ties keep candidate order',
        'development_bars': len(development), 'validation_bars': len(validation),
        'holdout_bars': len(holdout), 'candidates': candidates_report,
        'selected_candidate': selected['name'],
        'holdout_result': holdout_result,
        'holdout_benchmarks': {
            'buy_hold_return_pct': benchmark_buy_hold(holdout, cost_bps, point=point,
                                                       use_bar_spread=use_bar_spread),
            'no_trade_return_pct': 0.0,
        },
        'warning': 'O holdout deixa de ser intocado apos este relatorio; nao reutilize-o para ajustar parametros.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--terminal', default=r'C:\Program Files\MetaTrader 5\terminal64.exe')
    parser.add_argument('--symbol', default='EURUSD')
    parser.add_argument('--timeframe', choices=('M1', 'M5', 'M15', 'H1'), default='M5')
    parser.add_argument('--bars', type=int, default=10000)
    parser.add_argument('--cost-bps', type=float, default=2.0)
    parser.add_argument('--no-bar-spread', action='store_true')
    args = parser.parse_args()
    import MetaTrader5 as mt5
    mapping = {'M1': mt5.TIMEFRAME_M1, 'M5': mt5.TIMEFRAME_M5,
               'M15': mt5.TIMEFRAME_M15, 'H1': mt5.TIMEFRAME_H1}
    try:
        metadata = {}
        bars = fetch_closed_bars(mt5, args.terminal, args.symbol,
                                 mapping[args.timeframe], args.bars, metadata)
        report = evaluate_candidates(bars, args.cost_bps, metadata['point'],
                                     not args.no_bar_spread)
        report['data_audit'] = audit_bars(bars, args.timeframe, metadata['tick_time'])
        csv_path, json_path, payload = save_outputs(bars, report, args.symbol,
                                                    args.timeframe + '-evaluation')
    except (RuntimeError, ValueError) as error:
        print(f'ERRO: {error}')
        return 1
    printable = dict(payload)
    printable['holdout_result'] = compact(printable['holdout_result'])
    print(json.dumps(printable, indent=2))
    print(f'Dados: {csv_path}\nRelatorio: {json_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
