"""Paper trading local do WIN. Este módulo não envia ordens ao MetaTrader."""
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from b3_costs import DEFAULT_WIN_COSTS
from b3_instrument import futures_pnl, load_b3_spec
from backtest import fetch_closed_bars, simple_moving_average
from health import assess_feed


SAO_PAULO = ZoneInfo('America/Sao_Paulo')


def initial_state(symbol='WINV26', balance=500.0):
    return {
        'mode': 'B3_LOCAL_PAPER_ONLY', 'approved_for_orders': False,
        'symbol': symbol, 'balance': balance, 'equity': balance,
        'position': None, 'last_processed_bar': None, 'trades': [],
        'session_date': None, 'daily_start_balance': balance,
        'daily_realized_pnl': 0.0, 'entries_today': 0,
        'peak_equity': balance, 'drawdown_reais': 0.0,
    }


def validate_state(state):
    if state.get('mode') != 'B3_LOCAL_PAPER_ONLY':
        raise ValueError('Estado B3 recusado: modo inválido.')
    if float(state.get('balance', -1)) < 0:
        raise ValueError('Estado B3 inconsistente: saldo negativo.')
    position = state.get('position')
    if position is not None:
        if position.get('direction') not in (-1, 1) or position.get('contracts') != 1:
            raise ValueError('Estado B3 inconsistente: posição inválida.')
    return True


def load_state(path, symbol, balance):
    if not path.exists():
        return initial_state(symbol, balance)
    state = json.loads(path.read_text(encoding='utf-8'))
    validate_state(state)
    if state['symbol'] != symbol:
        raise ValueError('Estado pertence a outro ativo.')
    return state


def save_state(path, state):
    validate_state(state)
    path.parent.mkdir(exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(state, indent=2), encoding='utf-8')
    temporary.replace(path)


def market_phase(moment):
    if moment.weekday() >= 5 or moment.hour < 9 or moment.hour >= 18:
        return 'CLOSED'
    if moment.hour > 17 or (moment.hour == 17 and moment.minute >= 50):
        return 'FLATTEN_ONLY'
    if moment.hour < 9 or (moment.hour == 9 and moment.minute < 10):
        return 'OBSERVE_ONLY'
    if moment.hour > 17 or (moment.hour == 17 and moment.minute >= 30):
        return 'OBSERVE_ONLY'
    return 'ENTRY_ALLOWED'


def desired_direction(bars, fast=9, slow=21):
    closes = [float(bar['close']) for bar in bars]
    fast_ma, slow_ma = simple_moving_average(closes, fast), simple_moving_average(closes, slow)
    if len(bars) <= slow or fast_ma[-1] is None:
        raise ValueError('Histórico insuficiente para o sinal B3.')
    return 1 if fast_ma[-1] > slow_ma[-1] else -1


def process_bar(state, bars, spec, bid, ask, moment, stop_reais=20.0,
                daily_loss_reais=30.0,
                cost_per_side=DEFAULT_WIN_COSTS.normal_cost_per_side,
                slippage_ticks=DEFAULT_WIN_COSTS.slippage_ticks,
                kill_switch=False):
    validate_state(state)
    stamp = int(bars[-1]['time'])
    phase = market_phase(moment)
    day = moment.date().isoformat()
    if state['session_date'] != day:
        state['session_date'] = day
        state['daily_start_balance'] = state['balance']
        state['daily_realized_pnl'] = 0.0
        state['entries_today'] = 0
    position = state['position']
    mark = bid if position and position['direction'] == 1 else ask
    unrealized = 0.0 if not position else futures_pnl(
        position['entry_price'], mark, position['direction'], 1, spec)
    state['equity'] = round(state['balance'] + unrealized, 2)
    state['peak_equity'] = max(state['peak_equity'], state['equity'])
    state['drawdown_reais'] = round(state['equity'] - state['peak_equity'], 2)

    if state['last_processed_bar'] is not None and stamp <= state['last_processed_bar']:
        return state, {'action': 'WAIT', 'reason': 'bar_already_processed'}
    if phase == 'CLOSED':
        return state, {'action': 'WAIT', 'reason': 'market_closed'}

    signal = desired_direction(bars)
    slip = spec.tick_size * slippage_ticks
    exit_reason = None
    if position:
        if kill_switch:
            exit_reason = 'KILL_SWITCH'
        elif unrealized <= -stop_reais:
            exit_reason = 'STOP'
        elif phase == 'FLATTEN_ONLY':
            exit_reason = 'DAILY_FLAT'
        elif signal != position['direction']:
            exit_reason = 'SIGNAL'
        if exit_reason:
            exit_price = (bid - slip) if position['direction'] == 1 else (ask + slip)
            gross = futures_pnl(position['entry_price'], exit_price,
                                position['direction'], 1, spec)
            net_exit = gross - cost_per_side
            state['balance'] = round(state['balance'] + net_exit, 2)
            state['daily_realized_pnl'] = round(state['daily_realized_pnl'] + net_exit, 2)
            trade = {**position, 'exit_time': stamp, 'exit_price': exit_price,
                     'reason': exit_reason,
                     'net_pnl': round(gross - 2 * cost_per_side, 2)}
            state['trades'].append(trade)
            state['position'] = None
            state['equity'] = state['balance']
            state['last_processed_bar'] = stamp
            return state, {'action': 'PAPER_EXIT', 'reason': exit_reason,
                           'price': exit_price, 'net_pnl': trade['net_pnl']}

    if position is None and phase == 'ENTRY_ALLOWED':
        reasons = []
        if kill_switch:
            reasons.append('kill_switch_active')
        if state['daily_realized_pnl'] <= -daily_loss_reais:
            reasons.append('daily_loss_limit')
        if state['balance'] < stop_reais + 2 * cost_per_side:
            reasons.append('insufficient_training_balance')
        if state['entries_today'] >= 5:
            reasons.append('daily_entry_limit')
        if reasons:
            state['last_processed_bar'] = stamp
            return state, {'action': 'RISK_BLOCK', 'reasons': reasons}
        entry_price = (ask + slip) if signal == 1 else (bid - slip)
        state['balance'] = round(state['balance'] - cost_per_side, 2)
        state['daily_realized_pnl'] = round(state['daily_realized_pnl'] - cost_per_side, 2)
        state['position'] = {'direction': signal, 'contracts': 1,
                             'entry_time': stamp, 'entry_price': entry_price}
        state['entries_today'] += 1
        state['last_processed_bar'] = stamp
        return state, {'action': 'PAPER_ENTRY', 'direction': signal,
                       'price': entry_price, 'contracts': 1}

    state['last_processed_bar'] = stamp
    return state, {'action': 'HOLD' if position else 'WAIT', 'reason': phase.lower()}


