"""Diário persistente e idempotente de futuras intenções de execução Demo."""
import hashlib
import json
from datetime import datetime, timezone


ACTIVE_STATES = {'CREATED', 'PREFLIGHT_APPROVED', 'SENT', 'UNKNOWN'}
FINAL_STATES = {'CONFIRMED', 'REJECTED', 'CANCELLED'}


def intent_id(symbol, candle_time, direction):
    raw = f'{symbol}:{int(candle_time)}:{int(direction)}'.encode()
    return hashlib.sha256(raw).hexdigest()[:20]


def empty_journal():
    return {'mode': 'DEMO_EXECUTION_JOURNAL', 'version': 1, 'intents': []}


def validate_journal(journal):
    if journal.get('mode') != 'DEMO_EXECUTION_JOURNAL' or journal.get('version') != 1:
        raise ValueError('Diário de execução inválido.')
    identifiers = [item.get('id') for item in journal.get('intents', [])]
    if None in identifiers or len(identifiers) != len(set(identifiers)):
        raise ValueError('Diário contém intenções inválidas ou duplicadas.')
    allowed = ACTIVE_STATES | FINAL_STATES
    if any(item.get('status') not in allowed for item in journal['intents']):
        raise ValueError('Diário contém estado desconhecido.')
    return True


def load_journal(path):
    if not path.exists():
        return empty_journal()
    journal = json.loads(path.read_text(encoding='utf-8'))
    validate_journal(journal)
    return journal


def save_journal(path, journal):
    validate_journal(journal)
    path.parent.mkdir(exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(journal, indent=2), encoding='utf-8')
    temporary.replace(path)


def create_intent(journal, symbol, candle_time, direction, volume=1):
    validate_journal(journal)
    identifier = intent_id(symbol, candle_time, direction)
    existing = next((item for item in journal['intents'] if item['id'] == identifier), None)
    if existing:
        return existing, False
    if volume != 1 or symbol != 'WINV26' or direction not in (-1, 1):
        raise ValueError('Intenção fora do escopo inicial seguro.')
    if any(item['status'] in ACTIVE_STATES for item in journal['intents']):
        raise RuntimeError('Já existe uma intenção ativa; nova intenção bloqueada.')
    item = {
        'id': identifier, 'symbol': symbol, 'candle_time': int(candle_time),
        'direction': int(direction), 'volume': 1, 'status': 'CREATED',
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'broker_order': None, 'broker_deal': None,
    }
    journal['intents'].append(item)
    return item, True


def transition(item, target, **evidence):
    transitions = {
        'CREATED': {'PREFLIGHT_APPROVED', 'REJECTED', 'CANCELLED'},
        'PREFLIGHT_APPROVED': {'SENT', 'REJECTED', 'CANCELLED'},
        'SENT': {'CONFIRMED', 'REJECTED', 'UNKNOWN'},
        'UNKNOWN': {'CONFIRMED', 'REJECTED'},
    }
    current = item['status']
    if target not in transitions.get(current, set()):
        raise ValueError(f'Transição inválida: {current} -> {target}.')
    item['status'] = target
    item['updated_at_utc'] = datetime.now(timezone.utc).isoformat()
    for key in ('broker_order', 'broker_deal', 'retcode', 'comment'):
        if key in evidence:
            item[key] = evidence[key]
    return item


def recover_sent_intent(item, snapshot):
    if item['status'] not in {'SENT', 'UNKNOWN'}:
        return {'resolved': True, 'status': item['status']}
    managed_positions = [row for row in snapshot['positions'] if row['magic'] == 26090301]
    managed_orders = [row for row in snapshot['orders'] if row['magic'] == 26090301]
    managed_deals = [row for row in snapshot['recent_deals'] if row['magic'] == 26090301]
    protected_positions = [row for row in managed_positions if row.get('sl')]
    if protected_positions:
        if item['status'] == 'SENT':
            transition(item, 'CONFIRMED')
        elif item['status'] == 'UNKNOWN':
            transition(item, 'CONFIRMED')
        return {'resolved': True, 'status': 'CONFIRMED'}
    if managed_positions:
        if item['status'] == 'SENT':
            transition(item, 'UNKNOWN', comment='Posição encontrada sem stop confirmado.')
        return {'resolved': False, 'status': 'UNKNOWN',
                'action': 'BLOCK_UNPROTECTED_POSITION'}
    if managed_orders or managed_deals:
        if item['status'] == 'SENT':
            transition(item, 'UNKNOWN', comment='Evidência parcial sem posição protegida confirmada.')
        return {'resolved': False, 'status': 'UNKNOWN',
                'action': 'BLOCK_AND_RECONCILE_PARTIAL_EVIDENCE'}
    if item['status'] == 'SENT':
        transition(item, 'UNKNOWN', comment='Nenhuma evidência encontrada na corretora.')
    return {'resolved': False, 'status': 'UNKNOWN',
            'action': 'BLOCK_AND_REQUIRE_MANUAL_REVIEW'}


def journal_readiness(journal):
    active = [item for item in journal['intents'] if item['status'] in ACTIVE_STATES]
    unknown = [item for item in active if item['status'] == 'UNKNOWN']
    return {
        'ready': not active, 'active_intents': len(active),
        'unknown_intents': len(unknown),
        'blockers': (['unknown_execution_outcome'] if unknown else
                     ['active_execution_intent'] if active else []),
    }
