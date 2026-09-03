"""Read-only MT5 demo diagnostic. Never submits or modifies orders."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def validate_bars(bars):
    if bars is None or len(bars) < 2:
        raise ValueError('Historico insuficiente; abra o grafico M1 no terminal e tente novamente.')
    previous = None
    for bar in bars:
        stamp = int(bar['time'])
        if previous is not None and stamp <= previous:
            raise ValueError('Candles duplicados ou fora de ordem.')
        previous = stamp
        values = [float(bar[key]) for key in ('open', 'high', 'low', 'close')]
        import math
        if not all(math.isfinite(value) and value > 0 for value in values):
            raise ValueError('Preco invalido.')
        opening, high, low, close = values
        if low > min(opening, close) or high < max(opening, close) or low > high:
            raise ValueError('OHLC inconsistente.')
    return len(bars)


def collect(api, terminal, symbol=None):
    if not api.initialize(terminal, timeout=15000):
        raise RuntimeError(f'Falha ao conectar MT5: {api.last_error()}')
    try:
        info = api.terminal_info()
        account = api.account_info()
        if info is None or not info.connected or account is None:
            raise RuntimeError('Terminal desconectado ou conta indisponivel.')
        if account.trade_mode != api.ACCOUNT_TRADE_MODE_DEMO:
            raise RuntimeError('Diagnostico permitido somente em conta demo.')
        symbols = api.symbols_get()
        if symbols is None:
            raise RuntimeError(f'Falha ao listar ativos: {api.last_error()}')
        visible = [item.name for item in symbols if item.visible]
        if not visible:
            raise RuntimeError('Nenhum ativo visivel na Observacao do Mercado.')
        chosen = symbol or ('EURUSD' if 'EURUSD' in visible else visible[0])
        if chosen not in visible:
            raise ValueError('Adicione o ativo manualmente a Observacao do Mercado antes do teste.')
        bars = api.copy_rates_from_pos(chosen, api.TIMEFRAME_M1, 1, 100)
        count = validate_bars(bars)
        tick = api.symbol_info_tick(chosen)
        now = datetime.now(timezone.utc)
        age = None if tick is None else now.timestamp() - tick.time
        time_status = 'MISSING_TICK' if age is None else ('FUTURE_TIMESTAMP' if age < -60 else ('STALE_TICK' if age > 120 else 'OK'))
        return {
            'checked_at_utc': now.isoformat(),
            'mode': 'READ_ONLY_DEMO',
            'connected': bool(info.connected),
            'server': account.server,
            'terminal_build': info.build,
            'available_symbols': len(symbols),
            'visible_symbols': visible,
            'sample_symbol': chosen,
            'closed_m1_bars': count,
            'last_bar_utc': datetime.fromtimestamp(int(bars[-1]['time']), timezone.utc).isoformat(),
            'tick_age_seconds': None if age is None else round(age, 1),
            'time_status': time_status,
            'ready_for_trading': False,
            'note': 'Dados historicos validados; nao implica mercado aberto ou cotacao atualizada.',
        }
    finally:
        api.shutdown()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--terminal', default=r'C:\Program Files\MetaTrader 5\terminal64.exe')
    parser.add_argument('--symbol')
    args = parser.parse_args()
    import MetaTrader5 as mt5
    try:
        report = collect(mt5, args.terminal, args.symbol)
    except (RuntimeError, ValueError) as error:
        print(f'ERRO: {error}')
        return 1
    output = Path(__file__).parent / 'reports'
    output.mkdir(exist_ok=True)
    report_path = output / ('diagnostic-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
    report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    print(f'Relatorio: {report_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
