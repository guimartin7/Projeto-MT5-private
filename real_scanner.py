"""Scanner real somente leitura para WINV26; nunca envia ordens."""
import json
from datetime import datetime, timezone

TERMINAL = r'C:\Program Files\Clear Investimentos MT5 Terminal\terminal64.exe'
SERVER = 'ClearInvestimentos-CLEAR'
SYMBOL = 'WINV26'

def main():
    import MetaTrader5 as mt5
    if not mt5.initialize(TERMINAL, timeout=15000):
        print(json.dumps({'mode': 'REAL_READ_ONLY_SCANNER', 'error': mt5.last_error()}, ensure_ascii=False)); return 1
    try:
        account = mt5.account_info()
        if account is None or SERVER not in str(account.server):
            print(json.dumps({'mode': 'REAL_READ_ONLY_SCANNER', 'error': 'servidor real não confirmado'}, ensure_ascii=False)); return 2
        if not mt5.symbol_select(SYMBOL, True):
            print(json.dumps({'mode': 'REAL_READ_ONLY_SCANNER', 'error': f'ativo {SYMBOL} indisponível'}, ensure_ascii=False)); return 3
        info = mt5.symbol_info(SYMBOL); tick = mt5.symbol_info_tick(SYMBOL)
        rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M5, 0, 60)
        closes = [float(row['close']) for row in rates] if rates is not None else []
        bias = 'NEUTRO'; reason = 'histórico insuficiente'
        if len(closes) >= 21:
            fast, slow = sum(closes[-9:]) / 9, sum(closes[-21:]) / 21
            if fast > slow: bias, reason = 'COMPRA', 'SMA9 acima da SMA21'
            elif fast < slow: bias, reason = 'VENDA', 'SMA9 abaixo da SMA21'
            else: reason = 'médias sem direção'
        report = {'mode': 'REAL_READ_ONLY_SCANNER', 'captured_at_utc': datetime.now(timezone.utc).isoformat(),
                  'server': account.server, 'login': account.login,
                  'balance': account.balance, 'equity': account.equity,
                  'margin_free': account.margin_free,
                  'symbol': SYMBOL, 'currency': getattr(info, 'currency_profit', 'BRL'),
                  'bid': getattr(tick, 'bid', None), 'ask': getattr(tick, 'ask', None),
                  'tick_size': getattr(info, 'trade_tick_size', None), 'bars': len(closes),
                  'bias': bias, 'bias_reason': reason, 'positions': len(mt5.positions_get(symbol=SYMBOL) or []),
                  'orders': len(mt5.orders_get(symbol=SYMBOL) or []), 'order_send_called': False}
        print(json.dumps(report, indent=2, ensure_ascii=False, default=str)); return 0
    finally:
        mt5.shutdown()

if __name__ == '__main__': raise SystemExit(main())
