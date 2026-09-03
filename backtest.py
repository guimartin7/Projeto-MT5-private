"""Backtest local e somente leitura usando candles fechados do MT5."""
import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from diagnose import validate_bars
from data_audit import audit_bars


def simple_moving_average(values, window):
    if window < 1:
        raise ValueError('A janela deve ser positiva.')
    result = [None] * len(values)
    running = 0.0
    for index, value in enumerate(values):
        running += value
        if index >= window:
            running -= values[index - window]
        if index >= window - 1:
            result[index] = running / window
    return result


def relative_strength_index(values, window=14):
    if window < 2:
        raise ValueError('A janela do RSI deve ser pelo menos 2.')
    result = [None] * len(values)
    gains = [max(0.0, values[i] - values[i - 1]) for i in range(1, len(values))]
    losses = [max(0.0, values[i - 1] - values[i]) for i in range(1, len(values))]
    for index in range(window, len(values)):
        gain = sum(gains[index - window:index]) / window
        loss = sum(losses[index - window:index]) / window
        result[index] = 100.0 if loss == 0 else 100 - 100 / (1 + gain / loss)
    return result


def strategy_positions(bars, strategy='sma_trend', **parameters):
    closes = [float(bar['close']) for bar in bars]
    desired = [False] * len(bars)
    if strategy == 'sma_trend':
        fast, slow = parameters.get('fast', 20), parameters.get('slow', 50)
        if fast >= slow:
            raise ValueError('A media curta deve ser menor que a longa.')
        fast_ma, slow_ma = simple_moving_average(closes, fast), simple_moving_average(closes, slow)
        for index in range(slow - 1, len(bars)):
            desired[index] = fast_ma[index] > slow_ma[index]
        return desired, slow
    if strategy == 'momentum_breakout':
        entry, exit_window = parameters.get('entry_window', 40), parameters.get('exit_window', 20)
        if entry < 2 or exit_window < 2:
            raise ValueError('Janelas de rompimento invalidas.')
        holding = False
        warmup = max(entry, exit_window)
        for index in range(warmup, len(bars)):
            if not holding and closes[index] > max(closes[index-entry:index]):
                holding = True
            elif holding and closes[index] < min(closes[index-exit_window:index]):
                holding = False
            desired[index] = holding
        return desired, warmup
    if strategy == 'rsi_mean_reversion':
        window = parameters.get('rsi_window', 14)
        entry_level, exit_level = parameters.get('entry_level', 30), parameters.get('exit_level', 55)
        if not 0 < entry_level < exit_level < 100:
            raise ValueError('Niveis de RSI invalidos.')
        rsi = relative_strength_index(closes, window)
        holding = False
        for index in range(window, len(bars)):
            if not holding and rsi[index] < entry_level:
                holding = True
            elif holding and rsi[index] > exit_level:
                holding = False
            desired[index] = holding
        return desired, window
    raise ValueError(f'Estrategia desconhecida: {strategy}')


def run_backtest(bars, fast=20, slow=50, cost_bps=2.0, initial_cash=10_000.0,
                 point=0.0, use_bar_spread=False):
    return run_strategy_backtest(
        bars, 'sma_trend', {'fast': fast, 'slow': slow}, cost_bps,
        initial_cash, point, use_bar_spread
    )


