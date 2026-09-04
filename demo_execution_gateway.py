"""Gateway da Clear Demo com dupla confirmação. Nunca use em conta real."""
import json
from pathlib import Path

from demo_preflight import PreflightConfig, run_preflight
from execution_journal import (create_intent, journal_readiness, load_journal,
                               save_journal, transition)
from execution_policy import evaluate_execution_policy, load_daily_permit
from reconciliation import MANAGED_MAGIC, broker_snapshot


def arm_phrase(intent):
    return f'DEMO:{intent["id"]}:1-WINV26'


def prepare_intent(api, journal_path, candle_time, direction):
    journal = load_journal(journal_path)
    readiness = journal_readiness(journal)
    if not readiness['ready']:
        raise RuntimeError(f'Diário bloqueado: {readiness["blockers"]}')
    snapshot = broker_snapshot(api)
    if not snapshot['safe_for_new_entry']:
        raise RuntimeError(f'Reconciliação bloqueada: {snapshot["conflict_reasons"]}')
    config = PreflightConfig(direction=direction)
    preflight = run_preflight(api, config)
    if not preflight['check_approved']:
        raise RuntimeError(f'order_check recusou: {preflight["check_comment"]}')
    intent, created = create_intent(journal, config.symbol, candle_time, direction)
    if not created:
        raise RuntimeError('Intenção já existia; preparação duplicada bloqueada.')
    transition(intent, 'PREFLIGHT_APPROVED', retcode=preflight['check_retcode'],
               comment=preflight['check_comment'])
    save_journal(journal_path, journal)
    return intent, preflight


def _protected_position(api, symbol):
    positions = api.positions_get(symbol=symbol)
    if positions is None:
        return False
    matching = [position for position in positions
                if position.magic == MANAGED_MAGIC and position.volume == 1]
    return len(matching) == 1 and bool(matching[0].sl)


def execute_prepared(api, journal_path, intent_id, confirmation, environment_arm,
                     permit_path, today):
    journal = load_journal(journal_path)
    intent = next((item for item in journal['intents'] if item['id'] == intent_id), None)
    if intent is None or intent['status'] != 'PREFLIGHT_APPROVED':
        raise RuntimeError('Intenção preparada não encontrada ou em estado inválido.')
    required = arm_phrase(intent)
    if confirmation != required or environment_arm != required:
        raise RuntimeError('Dupla confirmação Demo ausente ou incorreta.')
    snapshot = broker_snapshot(api)
    permit = load_daily_permit(permit_path, today)
    policy = evaluate_execution_policy(snapshot, journal_readiness({
        **journal, 'intents': [entry for entry in journal['intents']
                               if entry['id'] != intent_id]}), permit, today)
    if not policy['allowed']:
        raise RuntimeError(f'Política de execução bloqueou: {policy["blockers"]}')
    config = PreflightConfig(direction=intent['direction'])
    preflight = run_preflight(api, config)
    if not preflight['check_approved']:
        transition(intent, 'REJECTED', retcode=preflight['check_retcode'],
                   comment=preflight['check_comment'])
        save_journal(journal_path, journal)
        return {'status': 'REJECTED_PREFLIGHT', 'sent': False}
    # Persistir SENT antes da chamada evita repetição cega após queda do processo.
    transition(intent, 'SENT', comment='Persistido antes de order_send.')
    save_journal(journal_path, journal)
    result = api.order_send(preflight['request'])
    if result is None:
        transition(intent, 'UNKNOWN', comment=f'order_send sem resposta: {api.last_error()}')
        save_journal(journal_path, journal)
        return {'status': 'UNKNOWN', 'sent': True}
    evidence = {'retcode': int(result.retcode), 'comment': result.comment,
                'broker_order': int(result.order), 'broker_deal': int(result.deal)}
    if int(result.retcode) != api.TRADE_RETCODE_DONE:
        transition(intent, 'REJECTED', **evidence)
        save_journal(journal_path, journal)
        return {'status': 'REJECTED', 'sent': True, **evidence}
    if not _protected_position(api, intent['symbol']):
        unprotected_evidence = {**evidence,
                                'comment': f'{result.comment}; posição com stop não confirmada.'}
        transition(intent, 'UNKNOWN', **unprotected_evidence)
        save_journal(journal_path, journal)
        return {'status': 'UNKNOWN_UNPROTECTED', 'sent': True,
                **unprotected_evidence}
    transition(intent, 'CONFIRMED', **evidence)
    save_journal(journal_path, journal)
    return {'status': 'CONFIRMED_PROTECTED', 'sent': True, **evidence}


def default_journal_path():
    return Path(__file__).parent / 'paper' / 'demo-execution-journal.json'


def default_permit_path():
    return Path(__file__).parent / 'paper' / 'DEMO_EXECUTION_PERMIT.json'
