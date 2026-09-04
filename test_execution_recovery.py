from datetime import datetime, timezone

from execution_journal import (create_intent, empty_journal, load_journal,
                               save_journal, transition)
from execution_recovery import recover_journal


def snapshot(status='CLEAN', positions=(), orders=(), deals=()):
    return {'status': status, 'safe_for_new_entry': status == 'CLEAN',
            'positions': list(positions), 'orders': list(orders),
            'recent_deals': list(deals)}


def make_journal(tmp_path, status, created='2026-09-02T12:00:00+00:00'):
    path = tmp_path / 'journal.json'
    journal = empty_journal()
    item, _ = create_intent(journal, 'WINV26', 123, 1)
    item['created_at_utc'] = created
    if status == 'PREFLIGHT_APPROVED':
        transition(item, status)
    elif status in {'SENT', 'UNKNOWN'}:
        transition(item, 'PREFLIGHT_APPROVED'); transition(item, 'SENT')
        if status == 'UNKNOWN':
            transition(item, 'UNKNOWN')
    save_journal(path, journal)
    return path, item['id']


def test_stale_preflight_is_cancelled_when_broker_clean(tmp_path, monkeypatch):
    path, identifier = make_journal(tmp_path, 'PREFLIGHT_APPROVED')
    monkeypatch.setattr('execution_recovery.broker_snapshot', lambda api: snapshot())
    report = recover_journal(object(), path, '2026-09-03')
    assert report['safe_to_continue']
    item = load_journal(path)['intents'][0]
    assert item['id'] == identifier and item['status'] == 'CANCELLED'


def test_sent_with_protected_position_is_confirmed(tmp_path, monkeypatch):
    path, _ = make_journal(tmp_path, 'SENT')
    broker = snapshot(status='MANAGED_EXPOSURE',
                      positions=({'magic': 26090301, 'sl': 99900},))
    monkeypatch.setattr('execution_recovery.broker_snapshot', lambda api: broker)
    report = recover_journal(object(), path, '2026-09-03')
    assert load_journal(path)['intents'][0]['status'] == 'CONFIRMED'
    assert not report['safe_to_continue']  # posição existente continua bloqueando entrada


def test_sent_without_evidence_becomes_unknown_and_blocks(tmp_path, monkeypatch):
    path, _ = make_journal(tmp_path, 'SENT')
    monkeypatch.setattr('execution_recovery.broker_snapshot', lambda api: snapshot())
    report = recover_journal(object(), path, '2026-09-03')
    assert not report['safe_to_continue']
    assert report['journal_readiness']['unknown_intents'] == 1


def test_expired_intent_is_not_cancelled_during_conflict(tmp_path, monkeypatch):
    path, _ = make_journal(tmp_path, 'CREATED')
    monkeypatch.setattr('execution_recovery.broker_snapshot',
                        lambda api: snapshot(status='CONFLICT'))
    report = recover_journal(object(), path, '2026-09-03')
    assert not report['safe_to_continue']
    assert load_journal(path)['intents'][0]['status'] == 'CREATED'
