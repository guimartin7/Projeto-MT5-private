"""Prepara uma intenção Demo e mostra a frase necessária; não envia ordem."""
import argparse
import json
from datetime import datetime, timezone

from demo_execution_gateway import arm_phrase, default_journal_path, prepare_intent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--direction', choices=('buy', 'sell'), required=True)
    parser.add_argument('--candle-time', type=int)
    args = parser.parse_args()
    if args.candle_time is None:
        args.candle_time = int(datetime.now(timezone.utc).timestamp())
    import MetaTrader5 as mt5
    if not mt5.initialize(r'C:\Program Files\MetaTrader 5\terminal64.exe', timeout=15000):
        print(f'BLOQUEADO: conexão: {mt5.last_error()}')
        return 1
    try:
        intent, preflight = prepare_intent(
            mt5, default_journal_path(), args.candle_time,
            1 if args.direction == 'buy' else -1)
    except (RuntimeError, ValueError, OSError, json.JSONDecodeError) as error:
        print(f'BLOQUEADO: {error}')
        return 2
    finally:
        mt5.shutdown()
    print(json.dumps({'sent': False, 'intent': intent,
                      'estimated_margin': preflight['estimated_margin'],
                      'required_confirmation': arm_phrase(intent)}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
