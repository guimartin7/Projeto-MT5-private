"""Recuperação conservadora do diário usando a corretora como fonte da verdade."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from execution_journal import (journal_readiness, load_journal,
                               recover_sent_intent, save_journal, transition)
from reconciliation import broker_snapshot


SAO_PAULO = ZoneInfo('America/Sao_Paulo')


def _local_date(iso_timestamp):
    instant = datetime.fromisoformat(iso_timestamp)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    return instant.astimezone(SAO_PAULO).date().isoformat()


def recover_journal(api, journal_path, today):
    journal = load_journal(journal_path)
    snapshot = broker_snapshot(api)
    actions = []
    for item in journal['intents']:
        if item['status'] in {'SENT', 'UNKNOWN'}:
            before = item['status']
            result = recover_sent_intent(item, snapshot)
            actions.append({'id': item['id'], 'before': before,
                            'after': item['status'], **result})
        elif item['status'] in {'CREATED', 'PREFLIGHT_APPROVED'}:
            if _local_date(item['created_at_utc']) != today:
                if snapshot['status'] == 'CLEAN':
                    before = item['status']
                    transition(item, 'CANCELLED',
                               comment='Intenção expirada sem exposição na corretora.')
                    actions.append({'id': item['id'], 'before': before,
                                    'after': 'CANCELLED', 'resolved': True})
                else:
                    actions.append({'id': item['id'], 'before': item['status'],
                                    'after': item['status'], 'resolved': False,
                                    'action': 'BLOCK_EXPIRED_INTENT_WITH_BROKER_EXPOSURE'})
    save_journal(journal_path, journal)
    readiness = journal_readiness(journal)
    return {
        'mode': 'READ_ONLY_BROKER_RECOVERY_LOCAL_JOURNAL_UPDATE',
        'broker_status': snapshot['status'], 'actions': actions,
        'journal_readiness': readiness,
        'safe_to_continue': snapshot['safe_for_new_entry'] and readiness['ready'],
    }
