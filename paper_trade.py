"""Paper trading local. Nunca envia, altera ou cancela ordens no MT5."""
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from backtest import fetch_closed_bars, strategy_positions
from risk import RiskLimits, entry_risk_check, update_risk_state


INITIAL_STATE = {
    'mode': 'LOCAL_PAPER_ONLY',
    'strategy_approved': False,
    'cash': 10000.0,
    'units': 0.0,
    'position': 'FLAT',
    'last_processed_bar': None,
    'trades': [],
    'peak_equity': 10000.0,
    'daily_start_equity': 10000.0,
    'entries_today': 0,
}


def load_state(path):
    if not path.exists():
        return dict(INITIAL_STATE)
    state = json.loads(path.read_text(encoding='utf-8'))
    if state.get('mode') != 'LOCAL_PAPER_ONLY':
        raise ValueError('Estado recusado: modo de paper trading invalido.')
    # Migra estados criados por versoes anteriores sem apagar o historico.
    for key, value in INITIAL_STATE.items():
        state.setdefault(key, value)
    state.setdefault('daily_return_pct', 0.0)
    state.setdefault('drawdown_pct', 0.0)
    return state


def save_state(path, state):
    path.parent.mkdir(exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(state, indent=2), encoding='utf-8')
    temporary.replace(path)


def process_latest_closed_bar(state, bars, point, cost_bps=2.0, limits=None,
                              kill_switch=False):
    latest = bars[-1]
    stamp = int(latest['time'])
    if state['last_processed_bar'] is not None and stamp <= state['last_processed_bar']:
        return state, {'action': 'WAIT', 'reason': 'bar_already_processed'}
    desired, _ = strategy_positions(bars, 'sma_trend', fast=20, slow=50)
    should_hold = desired[-1]
    mid = float(latest['close'])
    spread = float(latest['spread']) * point
    fee = cost_bps / 10000
    current_equity = state['cash'] + state['units'] * mid
    session_date = datetime.fromtimestamp(stamp, timezone.utc).date().isoformat()
    update_risk_state(state, current_equity, session_date)
    limits = limits or RiskLimits()
    event = {'action': 'HOLD', 'bar_time': stamp}
    if should_hold and state['position'] == 'FLAT':
        decision = entry_risk_check(state, limits, kill_switch)
        if decision['allowed']:
            price = (mid + spread / 2) * (1 + fee)
            state['units'] = state['cash'] / price
            state['cash'] = 0.0
            state['position'] = 'LONG'
            state['entries_today'] += 1
            trade = {'entry_time': stamp, 'entry_price': price, 'units': state['units']}
            state['trades'].append(trade)
            event = {'action': 'PAPER_BUY', 'bar_time': stamp, 'price': price}
        else:
            event = {'action': 'RISK_BLOCK', 'bar_time': stamp,
                     'reasons': decision['reasons']}
    elif not should_hold and state['position'] == 'LONG':
        price = (mid - spread / 2) * (1 - fee)
        state['cash'] = state['units'] * price
        state['units'] = 0.0
        state['position'] = 'FLAT'
        state['trades'][-1].update(exit_time=stamp, exit_price=price)
        event = {'action': 'PAPER_SELL', 'bar_time': stamp, 'price': price}
    state['last_processed_bar'] = stamp
    state['last_price'] = mid
    state['equity'] = round(state['cash'] + state['units'] * mid, 2)
    update_risk_state(state, state['equity'], session_date)
    state['updated_at_utc'] = datetime.now(timezone.utc).isoformat()
    return state, event


def append_event(path, event, state):
    record = {'recorded_at_utc': datetime.now(timezone.utc).isoformat(), **event,
              'position': state['position'], 'equity': state['equity']}
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(record) + '\n')


def run_once(api, args, state_path):
    metadata = {}
    bars = fetch_closed_bars(api, args.terminal, args.symbol, api.TIMEFRAME_M5,
                             250, metadata)
    state = load_state(state_path)
    kill_switch = state_path.parent.joinpath('KILL_SWITCH').exists()
    limits = RiskLimits(args.max_daily_loss, args.max_drawdown, args.max_entries)
    state, event = process_latest_closed_bar(state, bars, metadata['point'],
                                             args.cost_bps, limits, kill_switch)
    state['symbol'] = args.symbol
    state['server_timestamp_note'] = 'Timestamp bruto do servidor; offset ainda sob auditoria.'
    save_state(state_path, state)
    append_event(state_path.parent / f'{args.symbol}-M5-events.jsonl', event, state)
    return state, event


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--terminal', default=r'C:\Program Files\MetaTrader 5\terminal64.exe')
    parser.add_argument('--symbol', default='EURUSD')
    parser.add_argument('--cost-bps', type=float, default=2.0)
    parser.add_argument('--watch', action='store_true', help='Repete a leitura; Ctrl+C encerra.')
    parser.add_argument('--interval', type=int, default=30)
    parser.add_argument('--max-daily-loss', type=float, default=1.0)
    parser.add_argument('--max-drawdown', type=float, default=2.0)
    parser.add_argument('--max-entries', type=int, default=5)
    args = parser.parse_args()
    if args.interval < 5:
        parser.error('--interval deve ser pelo menos 5 segundos')
    import MetaTrader5 as mt5
    state_path = Path(__file__).parent / 'paper' / f'{args.symbol}-M5-state.json'
    try:
        while True:
            state, event = run_once(mt5, args, state_path)
            print(json.dumps({'event': event, 'position': state['position'],
                              'equity': state['equity'],
                              'daily_return_pct': round(state['daily_return_pct'], 4),
                              'drawdown_pct': round(state['drawdown_pct'], 4),
                              'entries_today': state['entries_today'],
                              'state': str(state_path)}, indent=2))
            if not args.watch:
                return 0
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print('Monitor encerrado; o estado ficticio foi preservado.')
        return 0
    except (RuntimeError, ValueError, OSError, json.JSONDecodeError) as error:
        print(f'ERRO: {error}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
