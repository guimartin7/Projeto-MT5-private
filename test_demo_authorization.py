import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from demo_authorization import CONFIRMATION, authorize_demo_session


TZ = ZoneInfo('America/Sao_Paulo')


def test_authorization_creates_daily_clear_demo_permit_without_order_send(tmp_path):
    path = tmp_path / 'DEMO_EXECUTION_PERMIT.json'
    permit = authorize_demo_session(path, CONFIRMATION,
                                    now=datetime(2026, 9, 6, 10, 0, tzinfo=TZ))
    saved = json.loads(path.read_text(encoding='utf-8'))
    assert permit['valid_date'] == '2026-09-06'
    assert saved['server'] == 'ClearInvestimentos-DEMO'
    assert saved['max_volume'] == 1
    assert saved['order_send_called'] is False


def test_authorization_rejects_wrong_confirmation(tmp_path):
    with pytest.raises(ValueError, match='inválida'):
        authorize_demo_session(tmp_path / 'permit.json', 'SIM')


def test_authorization_accepts_case_and_extra_spaces(tmp_path):
    permit = authorize_demo_session(
        tmp_path / 'permit.json', '  autorizar   demo winv26 1 contrato  ',
        now=datetime(2026, 9, 6, 10, 0, tzinfo=TZ))
    assert permit['symbol'] == 'WINV26'


def test_authorization_accepts_accidental_punctuation(tmp_path):
    permit = authorize_demo_session(
        tmp_path / 'permit.json', 'Autorizar-demo: WINV26 (1) contrato!',
        now=datetime(2026, 9, 6, 10, 0, tzinfo=TZ))
    assert permit['max_volume'] == 1
