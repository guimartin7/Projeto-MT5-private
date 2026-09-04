"""Backtest conservador do WIN, sempre local e sem envio de ordens."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from b3_costs import DEFAULT_WIN_COSTS
from b3_instrument import futures_pnl, load_b3_spec
from backtest import fetch_closed_bars, simple_moving_average
from diagnose import validate_bars


SAO_PAULO = ZoneInfo('America/Sao_Paulo')


def run_futures_backtest(bars, spec, initial_balance=500.0, contracts=1,
                         fast=9, slow=21, stop_reais=20.0,
                         daily_loss_reais=30.0,
                         cost_per_side=DEFAULT_WIN_COSTS.normal_cost_per_side,
                         slippage_ticks=DEFAULT_WIN_COSTS.slippage_ticks):
    validate_bars(bars)
    if contracts != 1:
        raise ValueError('Treinamento inicial limitado a exatamente 1 contrato.')
    if initial_balance <= 0 or stop_reais <= 0 or daily_loss_reais <= 0:
        raise ValueError('Parâmetros financeiros inválidos.')
    closes = [float(bar['close']) for bar in bars]
    fast_ma, slow_ma = simple_moving_average(closes, fast), simple_moving_average(closes, slow)
    balance = peak = initial_balance
    max_drawdown = 0.0
    position = None
    trades = []
    daily_pnl = {}
    blocked_entries = 0
    capital_blocks = 0
    slip = spec.tick_size * slippage_ticks

    def local_time(bar):
        return datetime.fromtimestamp(int(bar['time']), timezone.utc).astimezone(SAO_PAULO)

    def close_position(price, stamp, reason):
        nonlocal balance, position, peak, max_drawdown
        raw = futures_pnl(position['entry_price'], price, position['direction'], contracts, spec)
        net = raw - 2 * cost_per_side
        balance += net
        day = position['day']
        daily_pnl[day] = daily_pnl.get(day, 0.0) + net
        trades.append({**position, 'exit_time': stamp, 'exit_price': price,
                       'reason': reason, 'net_pnl': round(net, 2)})
        position = None
        peak = max(peak, balance)
        max_drawdown = min(max_drawdown, balance - peak)

    for index in range(slow + 1, len(bars)):
        bar = bars[index]
        moment = local_time(bar)
        day = moment.date().isoformat()
        previous_signal = 1 if fast_ma[index - 1] > slow_ma[index - 1] else -1
        if position:
            stop_points = stop_reais / (spec.value_per_point * contracts)
            if position['direction'] == 1 and float(bar['low']) <= position['entry_price'] - stop_points:
                close_position(position['entry_price'] - stop_points - slip,
                               int(bar['time']), 'STOP')
            elif position['direction'] == -1 and float(bar['high']) >= position['entry_price'] + stop_points:
                close_position(position['entry_price'] + stop_points + slip,
                               int(bar['time']), 'STOP')
            elif moment.hour > 17 or (moment.hour == 17 and moment.minute >= 50):
                exit_price = float(bar['open']) - slip * position['direction']
                close_position(exit_price, int(bar['time']), 'DAILY_FLAT')
            elif previous_signal != position['direction']:
                exit_price = float(bar['open']) - slip * position['direction']
                close_position(exit_price, int(bar['time']), 'SIGNAL')
        allowed_time = ((moment.hour > 9 or (moment.hour == 9 and moment.minute >= 10))
                        and (moment.hour < 17 or (moment.hour == 17 and moment.minute < 30)))
        if position is None and allowed_time:
            if balance < stop_reais + 2 * cost_per_side:
                capital_blocks += 1
                continue
            if daily_pnl.get(day, 0.0) <= -daily_loss_reais:
                blocked_entries += 1
                continue
            entry = float(bar['open']) + slip * previous_signal
            position = {'direction': previous_signal, 'entry_time': int(bar['time']),
                        'entry_price': entry, 'day': day, 'contracts': contracts}
    if position:
        close_position(float(bars[-1]['close']) - slip * position['direction'],
                       int(bars[-1]['time']), 'END_OF_DATA')
    wins = sum(trade['net_pnl'] > 0 for trade in trades)
    return {
        'mode': 'B3_HISTORICAL_TRAINING_ONLY', 'initial_balance': initial_balance,
        'final_balance': round(balance, 2), 'net_pnl': round(balance - initial_balance, 2),
        'return_pct': round((balance / initial_balance - 1) * 100, 4),
        'max_drawdown_reais': round(max_drawdown, 2), 'trades': len(trades),
        'win_rate_pct': round(wins / len(trades) * 100, 2) if trades else 0.0,
        'blocked_entries': blocked_entries, 'contracts': contracts,
        'capital_blocks': capital_blocks,
        'stop_reais': stop_reais, 'daily_loss_reais': daily_loss_reais,
        'cost_per_side_reais_assumption': cost_per_side,
        'default_cost_model': DEFAULT_WIN_COSTS.to_dict(),
        'slippage_ticks': slippage_ticks, 'strategy': f'SMA {fast}/{slow}',
        'instrument': spec.to_dict(), 'trade_log': trades,
        'approved_for_orders': False,
        'warning': 'Custo é hipótese conservadora, não tarifa confirmada da Clear.',
    }


def evaluate_futures_periods(bars, spec, **kwargs):
    if len(bars) < 1000:
        raise ValueError('Use ao menos 1.000 candles para separar os períodos.')
    split = int(len(bars) * .70)
    development, out_of_sample = bars[:split], bars[split:]
    return {
        'protocol': '70% development / 30% out-of-sample test',
        'total_bars': len(bars), 'development_bars': len(development),
        'out_of_sample_bars': len(out_of_sample),
        'first_bar_utc': datetime.fromtimestamp(int(bars[0]['time']), timezone.utc).isoformat(),
        'last_bar_utc': datetime.fromtimestamp(int(bars[-1]['time']), timezone.utc).isoformat(),
        'development': run_futures_backtest(development, spec, **kwargs),
        'out_of_sample': run_futures_backtest(out_of_sample, spec, **kwargs),
        'approved_for_orders': False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--symbol', default='WINV26')
    parser.add_argument('--bars', type=int, default=10000)
    parser.add_argument('--initial-balance', type=float, default=500)
    parser.add_argument('--cost-per-side', type=float,
                        default=DEFAULT_WIN_COSTS.normal_cost_per_side)
    args = parser.parse_args()
    import MetaTrader5 as mt5
    terminal = r'C:\Program Files\MetaTrader 5\terminal64.exe'
    if not mt5.initialize(terminal, timeout=15000):
        print(f'ERRO: conexão MT5: {mt5.last_error()}')
        return 1
    try:
        spec = load_b3_spec(mt5, args.symbol)
    finally:
        mt5.shutdown()
    bars = fetch_closed_bars(mt5, terminal, args.symbol, mt5.TIMEFRAME_M5, args.bars)
    try:
        report = evaluate_futures_periods(
            bars, spec, initial_balance=args.initial_balance,
            cost_per_side=args.cost_per_side)
    except ValueError as error:
        print(f'ERRO: {error}')
        return 1
    output = Path(__file__).parent / 'reports'
    output.mkdir(exist_ok=True)
    path = output / ('b3-backtest-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '.json')
    path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    summary = dict(report)
    for segment in ('development', 'out_of_sample'):
        summary[segment] = {key: value for key, value in report[segment].items()
                            if key != 'trade_log'}
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f'Relatório: {path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
