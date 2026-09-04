"""Relatório somente leitura das barreiras para execução Demo."""
import json
from pathlib import Path

from execution_journal import journal_readiness, load_journal
from reconciliation import broker_snapshot


def main():
    import MetaTrader5 as mt5
    if not mt5.initialize(r'C:\Program Files\MetaTrader 5\terminal64.exe', timeout=15000):
        print(f'ERRO: conexão MT5: {mt5.last_error()}')
        return 1
    try:
        snapshot = broker_snapshot(mt5)
        terminal, account = mt5.terminal_info(), mt5.account_info()
    except RuntimeError as error:
        print(f'ERRO: {error}')
        return 2
    finally:
        mt5.shutdown()
    journal = load_journal(Path(__file__).parent / 'paper' / 'demo-execution-journal.json')
    journal_status = journal_readiness(journal)
    blockers = []
    if not snapshot['safe_for_new_entry']:
        blockers.append('broker_reconciliation_conflict')
    if not journal_status['ready']:
        blockers.extend(journal_status['blockers'])
    if not terminal.trade_allowed:
        blockers.append('terminal_algo_trading_disabled')
    if terminal.tradeapi_disabled:
        blockers.append('external_python_api_disabled')
    if not account.trade_expert:
        blockers.append('account_expert_trading_disabled')
    report = {
        'mode': 'READ_ONLY_EXECUTION_READINESS', 'ready': not blockers,
        'blockers': blockers, 'broker_status': snapshot['status'],
        'journal': journal_status, 'order_send_available_in_this_command': False,
    }
    print(json.dumps(report, indent=2))
    return 0 if report['ready'] else 3


if __name__ == '__main__':
    raise SystemExit(main())
