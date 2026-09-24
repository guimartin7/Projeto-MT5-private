"""Diagnóstico somente leitura da conta real Clear; nunca envia ordens."""
import json
from datetime import datetime, timezone

TERMINAL = r'C:\Program Files\Clear Investimentos MT5 Terminal\terminal64.exe'
SERVER = 'ClearInvestimentos-CLEAR'
SYMBOL = 'WINV26'

def main():
    import MetaTrader5 as mt5
    if not mt5.initialize(TERMINAL, timeout=15000):
        print(json.dumps({'mode': 'REAL_READ_ONLY', 'connected': False,
                          'error': mt5.last_error()}, ensure_ascii=False))
        return 1
    try:
        account = mt5.account_info()
        if account is None or SERVER not in str(account.server):
            print(json.dumps({'mode': 'REAL_READ_ONLY', 'connected': False,
                              'error': 'servidor real Clear não confirmado',
                              'server': getattr(account, 'server', None)}, ensure_ascii=False))
            return 2
        info = mt5.symbol_info(SYMBOL)
        tick = mt5.symbol_info_tick(SYMBOL)
        positions = mt5.positions_get(symbol=SYMBOL) or []
        orders = mt5.orders_get(symbol=SYMBOL) or []
        report = {
            'mode': 'REAL_READ_ONLY', 'connected': True,
            'captured_at_utc': datetime.now(timezone.utc).isoformat(),
            'server': account.server, 'login': account.login,
            'balance': account.balance, 'equity': account.equity,
            'margin_free': account.margin_free, 'symbol': SYMBOL,
            'bid': getattr(tick, 'bid', None), 'ask': getattr(tick, 'ask', None),
            'positions': len(positions), 'orders': len(orders),
            'order_send_called': False,
            'warning': 'leitura real; nenhuma ordem foi enviada.'}
        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
        return 0
    finally:
        mt5.shutdown()

if __name__ == '__main__':
    raise SystemExit(main())