def run_strategy_backtest(bars, strategy, parameters=None, cost_bps=2.0,
                          initial_cash=10_000.0, point=0.0,
                          use_bar_spread=False):
    validate_bars(bars)
    if cost_bps < 0 or initial_cash <= 0:
        raise ValueError('Custos e capital inicial invalidos.')

    parameters = dict(parameters or {})
    closes = [float(bar['close']) for bar in bars]
    desired, warmup = strategy_positions(bars, strategy, **parameters)
    if len(bars) <= warmup + 2:
        raise ValueError('Historico insuficiente para a estrategia escolhida.')
    cash = initial_cash
    units = 0.0
    entry_cash = None
    trades = []
    equity_curve = []
    invested_bars = 0

    def bar_value(bar, key, default=0):
        try:
            return bar[key]
        except (KeyError, ValueError, IndexError):
            return default

    def execution_price(index, buying):
        mid = float(bars[index]['open'])
        spread = float(bar_value(bars[index], 'spread')) * point if use_bar_spread else 0.0
        adjusted = mid + spread / 2 if buying else mid - spread / 2
        fee = cost_bps / 10_000
        return adjusted * (1 + fee if buying else 1 - fee)

    # O sinal usa apenas o fechamento anterior; a execucao ocorre na abertura seguinte.
    for index in range(warmup + 1, len(bars)):
        should_hold = desired[index - 1]
        if should_hold and units == 0:
            price = execution_price(index, True)
            entry_cash = cash
            units = cash / price
            cash = 0.0
            trades.append({'side': 'BUY', 'time': int(bars[index]['time']), 'price': price})
        elif not should_hold and units > 0:
            price = execution_price(index, False)
            cash = units * price
            units = 0.0
            trades[-1]['exit_time'] = int(bars[index]['time'])
            trades[-1]['exit_price'] = price
            trades[-1]['return_pct'] = (cash / entry_cash - 1) * 100
            entry_cash = None
        if units > 0:
            invested_bars += 1
        equity_curve.append(cash + units * closes[index])

    if units > 0:
        price = execution_price(len(bars) - 1, False)
        cash = units * price
        trades[-1].update(exit_time=int(bars[-1]['time']), exit_price=price,
                          return_pct=(cash / entry_cash - 1) * 100, forced_exit=True)
    final_equity = cash
    peak = initial_cash
    max_drawdown = 0.0
    for equity in equity_curve:
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity / peak - 1)
    completed = [trade for trade in trades if 'return_pct' in trade]
    wins = sum(trade['return_pct'] > 0 for trade in completed)
    returns = [trade['return_pct'] for trade in completed]
    gains = sum(value for value in returns if value > 0)
    losses = abs(sum(value for value in returns if value < 0))
    losing_streak = current_streak = 0
    for value in returns:
        current_streak = current_streak + 1 if value <= 0 else 0
        losing_streak = max(losing_streak, current_streak)
    return {
        'initial_cash': initial_cash,
        'final_equity': round(final_equity, 2),
        'return_pct': round((final_equity / initial_cash - 1) * 100, 4),
        'max_drawdown_pct': round(max_drawdown * 100, 4),
        'trades': len(completed),
        'win_rate_pct': round(wins / len(completed) * 100, 2) if completed else 0.0,
        'average_trade_pct': round(sum(returns) / len(returns), 4) if returns else 0.0,
        'average_win_pct': round(gains / wins, 4) if wins else 0.0,
        'average_loss_pct': round(-losses / (len(returns) - wins), 4) if len(returns) > wins else 0.0,
        'profit_factor': round(gains / losses, 4) if losses else (None if not gains else 'infinite'),
        'max_consecutive_losses': losing_streak,
        'exposure_pct': round(invested_bars / max(1, len(equity_curve)) * 100, 2),
        'strategy': strategy, 'parameters': parameters,
        'cost_bps_per_side': cost_bps,
        'bar_spread_enabled': use_bar_spread,
        'trade_log': completed,
    }


def benchmark_buy_hold(bars, cost_bps=2.0, initial_cash=10_000.0, point=0.0,
                       use_bar_spread=False):
    first, last = bars[0], bars[-1]
    fee = cost_bps / 10_000
    try:
        first_points, last_points = first['spread'], last['spread']
    except (KeyError, ValueError, IndexError):
        first_points = last_points = 0
    first_spread = float(first_points) * point if use_bar_spread else 0
    last_spread = float(last_points) * point if use_bar_spread else 0
    buy = (float(first['open']) + first_spread / 2) * (1 + fee)
    sell = (float(last['close']) - last_spread / 2) * (1 - fee)
    final = initial_cash / buy * sell
    return round((final / initial_cash - 1) * 100, 4)


def evaluate_segments(bars, fast, slow, cost_bps, train_ratio=.7, point=0.0,
                      use_bar_spread=False):
    if not .5 <= train_ratio <= .9:
        raise ValueError('A proporcao de treino deve ficar entre 0.5 e 0.9.')
    split = int(len(bars) * train_ratio)
    train, test = bars[:split], bars[split:]
    if len(test) <= slow + 2:
        raise ValueError('A amostra de teste e pequena demais.')
    args = dict(fast=fast, slow=slow, cost_bps=cost_bps, point=point,
                use_bar_spread=use_bar_spread)
    return {
        'split_index': split,
        'train_bars': len(train), 'test_bars': len(test),
        'train': run_backtest(train, **args),
        'out_of_sample_test': run_backtest(test, **args),
        'buy_hold_test_return_pct': benchmark_buy_hold(test, cost_bps, point=point,
                                                       use_bar_spread=use_bar_spread),
        'no_trade_test_return_pct': 0.0,
    }


