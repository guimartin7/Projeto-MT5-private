"""Autorização local da sessão Clear Demo; não envia ordens."""
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


CONFIRMATION = 'AUTORIZAR DEMO WINV26 1 CONTRATO'
SAO_PAULO = ZoneInfo('America/Sao_Paulo')


def normalize_confirmation(value):
    return ''.join(character for character in str(value or '').upper()
                   if character.isalnum())


def authorize_demo_session(path, confirmation, server='ClearInvestimentos-DEMO',
                           symbol='WINV26', max_volume=1, now=None):
    if normalize_confirmation(confirmation) != normalize_confirmation(CONFIRMATION):
        raise ValueError('Confirmação da sessão Demo inválida.')
    if server != 'ClearInvestimentos-DEMO' or symbol != 'WINV26' or max_volume != 1:
        raise ValueError('A autorização está limitada à Clear Demo, WINV26 e 1 contrato.')
    moment = now or datetime.now(SAO_PAULO)
    permit = {
        'mode': 'CLEAR_DEMO_ONLY', 'server': server, 'symbol': symbol,
        'max_volume': max_volume, 'valid_date': moment.date().isoformat(),
        'authorized_at': moment.isoformat(), 'source': 'desktop_dashboard',
        'order_send_called': False,
    }
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix('.tmp')
    temporary.write_text(json.dumps(permit, indent=2), encoding='utf-8')
    temporary.replace(destination)
    return permit
