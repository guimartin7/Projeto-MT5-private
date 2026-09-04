"""Relatório somente leitura das barreiras para execução Demo."""
import json
from pathlib import Path

from execution_journal import journal_readiness, load_journal
from execution_policy import evaluate_execution_policy, load_daily_permit
from reconciliation import broker_snapshot
from datetime import datetime
from zoneinfo import ZoneInfo


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
    today = datetime.now(ZoneInfo('America/Sao_Paulo')).date().isoformat()
    permit = load_daily_permit(Path(__file__).parent / 'paper' /
                               'DEMO_EXECUTION_PERMIT.json', today)
    policy = evaluate_execution_policy(snapshot, journal_status, permit, today)
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
    blockers.extend(policy['blockers'])
    report = {
        'mode': 'READ_ONLY_EXECUTION_READINESS', 'ready': not blockers,
        'blockers': blockers, 'broker_status': snapshot['status'],
        'journal': journal_status, 'execution_policy': policy,
        'daily_permit': {'valid': permit['valid'], 'reason': permit['reason']},
        'order_send_available_in_this_command': False,
    }
    print(json.dumps(report, indent=2))
    return 0 if report['ready'] else 3


if __name__ == '__main__':
    raise SystemExit(main())