def fetch_closed_bars(api, terminal, symbol, timeframe, count, metadata=None):
    if not api.initialize(terminal, timeout=15000):
        raise RuntimeError(f'Falha ao conectar MT5: {api.last_error()}')
    try:
        account = api.account_info()
        if account is None or account.trade_mode != api.ACCOUNT_TRADE_MODE_DEMO:
            raise RuntimeError('Coleta permitida somente em conta demo.')
        if not api.symbol_select(symbol, True):
            raise RuntimeError(f'Ativo indisponivel: {symbol}')
        bars = api.copy_rates_from_pos(symbol, timeframe, 1, count)
        validate_bars(bars)
        if metadata is not None:
            info = api.symbol_info(symbol)
            tick = api.symbol_info_tick(symbol)
            metadata.update(
                point=float(info.point), tick_time=None if tick is None else tick.time,
                tick_bid=None if tick is None else float(tick.bid),
                tick_ask=None if tick is None else float(tick.ask),
            )
        return bars
    finally:
        api.shutdown()


def save_outputs(bars, report, symbol, timeframe_name):
    output = Path(__file__).parent / 'reports'
    output.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    csv_path = output / f'bars-{symbol}-{timeframe_name}-{stamp}.csv'
    with csv_path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle)
        writer.writerow(['time_utc', 'open', 'high', 'low', 'close', 'tick_volume', 'spread'])
        for bar in bars:
            writer.writerow([datetime.fromtimestamp(int(bar['time']), timezone.utc).isoformat(),
                             bar['open'], bar['high'], bar['low'], bar['close'],
                             bar['tick_volume'], bar['spread']])
    json_path = output / f'backtest-{symbol}-{timeframe_name}-{stamp}.json'
    payload = {'mode': 'HISTORICAL_BACKTEST_ONLY', 'symbol': symbol,
               'timeframe': timeframe_name, 'bars': len(bars), **report}
    json_path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    return csv_path, json_path, payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--terminal', default=r'C:\Program Files\MetaTrader 5\terminal64.exe')
    parser.add_argument('--symbol', default='EURUSD')
    parser.add_argument('--timeframe', choices=('M1', 'M5', 'M15', 'H1'), default='M5')
    parser.add_argument('--bars', type=int, default=5000)
    parser.add_argument('--fast', type=int, default=20)
    parser.add_argument('--slow', type=int, default=50)
    parser.add_argument('--cost-bps', type=float, default=2.0)
    parser.add_argument('--train-ratio', type=float, default=.7)
    parser.add_argument('--no-bar-spread', action='store_true', help='Ignora o spread historico do candle.')
    args = parser.parse_args()
    import MetaTrader5 as mt5
    mapping = {'M1': mt5.TIMEFRAME_M1, 'M5': mt5.TIMEFRAME_M5,
               'M15': mt5.TIMEFRAME_M15, 'H1': mt5.TIMEFRAME_H1}
    try:
        metadata = {}
        bars = fetch_closed_bars(mt5, args.terminal, args.symbol, mapping[args.timeframe], args.bars, metadata)
        report = evaluate_segments(bars, args.fast, args.slow, args.cost_bps,
                                   args.train_ratio, metadata['point'], not args.no_bar_spread)
        report['data_audit'] = audit_bars(bars, args.timeframe, metadata['tick_time'])
        csv_path, json_path, payload = save_outputs(bars, report, args.symbol, args.timeframe)
    except (RuntimeError, ValueError) as error:
        print(f'ERRO: {error}')
        return 1
    summary = dict(payload)
    for segment in ('train', 'out_of_sample_test'):
        if segment in summary:
            summary[segment] = {key: value for key, value in summary[segment].items()
                                if key != 'trade_log'}
    print(json.dumps(summary, indent=2))
    print(f'Dados: {csv_path}\nRelatorio: {json_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
