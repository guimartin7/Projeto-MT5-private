import pytest

from execution_journal import (create_intent, empty_journal, intent_id,
                               journal_readiness, recover_sent_intent,
                               transition)


def snapshot(positions=(), orders=(), deals=()):
    return {'positions': list(positions), 'orders': list(orders),
            'recent_deals': list(deals)}


def test_intent_is_deterministic_and_idempotent():
    journal = empty_journal()
    first, created = create_intent(journal, 'WINV26', 123, 1)
    again, created_again = create_intent(journal, 'WINV26', 123, 1)
    assert created and not created_again
    assert first is again
    assert first['id'] == intent_id('WINV26', 123, 1)


def test_second_active_intent_is_blocked():
    journal = empty_journal()
    create_intent(journal, 'WINV26', 123, 1)
    with pytest.raises(RuntimeError, match='intenção ativa'):
        create_intent(journal, 'WINV26', 124, -1)


def test_invalid_transition_is_blocked():
    item, _ = create_intent(empty_journal(), 'WINV26', 123, 1)
    with pytest.raises(ValueError, match='Transição inválida'):
        transition(item, 'CONFIRMED')


def test_unknown_outcome_blocks_until_broker_evidence():
    item, _ = create_intent(empty_journal(), 'WINV26', 123, 1)
    transition(item, 'PREFLIGHT_APPROVED')
    transition(item, 'SENT')
    result = recover_sent_intent(item, snapshot())
    assert not result['resolved'] and item['status'] == 'UNKNOWN'
    readiness = journal_readiness({'mode': 'DEMO_EXECUTION_JOURNAL',
                                   'version': 1, 'intents': [item]})
    assert not readiness['ready']
    assert readiness['blockers'] == ['unknown_execution_outcome']


def test_broker_evidence_confirms_sent_intent():
    item, _ = create_intent(empty_journal(), 'WINV26', 123, 1)
    transition(item, 'PREFLIGHT_APPROVED'); transition(item, 'SENT')
    result = recover_sent_intent(item, snapshot(positions=({'magic': 26090301, 'sl': 99900},)))
    assert result['resolved'] and item['status'] == 'CONFIRMED'


def test_unprotected_broker_position_stays_blocked():
    item, _ = create_intent(empty_journal(), 'WINV26', 123, 1)
    transition(item, 'PREFLIGHT_APPROVED'); transition(item, 'SENT')
    result = recover_sent_intent(item, snapshot(positions=({'magic': 26090301, 'sl': 0},)))
    assert not result['resolved'] and item['status'] == 'UNKNOWN'
    assert result['action'] == 'BLOCK_UNPROTECTED_POSITION'


def test_final_intent_allows_next_one():
    journal = empty_journal()
    item, _ = create_intent(journal, 'WINV26', 123, 1)
    transition(item, 'CANCELLED')
    _, created = create_intent(journal, 'WINV26', 124, -1)
    assert created
