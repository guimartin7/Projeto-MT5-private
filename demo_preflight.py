"""Pré-validação de ordem Clear Demo. Nunca envia a solicitação ao servidor."""
import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone

from b3_instrument import load_b3_spec
from b3_paper import SAO_PAULO, market_phase
from health import assess_feed


@dataclass(frozen=True)
class PreflightConfig:
    symbol: str = 'WINV26'
    volume: float = 1.0
    stop_points: float = 100.0
    target_points: float = 200.0
    direction: int = 1
    deviation_points: int = 10
    magic: int = 26090301


def round_to_tick(price, tick_size):
    return round(price / tick_size) * tick_size


def validate_context(api, config, now=None):
    terminal, account = api.terminal_info(), api.account_info()
    if terminal is None or account is None or not terminal.connected:
        raise RuntimeError('Terminal ou conta desconectada.')
    if account.trade_mode != api.ACCOUNT_TRADE_MODE_DEMO:
        raise RuntimeError('Pré-validação recusada fora de conta Demo.')
    if account.server != 'ClearInvestimentos-DEMO':
        raise RuntimeError('Servidor recusado: esperado ClearInvestimentos-DEMO.')
    if account.margin_mode != api.ACCOUNT_MARGIN_MODE_RETAIL_NETTING:
        raise RuntimeError('Conta recusada: esperado modo Netting.')
    if config.symbol != 'WINV26' or config.volume != 1:
        raise RuntimeError('Escopo inicial limitado a 1 contrato de WINV26.')
    if config.direction not in (-1, 1):
        raise ValueError('Direção deve ser compra (1) ou venda (-1).')
    moment = (now or datetime.now(timezone.utc)).astimezone(SAO_PAULO)
    if market_phase(moment) != 'ENTRY_ALLOWED':
        raise RuntimeError('Pré-validação disponível somente na janela de entrada B3.')
    positions, orders = api.positions_get(symbol=config.symbol), api.orders_get(symbol=config.symbol)
    if positions is None or orders is None:
        raise RuntimeError(f'Falha ao consultar exposição: {api.last_error()}')
    if positions or orders:
        raise RuntimeError('Já existe posição ou ordem no ativo; nova entrada bloqueada.')
    if not terminal.trade_allowed:
        raise RuntimeError('Negociação algorítmica está desabilitada no terminal.')
    if terminal.tradeapi_disabled:
        raise RuntimeError('API externa Python está desabilitada no terminal.')
    if not account.trade_allowed or not account.trade_expert:
        raise RuntimeError('Conta não permite negociação automatizada.')


def build_request(api, config, spec):
    tick = api.symbol_info_tick(config.symbol)
    if tick is None:
        raise RuntimeError('Cotação indisponível.')
    feed = assess_feed(tick.time, tick.bid, tick.ask)
    if not feed['healthy']:
        raise RuntimeError(f'Feed recusado: {feed["status"]}.')
    buying = config.direction == 1
    price = float(tick.ask if buying else tick.bid)
    stop = price - config.stop_points if buying else price + config.stop_points
    target = price + config.target_points if buying else price - config.target_points
    return {
        'action': api.TRADE_ACTION_DEAL, 'symbol': config.symbol,
        'volume': config.volume, 'type': api.ORDER_TYPE_BUY if buying else api.ORDER_TYPE_SELL,
        'price': round_to_tick(price, spec.tick_size),
        'sl': round_to_tick(stop, spec.tick_size),
        'tp': round_to_tick(target, spec.tick_size),
        'deviation': config.deviation_points, 'magic': config.magic,
        'comment': 'mt5-lab-demo-preflight', 'type_time': api.ORDER_TIME_DAY,
        'type_filling': api.ORDER_FILLING_IOC,
    }, feed


def run_preflight(api, config, now=None):
    validate_context(api, config, now)
    spec = load_b3_spec(api, config.symbol)
    request, feed = build_request(api, config, spec)
    margin = api.order_calc_margin(request['type'], request['symbol'], request['volume'], request['price'])
    if margin is None:
        raise RuntimeError(f'Não foi possível calcular margem: {api.last_error()}')
    result = api.order_check(request)
    if result is None:
        raise RuntimeError(f'order_check falhou: {api.last_error()}')
    return {
        'mode': 'DEMO_PREFLIGHT_ONLY', 'would_send_order': False,
        'server': 'ClearInvestimentos-DEMO', 'request': request,
        'estimated_margin': float(margin), 'feed_health': feed,
        'check_retcode': int(result.retcode), 'check_comment': result.comment,
        'check_approved': int(result.retcode) == 0,
        'warning': 'order_check aprovado não garante execução de uma ordem futura.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--direction', choices=('buy', 'sell'), default='buy')
    args = parser.parse_args()
    import MetaTrader5 as mt5
    terminal = r'C:\Program Files\MetaTrader 5\terminal64.exe'
    if not mt5.initialize(terminal, timeout=15000):
        print(f'BLOQUEADO: conexão MT5: {mt5.last_error()}')
        return 1
    try:
        report = run_preflight(mt5, PreflightConfig(direction=1 if args.direction == 'buy' else -1))
    except (RuntimeError, ValueError) as error:
        print(f'BLOQUEADO: {error}')
        return 2
    finally:
        mt5.shutdown()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report['check_approved'] else 3


if __name__ == '__main__':
    raise SystemExit(main())
