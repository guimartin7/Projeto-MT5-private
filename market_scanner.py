"""Scanner somente leitura dos contratos B3 disponibilizados pela Clear Demo."""
import json
from datetime import datetime, timezone
from pathlib import Path


TRADABLE_MODE = 4  # SYMBOL_TRADE_MODE_FULL no MetaTrader 5


def is_supported_contract(info):
    name = str(getattr(info, 'name', '')).upper()
    return (name.startswith(('WIN', 'WDO')) and '$' not in name and
            '@' not in name and int(getattr(info, 'trade_mode', -1)) == TRADABLE_MODE)


def score_quote(bid, ask, tick_size):
    if bid <= 0 or ask <= 0 or ask < bid or tick_size <= 0:
        return {'status': 'NO_VALID_QUOTE', 'score': 0.0, 'spread_ticks': None}
    spread_ticks = (ask - bid) / tick_size
    score = max(0.0, 100.0 - spread_ticks * 10.0)
    return {'status': 'QUOTE_AVAILABLE', 'score': round(score, 2),
            'spread_ticks': round(spread_ticks, 2)}


def scan_symbols(api):
    account = api.account_info()
    if account is None or account.trade_mode != api.ACCOUNT_TRADE_MODE_DEMO:
        raise RuntimeError('Scanner permitido somente na conta Demo.')
    if 'ClearInvestimentos-DEMO' not in account.server:
        raise RuntimeError('Servidor recusado: esperado ClearInvestimentos-DEMO.')
    rows = []
    for info in api.symbols_get() or []:
        if not is_supported_contract(info):
            continue
        name = info.name
        if not getattr(info, 'visible', True):
            api.symbol_select(name, True)
        tick = api.symbol_info_tick(name)
        bid = float(getattr(tick, 'bid', 0) or 0)
        ask = float(getattr(tick, 'ask', 0) or 0)
        quote = score_quote(bid, ask, float(info.trade_tick_size))
        rows.append({
            'symbol': name, 'description': info.description,
            'currency_profit': getattr(info, 'currency_profit', 'BRL'),
            'bid': bid, 'ask': ask, 'tick_size': float(info.trade_tick_size),
            'expiration_time': int(getattr(info, 'expiration_time', 0) or 0),
            **quote, 'eligible_for_authorization': quote['status'] == 'QUOTE_AVAILABLE',
        })
    rows.sort(key=lambda row: (-row['score'], row['symbol']))
    return {
        'mode': 'READ_ONLY_MARKET_SCANNER',
        'server': account.server,
        'captured_at_utc': datetime.now(timezone.utc).isoformat(),
        'contracts_found': len(rows),
        'quote_available': sum(row['eligible_for_authorization'] for row in rows),
        'candidates': rows,
        'selected_candidate': (rows[0]['symbol'] if rows and
                               rows[0]['eligible_for_authorization'] else None),
        'approved_for_orders': False,
        'warning': 'Ranking técnico exploratório; não é recomendação financeira.',
    }


def main():
    import MetaTrader5 as mt5
    terminal = r'C:\Program Files\MetaTrader 5\terminal64.exe'
    if not mt5.initialize(terminal, timeout=15000):
        print(json.dumps({'status': 'CONNECTION_ERROR', 'error': mt5.last_error()}))
        return 1
    try:
        report = scan_symbols(mt5)
    except (RuntimeError, ValueError) as error:
        print(json.dumps({'status': 'BLOCKED', 'error': str(error)}, ensure_ascii=False))
        return 1
    finally:
        mt5.shutdown()
    output = Path(__file__).parent / 'paper'
    output.mkdir(exist_ok=True)
    (output / 'market-scan.json').write_text(
        json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
