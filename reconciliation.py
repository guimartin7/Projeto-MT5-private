"""Reconciliação somente leitura entre o sistema e a Clear Demo."""
from datetime import datetime, timedelta, timezone


MANAGED_MAGIC = 26090301


def _record(item, fields):
    return {field: getattr(item, field, None) for field in fields}


def broker_snapshot(api, symbol='WINV26', now=None):
    account = api.account_info()
    terminal = api.terminal_info()
    if account is None or terminal is None or not terminal.connected:
        raise RuntimeError('Terminal ou conta desconectada.')
    if account.trade_mode != api.ACCOUNT_TRADE_MODE_DEMO:
        raise RuntimeError('Reconciliação recusada fora de conta Demo.')
    if account.server != 'ClearInvestimentos-DEMO':
        raise RuntimeError('Servidor recusado para reconciliação.')
    positions = api.positions_get(symbol=symbol)
    orders = api.orders_get(symbol=symbol)
    if positions is None or orders is None:
        raise RuntimeError(f'Falha ao consultar posição/ordem: {api.last_error()}')
    end = now or datetime.now(timezone.utc)
    deals = api.history_deals_get(end - timedelta(days=7), end, group=f'*{symbol}*')
    if deals is None:
        raise RuntimeError(f'Falha ao consultar negócios: {api.last_error()}')
    position_rows = [_record(item, ('ticket', 'time', 'type', 'magic', 'volume',
                                    'price_open', 'sl', 'tp', 'price_current', 'profit'))
                     for item in positions]
    order_rows = [_record(item, ('ticket', 'time_setup', 'type', 'magic', 'volume_initial',
                                 'volume_current', 'price_open', 'sl', 'tp', 'comment'))
                  for item in orders]
    deal_rows = [_record(item, ('ticket', 'order', 'time', 'type', 'entry', 'magic',
                                'volume', 'price', 'profit', 'commission', 'fee', 'swap'))
                 for item in deals]
    managed_positions = [row for row in position_rows if row['magic'] == MANAGED_MAGIC]
    foreign_positions = [row for row in position_rows if row['magic'] != MANAGED_MAGIC]
    managed_orders = [row for row in order_rows if row['magic'] == MANAGED_MAGIC]
    foreign_orders = [row for row in order_rows if row['magic'] != MANAGED_MAGIC]
    reasons = []
    if len(position_rows) > 1:
        reasons.append('multiple_positions_in_netting_account')
    if foreign_positions:
        reasons.append('foreign_or_manual_position')
    if foreign_orders:
        reasons.append('foreign_or_manual_order')
    if len(managed_positions) > 1:
        reasons.append('multiple_managed_positions')
    status = 'CONFLICT' if reasons else ('MANAGED_EXPOSURE' if managed_positions or managed_orders else 'CLEAN')
    return {
        'mode': 'READ_ONLY_RECONCILIATION', 'server': account.server,
        'balance': getattr(account, 'balance', None),
        'equity': getattr(account, 'equity', None),
        'margin_free': getattr(account, 'margin_free', None),
        'symbol': symbol, 'status': status, 'safe_for_new_entry': status == 'CLEAN',
        'conflict_reasons': reasons, 'positions': position_rows, 'orders': order_rows,
        'managed_position_count': len(managed_positions),
        'managed_order_count': len(managed_orders),
        'foreign_position_count': len(foreign_positions),
        'foreign_order_count': len(foreign_orders),
        'recent_deals': deal_rows[-500:],
        'captured_at_utc': end.isoformat(),
    }


def compare_expected(snapshot, expected_position=None):
    reasons = list(snapshot['conflict_reasons'])
    managed = [row for row in snapshot['positions'] if row['magic'] == MANAGED_MAGIC]
    if expected_position is None and managed:
        reasons.append('broker_has_position_but_local_state_is_flat')
    elif expected_position is not None and not managed:
        reasons.append('local_state_has_position_but_broker_is_flat')
    elif expected_position is not None and managed:
        actual = managed[0]
        if float(actual['volume']) != float(expected_position['volume']):
            reasons.append('position_volume_mismatch')
        if int(actual['type']) != int(expected_position['type']):
            reasons.append('position_direction_mismatch')
        if not actual['sl']:
            reasons.append('broker_position_without_stop')
    return {'matches': not reasons, 'reasons': list(dict.fromkeys(reasons))}
