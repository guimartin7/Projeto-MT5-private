"""Exibe uma fotografia sanitizada da exposição no WINV26."""
import json

from reconciliation import broker_snapshot, compare_expected


def main():
    import MetaTrader5 as mt5
    if not mt5.initialize(r'C:\Program Files\MetaTrader 5\terminal64.exe', timeout=15000):
        print(f'ERRO: conexão MT5: {mt5.last_error()}')
        return 1
    try:
        snapshot = broker_snapshot(mt5)
        snapshot['expected_flat_check'] = compare_expected(snapshot)
        deals = snapshot.get('recent_deals', [])
        exits = [deal for deal in deals if deal.get('entry') == 1]
        if exits:
            last = exits[-1]
            snapshot['last_exit'] = {
                'ticket': last.get('ticket'),
                'price': last.get('price'),
                'profit': last.get('profit', 0.0),
                'reason': ('STOP/LOSS' if float(last.get('profit', 0) or 0) < 0
                           else 'TAKE_PROFIT/OUTRO')}
        else:
            snapshot['last_exit'] = None
    except RuntimeError as error:
        print(f'ERRO: {error}')
        return 2
    finally:
        mt5.shutdown()
    print(json.dumps(snapshot, indent=2, ensure_ascii=False))
    return 0 if snapshot['expected_flat_check']['matches'] else 3


if __name__ == '__main__':
    raise SystemExit(main())
