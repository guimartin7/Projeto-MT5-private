"""Reconcilia o diário após falha; nunca envia ordens."""
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from demo_execution_gateway import default_journal_path
from execution_recovery import recover_journal


def main():
    import MetaTrader5 as mt5
    if not mt5.initialize(r'C:\Program Files\MetaTrader 5\terminal64.exe', timeout=15000):
        print(f'ERRO: conexão MT5: {mt5.last_error()}')
        return 1
    try:
        today = datetime.now(ZoneInfo('America/Sao_Paulo')).date().isoformat()
        report = recover_journal(mt5, default_journal_path(), today)
    except (RuntimeError, ValueError, OSError, json.JSONDecodeError) as error:
        print(f'ERRO: {error}')
        return 2
    finally:
        mt5.shutdown()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report['safe_to_continue'] else 3


if __name__ == '__main__':
    raise SystemExit(main())
