"""Diagnóstico somente leitura da margem de 1 WIN na Clear Demo."""
import argparse
import json

from b3_costs import DEFAULT_WIN_COSTS
from b3_instrument import load_b3_spec


def calculate_margin_report(api, symbol='WINV26'):
    spec = load_b3_spec(api, symbol)
    tick = api.symbol_info_tick(symbol)
    bid = float(getattr(tick, 'bid', 0) or 0)
    ask = float(getattr(tick, 'ask', 0) or 0)
    report = {
        'mode': 'READ_ONLY_MARGIN_DIAGNOSTIC', 'symbol': symbol, 'contracts': 1,
        'bid': bid, 'ask': ask, 'broker_buy_margin': None,
        'broker_sell_margin': None,
        'public_clear_reference': DEFAULT_WIN_COSTS.clear_day_trade_margin_reference,
        'order_check_called': False, 'order_send_called': False,
        'instrument': spec.to_dict(),
    }
    if bid <= 0 or ask <= 0:
        report['status'] = 'UNAVAILABLE_NO_VALID_QUOTE'
        report['warning'] = 'Sem bid/ask válido; repita durante o pregão.'
        return report
    buy = api.order_calc_margin(api.ORDER_TYPE_BUY, symbol, 1.0, ask)
    sell = api.order_calc_margin(api.ORDER_TYPE_SELL, symbol, 1.0, bid)
    report['broker_buy_margin'] = None if buy is None else round(float(buy), 2)
    report['broker_sell_margin'] = None if sell is None else round(float(sell), 2)
    report['status'] = ('OK' if buy is not None and sell is not None
                        else 'BROKER_CALCULATION_UNAVAILABLE')
    report['warning'] = ('O cálculo do servidor prevalece; a referência pública '
                         'não autoriza operação.')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--terminal', default=r'C:\Program Files\MetaTrader 5\terminal64.exe')
    parser.add_argument('--symbol', default='WINV26')
    args = parser.parse_args()
    import MetaTrader5 as mt5
    if not mt5.initialize(args.terminal, timeout=15000):
        print(json.dumps({'status': 'CONNECTION_ERROR', 'error': mt5.last_error()}))
        return 1
    try:
        report = calculate_margin_report(mt5, args.symbol)
    except (RuntimeError, ValueError) as error:
        print(json.dumps({'status': 'BLOCKED', 'error': str(error)}, ensure_ascii=False))
        return 1
    finally:
        mt5.shutdown()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report['status'] in ('OK', 'UNAVAILABLE_NO_VALID_QUOTE') else 1


if __name__ == '__main__':
    raise SystemExit(main())
