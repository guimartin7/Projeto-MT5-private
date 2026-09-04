"""Política final de autorização para uma futura entrada na Clear Demo."""
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


SAO_PAULO = ZoneInfo('America/Sao_Paulo')


def load_daily_permit(path, today):
    if not path.exists():
        return {'valid': False, 'reason': 'daily_execution_permit_missing'}
    try:
        permit = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return {'valid': False, 'reason': 'daily_execution_permit_invalid'}
    required = {
        'mode': 'CLEAR_DEMO_ONLY', 'server': 'ClearInvestimentos-DEMO',
        'symbol': 'WINV26', 'max_volume': 1, 'valid_date': today,
    }
    if any(permit.get(key) != value for key, value in required.items()):
        return {'valid': False, 'reason': 'daily_execution_permit_mismatch'}
    return {'valid': True, 'reason': None, 'permit': permit}


def deal_net_result(deal):
    return sum(float(deal.get(key) or 0) for key in
               ('profit', 'commission', 'fee', 'swap'))


def evaluate_execution_policy(snapshot, journal_status, permit_status, today,
                              max_daily_loss=30.0, max_entries=3):
    blockers = []
    if not snapshot.get('safe_for_new_entry'):
        blockers.append('broker_not_clean')
    if not journal_status.get('ready'):
        blockers.extend(journal_status.get('blockers', ['execution_journal_blocked']))
    if not permit_status.get('valid'):
        blockers.append(permit_status.get('reason', 'daily_execution_permit_invalid'))
    todays = []
    for deal in snapshot.get('recent_deals', []):
        stamp = deal.get('time')
        if stamp is None or deal.get('magic') != 26090301:
            continue
        day = datetime.fromtimestamp(int(stamp), timezone.utc).astimezone(SAO_PAULO).date().isoformat()
        if day == today:
            todays.append(deal)
    realized = sum(deal_net_result(deal) for deal in todays)
    # DEAL_ENTRY_IN é 0; entradas são contadas pelos registros efetivos da corretora.
    entries = sum(deal.get('entry') == 0 for deal in todays)
    if realized <= -max_daily_loss:
        blockers.append('broker_daily_loss_limit')
    if entries >= max_entries:
        blockers.append('broker_daily_entry_limit')
    return {
        'allowed': not blockers, 'blockers': list(dict.fromkeys(blockers)),
        'broker_daily_net_pnl': round(realized, 2),
        'broker_entries_today': entries,
        'max_daily_loss': max_daily_loss, 'max_entries': max_entries,
    }
