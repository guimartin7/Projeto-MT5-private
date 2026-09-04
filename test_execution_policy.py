import json

from execution_policy import (evaluate_execution_policy, load_daily_permit)


TODAY = '2026-09-03'


def clean_snapshot(deals=()):
    return {'safe_for_new_entry': True, 'recent_deals': list(deals)}


def valid_permit(tmp_path):
    path = tmp_path / 'permit.json'
    path.write_text(json.dumps({
        'mode': 'CLEAR_DEMO_ONLY', 'server': 'ClearInvestimentos-DEMO',
        'symbol': 'WINV26', 'max_volume': 1, 'valid_date': TODAY,
    }), encoding='utf-8')
    return load_daily_permit(path, TODAY)


def test_missing_expired_and_valid_permits(tmp_path):
    assert load_daily_permit(tmp_path / 'missing', TODAY)['reason'] == 'daily_execution_permit_missing'
    status = valid_permit(tmp_path)
    assert status['valid']
    assert not load_daily_permit(tmp_path / 'permit.json', '2026-09-04')['valid']


def test_policy_uses_broker_loss_and_entry_count(tmp_path):
    deals = [
        {'time': 1788447600, 'magic': 26090301, 'entry': 0,
         'profit': -31, 'commission': 0, 'fee': 0, 'swap': 0},
        {'time': 1788447601, 'magic': 26090301, 'entry': 0,
         'profit': 0, 'commission': 0, 'fee': 0, 'swap': 0},
        {'time': 1788447602, 'magic': 26090301, 'entry': 0,
         'profit': 0, 'commission': 0, 'fee': 0, 'swap': 0},
    ]
    policy = evaluate_execution_policy(clean_snapshot(deals), {'ready': True},
                                       valid_permit(tmp_path), TODAY)
    assert not policy['allowed']
    assert set(policy['blockers']) == {'broker_daily_loss_limit',
                                       'broker_daily_entry_limit'}


def test_policy_allows_clean_state_with_valid_permit(tmp_path):
    policy = evaluate_execution_policy(clean_snapshot(), {'ready': True},
                                       valid_permit(tmp_path), TODAY)
    assert policy['allowed']
