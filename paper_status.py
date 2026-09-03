"""Exibe o estado atual do paper trading sem conectar ao MT5."""
import argparse
import json
from pathlib import Path

from paper_trade import load_state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--symbol', default='EURUSD')
    parser.add_argument('--events', type=int, default=5)
    args = parser.parse_args()
    directory = Path(__file__).parent / 'paper'
    state_path = directory / f'{args.symbol}-M5-state.json'
    if not state_path.exists():
        print('Nenhum estado encontrado. Execute paper_trade.py primeiro.')
        return 1
    try:
        state = load_state(state_path)
        event_path = directory / f'{args.symbol}-M5-events.jsonl'
        lines = event_path.read_text(encoding='utf-8').splitlines() if event_path.exists() else []
        recent = [json.loads(line) for line in lines[-max(0, args.events):]]
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(f'ERRO: {error}')
        return 1
    summary = {key: state.get(key) for key in (
        'mode', 'strategy_approved', 'symbol', 'position', 'cash', 'units',
        'equity', 'daily_return_pct', 'drawdown_pct', 'entries_today',
        'last_processed_bar', 'updated_at_utc', 'feed_health')}
    summary['recent_events'] = recent
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
