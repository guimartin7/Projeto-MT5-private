from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from demo_execution_gateway import arm_phrase, execute_prepared
from execution_journal import create_intent, empty_journal, save_journal, transition


def prepared(tmp_path):
    path = tmp_path / 'journal.json'
    journal = empty_journal()
    item, _ = create_intent(journal, 'WINV26', 123, 1)
    transition(item, 'PREFLIGHT_APPROVED')
    save_journal(path, journal)
    return path, item


def api_mock():
    api = Mock(TRADE_RETCODE_DONE=10009)
    result = SimpleNamespace(retcode=10009, comment='Done', order=10, deal=11)
    api.order_send.return_value = result
    api.positions_get.return_value = (
        SimpleNamespace(magic=26090301, volume=1, sl=99900),)
    return api


def permit(tmp_path):
    path = tmp_path / 'permit.json'
    path.write_text('{"mode":"CLEAR_DEMO_ONLY","server":"ClearInvestimentos-DEMO","symbol":"WINV26","max_volume":1,"valid_date":"2026-09-03"}', encoding='utf-8')
    return path


def test_missing_double_confirmation_never_sends(tmp_path, monkeypatch):
    path, item = prepared(tmp_path)
    api = api_mock()
    with pytest.raises(RuntimeError, match='Dupla confirmação'):
        execute_prepared(api, path, item['id'], arm_phrase(item), None,
                         permit(tmp_path), '2026-09-03')
    api.order_send.assert_not_called()


def test_persists_sent_before_order_call_and_confirms_protected(tmp_path, monkeypatch):
    path, item = prepared(tmp_path)
    api = api_mock()
    monkeypatch.setattr('demo_execution_gateway.run_preflight', lambda *args: {
        'check_approved': True, 'check_retcode': 0, 'check_comment': 'Done',
        'request': {'symbol': 'WINV26', 'sl': 99900, 'tp': 100200}})
    phrase = arm_phrase(item)
    monkeypatch.setattr('demo_execution_gateway.broker_snapshot', lambda api: {'safe_for_new_entry': True, 'recent_deals': []})
    result = execute_prepared(api, path, item['id'], phrase, phrase,
                              permit(tmp_path), '2026-09-03')
    assert result['status'] == 'CONFIRMED_PROTECTED'
    api.order_send.assert_called_once()


def test_execution_without_confirmed_stop_becomes_unknown(tmp_path, monkeypatch):
    path, item = prepared(tmp_path)
    api = api_mock(); api.positions_get.return_value = ()
    monkeypatch.setattr('demo_execution_gateway.run_preflight', lambda *args: {
        'check_approved': True, 'check_retcode': 0, 'check_comment': 'Done',
        'request': {'symbol': 'WINV26', 'sl': 99900, 'tp': 100200}})
    phrase = arm_phrase(item)
    monkeypatch.setattr('demo_execution_gateway.broker_snapshot', lambda api: {'safe_for_new_entry': True, 'recent_deals': []})
    result = execute_prepared(api, path, item['id'], phrase, phrase,
                              permit(tmp_path), '2026-09-03')
    assert result['status'] == 'UNKNOWN_UNPROTECTED'


def test_rejected_send_is_final(tmp_path, monkeypatch):
    path, item = prepared(tmp_path)
    api = api_mock()
    api.order_send.return_value = SimpleNamespace(retcode=10030, comment='Rejected', order=0, deal=0)
    monkeypatch.setattr('demo_execution_gateway.run_preflight', lambda *args: {
        'check_approved': True, 'check_retcode': 0, 'check_comment': 'Done',
        'request': {'symbol': 'WINV26', 'sl': 99900, 'tp': 100200}})
    phrase = arm_phrase(item)
    monkeypatch.setattr('demo_execution_gateway.broker_snapshot', lambda api: {'safe_for_new_entry': True, 'recent_deals': []})
    assert execute_prepared(api, path, item['id'], phrase, phrase,
                            permit(tmp_path), '2026-09-03')['status'] == 'REJECTED'


def test_missing_daily_permit_never_sends(tmp_path, monkeypatch):
    path, item = prepared(tmp_path)
    api = api_mock(); phrase = arm_phrase(item)
    monkeypatch.setattr('demo_execution_gateway.broker_snapshot', lambda api: {'safe_for_new_entry': True, 'recent_deals': []})
    with pytest.raises(RuntimeError, match='daily_execution_permit_missing'):
        execute_prepared(api, path, item['id'], phrase, phrase,
                         tmp_path / 'missing.json', '2026-09-03')
    api.order_send.assert_not_called()
