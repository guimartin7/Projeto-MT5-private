"""Encerra a posição gerenciada Demo após confirmação explícita."""
import argparse, json
from pathlib import Path
TERMINAL = r'C:\Program Files\MetaTrader 5\terminal64.exe'

parser = argparse.ArgumentParser(); parser.add_argument('--confirm-close', required=True)
args = parser.parse_args()
if args.confirm_close != 'CLOSE DEMO WINV26':
    raise SystemExit('Confirmação de encerramento inválida.')
import MetaTrader5 as mt5
if not mt5.initialize(TERMINAL, timeout=15000): raise SystemExit(f'Conexão recusada: {mt5.last_error()}')
try:
    positions = mt5.positions_get(symbol='WINV26') or []
    managed = [p for p in positions if p.magic == 26090301]
    if not managed: print(json.dumps({'sent': False, 'reason': 'posição não encontrada'})); raise SystemExit(0)
    p = managed[0]; tick = mt5.symbol_info_tick('WINV26')
    request = {'action': mt5.TRADE_ACTION_DEAL, 'symbol': 'WINV26', 'volume': p.volume,
               'type': mt5.ORDER_TYPE_SELL if p.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY,
               'position': p.ticket, 'price': tick.bid if p.type == mt5.POSITION_TYPE_BUY else tick.ask,
               'deviation': 10, 'magic': 26090301, 'comment': 'mt5-panel-close',
               'type_time': mt5.ORDER_TIME_DAY, 'type_filling': mt5.ORDER_FILLING_RETURN}
    check = mt5.order_check(request)
    if check is None or check.retcode != 0: raise SystemExit(f'order_check recusou: {getattr(check, "comment", mt5.last_error())}')
    result = mt5.order_send(request)
    print(json.dumps({'sent': True, 'retcode': result.retcode, 'comment': result.comment,
                      'order': result.order, 'deal': result.deal}))
finally: mt5.shutdown()
