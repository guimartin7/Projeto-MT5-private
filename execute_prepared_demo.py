"""Executa somente uma intenção Demo previamente preparada e duplamente armada."""
import argparse
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from demo_execution_gateway import (default_journal_path, default_permit_path,
                                    execute_prepared)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--intent', required=True)
    parser.add_argument('--confirm-demo-order', required=True)
    args = parser.parse_args()
    import MetaTrader5 as mt5
    if not mt5.initialize(r'C:\Program Files\MetaTrader 5\terminal64.exe', timeout=15000):
        print(f'BLOQUEADO: conexão: {mt5.last_error()}')
        return 1
    try:
        result = execute_prepared(
            mt5, default_journal_path(), args.intent, args.confirm_demo_order,
            os.environ.get('MT5_DEMO_EXECUTION_ARM'), default_permit_path(),
            datetime.now(ZoneInfo('America/Sao_Paulo')).date().isoformat())
    except (RuntimeError, ValueError, OSError, json.JSONDecodeError) as error:
        print(f'BLOQUEADO: {error}')
        return 2
    finally:
        mt5.shutdown()
    print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'CONFIRMED_PROTECTED' else 3


if __name__ == '__main__':
    raise SystemExit(main())