def append_event(path, event, state):
    record = {'recorded_at_utc': datetime.now(timezone.utc).isoformat(), **event,
              'balance': state['balance'], 'equity': state['equity']}
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(record) + '\n')


def run_once(api, args, state_path):
    terminal = args.terminal
    if not api.initialize(terminal, timeout=15000):
        raise RuntimeError(f'Falha ao conectar: {api.last_error()}')
    try:
        spec = load_b3_spec(api, args.symbol)
    finally:
        api.shutdown()
    metadata = {}
    bars = fetch_closed_bars(api, terminal, args.symbol, api.TIMEFRAME_M5, 250, metadata)
    now = datetime.now(timezone.utc)
    local_now = now.astimezone(SAO_PAULO)
    state = load_state(state_path, args.symbol, args.initial_balance)
    if market_phase(local_now) != 'CLOSED':
        feed = assess_feed(metadata['tick_time'], metadata['tick_bid'], metadata['tick_ask'])
        if not feed['healthy']:
            event = {'action': 'FEED_BLOCK', 'reason': feed['status']}
            state['feed_health'] = feed
            save_state(state_path, state)
            append_event(state_path.parent / f'{args.symbol}-M5-events.jsonl', event, state)
            return state, event
    kill_switch = state_path.parent.joinpath('B3_KILL_SWITCH').exists()
    state, event = process_bar(state, bars, spec, metadata['tick_bid'],
                               metadata['tick_ask'], local_now,
                               cost_per_side=args.cost_per_side,
                               kill_switch=kill_switch)
    state['updated_at_utc'] = now.isoformat()
    save_state(state_path, state)
    append_event(state_path.parent / f'{args.symbol}-M5-events.jsonl', event, state)
    return state, event


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--terminal', default=r'C:\Program Files\MetaTrader 5\terminal64.exe')
    parser.add_argument('--symbol', default='WINV26')
    parser.add_argument('--initial-balance', type=float, default=500)
    parser.add_argument('--cost-per-side', type=float,
                        default=DEFAULT_WIN_COSTS.normal_cost_per_side)
    parser.add_argument('--watch', action='store_true')
    parser.add_argument('--interval', type=int, default=30)
    args = parser.parse_args()
    if args.interval < 5:
        parser.error('--interval deve ser pelo menos 5 segundos')
    import MetaTrader5 as mt5
    state_path = Path(__file__).parent / 'paper' / f'{args.symbol}-M5-state.json'
    try:
        while True:
            state, event = run_once(mt5, args, state_path)
            print(json.dumps({'event': event, 'balance': state['balance'],
                              'equity': state['equity'],
                              'position': state['position'],
                              'approved_for_orders': False}, indent=2))
            if not args.watch:
                return 0
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print('Monitor B3 encerrado; estado fictício preservado.')
        return 0
    except (RuntimeError, ValueError, OSError, json.JSONDecodeError) as error:
        print(f'ERRO: {error}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
